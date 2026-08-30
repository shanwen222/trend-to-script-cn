#!/usr/bin/env python3
"""Validate the public repository without network access or credentials."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_sensitive import scan_history, scan_worktree


REQUIRED = (
    "SKILL.md",
    "README.md",
    "LICENSE",
    "VERSION",
    "THIRD_PARTY_NOTICES.md",
    "agents/openai.yaml",
    "scripts/check_sources.py",
    "scripts/bootstrap_dependencies.py",
    "scripts/check_sensitive.py",
    "scripts/tianapi_hotsearch.py",
    "references/dependencies.json",
    "references/dependency-bootstrap.md",
    "hooks/pre-push",
    "scripts/install_pre_push_hook.py",
)
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".txt", ""}
SECRET_ASSIGNMENT = re.compile(
    r"""(?i)(?:TIANAPI_KEY|XHS_COOKIE|AUTH_TOKEN|API_KEY|SECRET)\s*[:=]\s*["']([^"']+)["']"""
)
ALLOWED_SECRET_VALUES = {"your_key_here", "example", "placeholder", "***"}
LOCAL_PATH = re.compile(r"(?:[A-Za-z]:\\Users\\|/Users/|/home/[^/\s]+/)")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def check_required(errors: list[str]) -> None:
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            fail(errors, f"missing required file: {relative}")


def check_skill(errors: list[str]) -> None:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(errors, "SKILL.md must start with YAML frontmatter")
    if not re.search(r"(?m)^name:\s*trend-to-script-cn\s*$", text):
        fail(errors, "SKILL.md name must be trend-to-script-cn")
    if not re.search(r"(?m)^description:\s*.+$", text):
        fail(errors, "SKILL.md needs a description")


def check_markdown_links(errors: list[str]) -> None:
    pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        for target in pattern.findall(path.read_text(encoding="utf-8")):
            clean = target.strip("<>").split("#", 1)[0]
            if not clean or "://" in clean or clean.startswith("mailto:"):
                continue
            if not (path.parent / clean).resolve().exists():
                fail(errors, f"broken local link in {path.relative_to(ROOT)}: {target}")


def check_python(errors: list[str]) -> None:
    for path in ROOT.rglob("*.py"):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            fail(errors, f"python syntax error in {path.relative_to(ROOT)}: {exc}")


def check_fixtures(errors: list[str]) -> None:
    fixtures = sorted((ROOT / "tests" / "fixtures").glob("*.json"))
    if len(fixtures) != 3:
        fail(errors, f"expected 3 regression fixtures, found {len(fixtures)}")
    for path in fixtures:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(errors, f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
            continue
        for key in ("id", "request", "expected_invariants"):
            if key not in payload:
                fail(errors, f"{path.relative_to(ROOT)} missing key: {key}")


def check_dependency_manifest(errors: list[str]) -> None:
    path = ROOT / "references" / "dependencies.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(errors, f"invalid dependency manifest: {exc}")
        return
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list) or len(dependencies) != 3:
        fail(errors, "dependency manifest must declare exactly 3 mandatory dependencies")
        return
    expected = {"agent-reach", "humanizer-zh", "yuwen-publish-precheck"}
    actual = {item.get("name") for item in dependencies if isinstance(item, dict)}
    if actual != expected:
        fail(errors, f"dependency manifest names mismatch: {sorted(actual)}")
    for item in dependencies:
        if not isinstance(item, dict) or not re.fullmatch(r"[0-9a-f]{40}", str(item.get("ref", ""))):
            fail(errors, "dependency manifest refs must be full commit SHAs")


def check_repository_hygiene(errors: list[str]) -> None:
    ignored_dirs = {".git", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in ignored_dirs for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if LOCAL_PATH.search(text):
            fail(errors, f"local absolute path found in {path.relative_to(ROOT)}")
        for match in SECRET_ASSIGNMENT.finditer(text):
            value = match.group(1).strip()
            if value not in ALLOWED_SECRET_VALUES and not value.startswith("$"):
                fail(errors, f"possible credential found in {path.relative_to(ROOT)}")
    for unwanted in ("output", ".env", "__pycache__"):
        if (ROOT / unwanted).exists():
            fail(errors, f"unwanted generated path in repository: {unwanted}")


def check_sensitive_content(errors: list[str]) -> None:
    findings = scan_worktree(ROOT)
    history_findings = scan_history(ROOT)
    for item in [*findings, *history_findings]:
        fail(
            errors,
            f"sensitive/privacy scan hit in {item.source}:{item.path} "
            f"[rule={item.rule} commit={item.commit}]",
        )


def main() -> int:
    errors: list[str] = []
    check_required(errors)
    check_skill(errors)
    check_markdown_links(errors)
    check_python(errors)
    check_fixtures(errors)
    check_dependency_manifest(errors)
    check_repository_hygiene(errors)
    check_sensitive_content(errors)
    if errors:
        print("Repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
