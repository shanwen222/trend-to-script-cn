#!/usr/bin/env python3
"""Scan repository content before it is published to GitHub.

This is the single repository-publication scanner. It has no third-party
dependencies and never prints matched content.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_REPO = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 10 * 1024 * 1024
ZERO_SHA = "0" * 40

MEDIA_EXTENSIONS = {
    ".3g2", ".3gp", ".avi", ".bmp", ".flac", ".gif", ".ico", ".jpeg", ".jpg",
    ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4", ".mpeg", ".mpg", ".pdf",
    ".png", ".psd", ".rar", ".riff", ".svg", ".tar", ".tif", ".tiff", ".wav",
    ".webm", ".webp", ".zip",
}

_WINDOWS_USER_PATH = r"[A-Z]:\\" + "Users" + r"\\[A-Za-z0-9._-]{2,}"
_UNIX_USER_PATH = "/" + "Users" + r"/[A-Za-z0-9._-]{2,}"
_HOME_USER_PATH = "/" + "home" + r"/[A-Za-z0-9._-]{2,}"

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "github_token",
        re.compile(
            r"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})"
        ),
    ),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b")),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"),
    ),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("basic_auth_url", re.compile(r"(?i)\bhttps?://[^/\s:@]+:[^/\s@]+@")),
    (
        "credential_assignment",
        re.compile(
            r'''(?ix)\b(?:api[_-]?key|access[_-]?key|secret(?:[_-]?key)?|client[_-]?secret|auth(?:entication)?[_-]?token|password|passwd|token|cookie|authorization)\b\s*(?:=|:)\s*(?:"([^"\r\n]+)"|'([^'\r\n]+)')'''
        ),
    ),
    (
        "cookie_header",
        re.compile(r"(?i)\b(?:cookie|set-cookie)\s*:\s*[^\r\n=]{1,80}=[^\r\n]{8,}"),
    ),
)

PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "email",
        re.compile(r"(?i)(?<![\w.+-])[\w.+-]{1,64}@(?:[\w-]+\.)+[A-Za-z]{2,}(?![\w.-])"),
    ),
    ("mainland_mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    (
        "china_id_card",
        re.compile(
            r"(?<!\d)[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
        ),
    ),
    (
        "labeled_personal_data",
        re.compile(
            r"(?:姓名|身份证(?:号码|号)?|手机号(?:码)?|家庭住址|住址|收货地址|银行卡号|微信号|出生日期|生日)\s*[：:]\s*(?!示例|example|your|placeholder|<|\[)(?:[^\s,，;；|]+)"
        ),
    ),
    (
        "local_user_path",
        re.compile(
            "(?i)(?:"
            + "|".join((_WINDOWS_USER_PATH, _UNIX_USER_PATH, _HOME_USER_PATH))
            + ")"
        ),
    ),
)

EMBEDDED_IMAGE_DATA = re.compile(
    r"(?is)data:image/(?:png|jpe?g|gif|webp|bmp|svg\+xml);base64,[A-Za-z0-9+/=\s]{100,}"
)
EMBEDDED_MEDIA_BASE64 = re.compile(
    r"(?i)(?:iVBORw0KGgo|/9j/4AAQ|R0lGOD|JVBERi0|UEsDB)[A-Za-z0-9+/=]{60,}"
)
LONG_BASE64 = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{240,}={0,2}(?![A-Za-z0-9+/])")
SUSPICIOUS_FILENAME = re.compile(
    r"(?i)^(?:\.env(?:\..*)?|id_rsa(?:\..*)?|.*\.(?:pem|key|p12|pfx)|credentials?\.json|service[-_]?account.*\.json)$"
)
PLACEHOLDER_TERMS = (
    "your_key_here", "your-token", "your_token", "example", "placeholder", "redact",
    "replace_me", "change_me", "dummy", "<", "[", "***", "xxxx", "...",
)


@dataclass(frozen=True)
class Finding:
    source: str
    path: str
    rule: str
    commit: str = ""


def is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        not normalized
        or normalized.startswith("$")
        or any(term in normalized for term in PLACEHOLDER_TERMS)
    )


def _finding(source: str, path: str, rule: str, commit: str = "") -> Finding:
    return Finding(source=source, path=path, rule=rule, commit=commit)


def _dedupe(findings: list[Finding]) -> list[Finding]:
    unique: dict[tuple[str, str, str, str], Finding] = {}
    for item in findings:
        unique[(item.source, item.path, item.rule, item.commit)] = item
    return sorted(unique.values(), key=lambda item: (item.source, item.path, item.rule, item.commit))


def scan_text(text: str, *, source: str, path: str, commit: str = "") -> list[Finding]:
    findings: list[Finding] = []
    for rule, pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if rule == "credential_assignment":
            values = [group for group in match.groups() if group is not None]
            if values and is_placeholder(values[0]):
                continue
        findings.append(_finding(source, path, rule, commit))
    for rule, pattern in PII_PATTERNS:
        if pattern.search(text):
            findings.append(_finding(source, path, rule, commit))
    if EMBEDDED_IMAGE_DATA.search(text) or EMBEDDED_MEDIA_BASE64.search(text):
        findings.append(_finding(source, path, "embedded_image_data", commit))
    elif LONG_BASE64.search(text):
        findings.append(_finding(source, path, "embedded_base64", commit))
    return findings


def _media_header_rules(data: bytes) -> list[str]:
    rules: list[str] = []
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        rules.append("png_header")
    if data.startswith(b"\xff\xd8\xff"):
        rules.append("jpeg_header")
    if data.startswith((b"GIF87a", b"GIF89a")):
        rules.append("gif_header")
    if data.startswith(b"%PDF-"):
        rules.append("pdf_header")
    if data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        rules.append("zip_header")
    if data.startswith(b"\x00\x00\x01\x00"):
        rules.append("ico_header")
    if data.startswith(b"RIFF"):
        rules.append("riff_header")
        if len(data) >= 12 and data[8:12] == b"WEBP":
            rules.append("webp_header")
    if len(data) >= 8 and data[4:8] == b"ftyp":
        rules.append("media_container_header")
    return rules


def scan_bytes(data: bytes, *, source: str, path: str, commit: str = "") -> list[Finding]:
    findings: list[Finding] = []
    if Path(path).suffix.lower() in MEDIA_EXTENSIONS:
        findings.append(_finding(source, path, "media_extension", commit))
    for rule in _media_header_rules(data):
        findings.append(_finding(source, path, rule, commit))
    if len(data) > MAX_FILE_BYTES:
        findings.append(_finding(source, path, "large_file", commit))
        return _dedupe(findings)
    if b"\x00" in data:
        findings.append(_finding(source, path, "nul_byte_binary", commit))
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        findings.append(_finding(source, path, "non_utf8_binary", commit))
        text = data.decode("latin-1")
    findings.extend(scan_text(text, source=source, path=path, commit=commit))
    return _dedupe(findings)


def _suspicious_filename(path: str, *, source: str, commit: str = "") -> list[Finding]:
    basename = Path(path).name
    if basename == ".env.example" or not SUSPICIOUS_FILENAME.fullmatch(basename):
        return []
    return [_finding(source, path, "suspicious_filename", commit)]


def _git(repo: Path, args: list[str], *, input_data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=repo, input=input_data, capture_output=True, check=False
    )


def _resolve_repo(repo_arg: str | None) -> Path | None:
    candidate = Path(repo_arg).expanduser().resolve() if repo_arg else DEFAULT_REPO
    result = _git(candidate, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        return None
    return Path(os.fsdecode(result.stdout.strip())).resolve()


def _nul_list(result: subprocess.CompletedProcess[bytes]) -> list[str] | None:
    if result.returncode != 0:
        return None
    return [os.fsdecode(item) for item in result.stdout.split(b"\x00") if item]


def scan_worktree(repo: Path) -> list[Finding]:
    tracked = _nul_list(_git(repo, ["ls-files", "-z"]))
    untracked = _nul_list(_git(repo, ["ls-files", "--others", "--exclude-standard", "-z"]))
    if tracked is None or untracked is None:
        return [_finding("scanner", "<repository>", "worktree_listing_failed")]
    findings: list[Finding] = []
    for relative in sorted(set(tracked + untracked)):
        path = repo / Path(relative)
        safe_relative = Path(relative).as_posix()
        if path.is_symlink():
            findings.append(_finding("worktree", safe_relative, "symlink_file"))
            continue
        if not path.is_file():
            # A tracked file deleted in the working tree is not part of the
            # next upload; historical scans cover its previous contents.
            continue
        findings.extend(_suspicious_filename(safe_relative, source="worktree"))
        try:
            data = path.read_bytes()
        except OSError:
            findings.append(_finding("worktree", safe_relative, "file_read_failed"))
            continue
        findings.extend(scan_bytes(data, source="worktree", path=safe_relative))
    return _dedupe(findings)


def _all_commits(repo: Path) -> list[str] | None:
    result = _git(repo, ["rev-list", "--all"])
    if result.returncode != 0:
        return None
    return [line.decode("ascii", errors="replace") for line in result.stdout.splitlines() if line]


def _range_commits(repo: Path, local_sha: str, remote_sha: str) -> list[str] | None:
    args = ["rev-list", local_sha]
    if remote_sha != ZERO_SHA:
        args.extend(["--not", remote_sha])
    result = _git(repo, args)
    if result.returncode != 0:
        return None
    return [line.decode("ascii", errors="replace") for line in result.stdout.splitlines() if line]


def _tree_entries(repo: Path, commit: str) -> list[tuple[str, str]] | None:
    result = _git(repo, ["ls-tree", "-r", "-z", "--full-tree", commit])
    if result.returncode != 0:
        return None
    entries: list[tuple[str, str]] = []
    for raw_entry in result.stdout.split(b"\x00"):
        if not raw_entry:
            continue
        metadata, separator, raw_path = raw_entry.partition(b"\t")
        if not separator:
            continue
        parts = metadata.split()
        if len(parts) != 3 or parts[1] != b"blob":
            continue
        entries.append((parts[2].decode("ascii"), os.fsdecode(raw_path)))
    return entries


def scan_commits(repo: Path, commits: list[str], *, source: str) -> list[Finding]:
    findings: list[Finding] = []
    blob_context: dict[str, tuple[str, str]] = {}
    for commit in commits:
        entries = _tree_entries(repo, commit)
        if entries is None:
            findings.append(_finding("scanner", "<history>", "history_tree_unavailable", commit))
            continue
        for blob_sha, path in entries:
            findings.extend(_suspicious_filename(path, source=source, commit=commit))
            blob_context.setdefault(blob_sha, (path, commit))
    for blob_sha, (path, commit) in blob_context.items():
        result = _git(repo, ["cat-file", "-p", blob_sha])
        if result.returncode != 0:
            findings.append(_finding("scanner", path, "history_object_unreadable", commit))
            continue
        findings.extend(scan_bytes(result.stdout, source=source, path=path, commit=commit))
    return _dedupe(findings)


def scan_history(repo: Path) -> list[Finding]:
    commits = _all_commits(repo)
    if commits is None:
        return [_finding("scanner", "<history>", "history_listing_failed")]
    return scan_commits(repo, commits, source="history")


def _read_push_lines() -> list[tuple[str, str]]:
    if sys.stdin.isatty():
        return []
    lines = sys.stdin.read().splitlines()
    ranges: list[tuple[str, str]] = []
    for line in lines:
        parts = line.split()
        if len(parts) != 4:
            continue
        _, local_sha, _, remote_sha = parts
        if re.fullmatch(r"[0-9a-fA-F]{40}", local_sha) and re.fullmatch(
            r"[0-9a-fA-F]{40}", remote_sha
        ):
            ranges.append((local_sha, remote_sha))
    return ranges


def scan_pre_push(repo: Path) -> list[Finding]:
    findings = scan_worktree(repo)
    ranges = _read_push_lines()
    if not ranges:
        commits = _all_commits(repo)
        if commits is None:
            return _dedupe(findings + [_finding("scanner", "<history>", "pre_push_history_unavailable")])
        return _dedupe(findings + scan_commits(repo, commits, source="pre-push"))
    commits: list[str] = []
    for local_sha, remote_sha in ranges:
        if local_sha == ZERO_SHA:
            continue
        range_commits = _range_commits(repo, local_sha, remote_sha)
        if range_commits is None:
            findings.append(_finding("scanner", "<push-range>", "pre_push_range_unavailable"))
            continue
        commits.extend(range_commits)
    return _dedupe(findings + scan_commits(repo, sorted(set(commits)), source="pre-push"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan repository worktree, Git history, or the current pre-push range."
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--history", action="store_true", help="scan all blobs in all reachable Git history")
    scope.add_argument("--worktree-only", action="store_true", help="scan tracked and unignored untracked worktree files")
    scope.add_argument("--pre-push", action="store_true", help="scan worktree and commits supplied by a pre-push hook")
    parser.add_argument("--repo", help="repository path; defaults to this project")
    parser.add_argument("--json", action="store_true", help="emit JSON without matched content")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo = _resolve_repo(args.repo)
    if repo is None:
        findings = [_finding("scanner", "<repository>", "repository_unavailable")]
    elif args.history:
        findings = scan_history(repo)
    elif args.worktree_only:
        findings = scan_worktree(repo)
    else:
        findings = scan_pre_push(repo)
    findings = _dedupe(findings)
    status = "blocked" if findings else "clear"
    payload = {"status": status, "findings": [asdict(item) for item in findings]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"status={status}")
        for item in findings:
            print(f"source={item.source} path={item.path} rule={item.rule} commit={item.commit}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
