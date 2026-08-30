#!/usr/bin/env python3
"""Install this project's tracked pre-push hook into a repository's .git/hooks."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOK_SOURCE = PROJECT_ROOT / "hooks" / "pre-push"


def git_path(repo: Path, *args: str) -> Path | None:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    output = Path(os.fsdecode(result.stdout.strip()))
    return (repo / output).resolve() if not output.is_absolute() else output.resolve()


def resolve_repo(value: str | None) -> Path | None:
    candidate = Path(value).expanduser().resolve() if value else PROJECT_ROOT
    return git_path(candidate, "rev-parse", "--show-toplevel")


def install(repo: Path, *, force: bool) -> tuple[bool, str]:
    if not HOOK_SOURCE.is_file():
        return False, "tracked hook source is missing"
    hooks_dir = git_path(repo, "rev-parse", "--git-path", "hooks")
    if hooks_dir is None:
        return False, "target is not a Git repository"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    target = hooks_dir / "pre-push"
    source = HOOK_SOURCE.read_bytes()
    if target.exists():
        try:
            existing = target.read_bytes()
        except OSError:
            return False, "existing hook cannot be read"
        if existing == source:
            return True, f"already installed: {target}"
        if not force:
            return False, f"unknown existing hook not overwritten: {target}"
        backup = target.with_name("pre-push.backup")
        if not backup.exists():
            shutil.copy2(target, backup)
    fd, temporary_name = tempfile.mkstemp(prefix="pre-push.", dir=hooks_dir)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(source)
        if os.name != "nt":
            temporary.chmod(0o755)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    if os.name != "nt":
        target.chmod(0o755)
    return True, f"installed: {target}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the current project's pre-push hook.")
    parser.add_argument("--repo", help="target repository; defaults to the current project")
    parser.add_argument("--force", action="store_true", help="overwrite an unknown existing hook after backing it up")
    args = parser.parse_args(argv)
    repo = resolve_repo(args.repo)
    if repo is None:
        print("source=installer path=<repository> rule=repository_unavailable commit=")
        return 1
    ok, message = install(repo, force=args.force)
    if ok:
        print(message)
        return 0
    print(f"source=installer path=.git/hooks/pre-push rule=install_blocked commit=")
    print(message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
