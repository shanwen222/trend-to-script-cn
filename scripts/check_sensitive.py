#!/usr/bin/env python3
"""Scan a repository for credentials, personal data, and local-path leaks.

The scanner is dependency-free and never prints matched content. Use it before
staging or pushing a public repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_SCAN_BYTES = 2 * 1024 * 1024
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}
SAFE_FILENAMES = {".env.example"}


@dataclass(frozen=True)
class Finding:
    source: str
    path: str
    line: int | None
    category: str
    rule: str


@dataclass(frozen=True)
class Unscanned:
    source: str
    path: str
    reason: str


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "github_token",
        re.compile(r"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    ),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"),
    ),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("basic_auth_url", re.compile(r"(?i)\bhttps?://[^/\s:@]+:[^/\s@]+@")),
    (
        "credential_assignment",
        re.compile(
            r'''(?ix)\b(?:api[_-]?key|access[_-]?key|secret(?:[_-]?key)?|auth(?:entication)?[_-]?token|password|passwd|token|cookie|authorization)\b\s*(?:=|:)\s*(?:"([^"\r\n]+)"|'([^'\r\n]+)')'''
        ),
    ),
)

_WINDOWS_USER_PATH = r"[A-Z]:\\" + "Users" + r"\\[A-Za-z0-9._-]{2,}"
_UNIX_USER_PATH = "/" + "Users" + r"/[A-Za-z0-9._-]{2,}"
_HOME_USER_PATH = "/" + "home" + r"/[A-Za-z0-9._-]{2,}"


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
        re.compile("(?i)(?:" + "|".join((_WINDOWS_USER_PATH, _UNIX_USER_PATH, _HOME_USER_PATH)) + ")"),
    ),
)

SUSPICIOUS_FILENAME = re.compile(
    r"(?i)^(?:\.env(?:\..*)?|id_rsa(?:\..*)?|.*\.(?:pem|key|p12|pfx)|credentials?\.json|service[-_]?account.*\.json)$"
)
PLACEHOLDER_TERMS = (
    "your_key_here",
    "your-token",
    "your_token",
    "example",
    "placeholder",
    "redact",
    "replace_me",
    "change_me",
    "dummy",
    "<",
    "[",
    "***",
    "xxxx",
    "...",
)


def is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        not normalized
        or normalized.startswith("$")
        or any(term in normalized for term in PLACEHOLDER_TERMS)
    )


def _add_line_findings(
    findings: list[Finding], *, source: str, path: str, line_number: int, text: str
) -> None:
    for rule, pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if rule == "credential_assignment":
            values = [group for group in match.groups() if group is not None]
            if values and is_placeholder(values[0]):
                continue
        findings.append(
            Finding(
                source=source,
                path=path,
                line=line_number,
                category="secret",
                rule=rule,
            )
        )
    for rule, pattern in PII_PATTERNS:
        if pattern.search(text):
            findings.append(
                Finding(
                    source=source,
                    path=path,
                    line=line_number,
                    category="privacy",
                    rule=rule,
                )
            )


def scan_text(text: str, *, source: str, path: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        _add_line_findings(
            findings,
            source=source,
            path=path,
            line_number=line_number,
            text=line,
        )
    return findings


def _filename_finding(*, source: str, path: str) -> Finding | None:
    basename = Path(path).name
    if basename in SAFE_FILENAMES or not SUSPICIOUS_FILENAME.fullmatch(basename):
        return None
    return Finding(
        source=source,
        path=path,
        line=None,
        category="secret",
        rule="suspicious_filename",
    )


def _decode_text(data: bytes) -> str | None:
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _scan_bytes(
    data: bytes,
    *,
    source: str,
    path: str,
    findings: list[Finding],
    unscanned: list[Unscanned],
) -> None:
    if len(data) > MAX_SCAN_BYTES:
        unscanned.append(
            Unscanned(source=source, path=path, reason="file exceeds 2 MiB scan limit")
        )
        return
    text = _decode_text(data)
    if text is None:
        unscanned.append(
            Unscanned(source=source, path=path, reason="binary or non-UTF-8 file")
        )
        return
    findings.extend(scan_text(text, source=source, path=path))


def _iter_worktree_files() -> list[Path]:
    files: list[Path] = []
    for directory, dirnames, filenames in os.walk(ROOT, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if not path.is_symlink():
                files.append(path)
    return files


def scan_worktree(root: Path = ROOT) -> tuple[list[Finding], list[Unscanned]]:
    del root  # The public API is fixed to the Skill repository root for safety.
    findings: list[Finding] = []
    unscanned: list[Unscanned] = []
    for path in _iter_worktree_files():
        relative = path.relative_to(ROOT).as_posix()
        filename_finding = _filename_finding(source="working_tree", path=relative)
        if filename_finding:
            findings.append(filename_finding)
        try:
            data = path.read_bytes()
        except OSError as exc:
            unscanned.append(
                Unscanned(source="working_tree", path=relative, reason=f"read failed: {exc}")
            )
            continue
        _scan_bytes(
            data,
            source="working_tree",
            path=relative,
            findings=findings,
            unscanned=unscanned,
        )
    return findings, unscanned


def scan_git_history(root: Path = ROOT) -> tuple[list[Finding], list[Unscanned]]:
    del root  # The public API is fixed to the Skill repository root for safety.
    findings: list[Finding] = []
    unscanned: list[Unscanned] = []
    try:
        listed = subprocess.run(
            ["git", "rev-list", "--objects", "--all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        unscanned.append(
            Unscanned(source="git_history", path="<git>", reason=f"history listing failed: {exc}")
        )
        return findings, unscanned

    seen: set[str] = set()
    for entry in listed.stdout.splitlines():
        object_id, separator, object_path = entry.partition(" ")
        if not separator or object_id in seen:
            continue
        seen.add(object_id)
        try:
            object_type = subprocess.run(
                ["git", "cat-file", "-t", object_id],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="ascii",
                errors="replace",
            ).stdout.strip()
            if object_type != "blob":
                continue
            data = subprocess.run(
                ["git", "cat-file", "-p", object_id],
                cwd=ROOT,
                check=True,
                capture_output=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            unscanned.append(
                Unscanned(
                    source="git_history",
                    path=f"{object_id[:12]}/{object_path}",
                    reason=f"object read failed: {exc}",
                )
            )
            continue
        display_path = f"{object_id[:12]}/{object_path}"
        filename_finding = _filename_finding(source="git_history", path=display_path)
        if filename_finding:
            findings.append(filename_finding)
        _scan_bytes(
            data,
            source="git_history",
            path=display_path,
            findings=findings,
            unscanned=unscanned,
        )
    return findings, unscanned


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan the working tree and/or reachable Git history without printing matched content."
    )
    parser.add_argument("--working-tree", action="store_true", help="scan repository files, including untracked files")
    parser.add_argument("--history", action="store_true", help="scan blobs reachable from all local Git refs")
    parser.add_argument("--pre-push", action="store_true", help="scan both working tree and reachable Git history")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    no_scope = not (args.working_tree or args.history or args.pre_push)
    scan_worktree_requested = args.working_tree or args.pre_push or no_scope
    scan_history_requested = args.history or args.pre_push or no_scope

    findings: list[Finding] = []
    unscanned: list[Unscanned] = []
    scopes: list[str] = []
    if scan_worktree_requested:
        scopes.append("working_tree")
        worktree_findings, worktree_unscanned = scan_worktree()
        findings.extend(worktree_findings)
        unscanned.extend(worktree_unscanned)
    if scan_history_requested:
        scopes.append("git_history")
        history_findings, history_unscanned = scan_git_history()
        findings.extend(history_findings)
        unscanned.extend(history_unscanned)

    status = "blocked" if findings or unscanned else "clear"
    payload = {
        "status": status,
        "scopes": scopes,
        "finding_count": len(findings),
        "unscanned_count": len(unscanned),
        "findings": [asdict(item) for item in findings],
        "unscanned": [asdict(item) for item in unscanned],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Sensitive/privacy scan: {status.upper()}")
        for item in findings:
            location = f":{item.line}" if item.line is not None else ""
            print(f"- {item.source}:{item.path}{location} [{item.category}/{item.rule}]")
        for item in unscanned:
            print(f"- {item.source}:{item.path} [unscanned: {item.reason}]")
        if status == "clear":
            print("No credential, personal-data, suspicious-file, or local-path patterns found.")
        else:
            print("Do not stage or push until every finding is reviewed and cleared.")
    return 1 if status == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
