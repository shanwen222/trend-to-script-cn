#!/usr/bin/env python3
"""Report available data-source backends without exposing credentials or logging in."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMMANDS = ("agent-reach", "mcporter", "opencli", "bili", "yt-dlp", "gh", "curl")


def find_yuwen_precheck() -> Path | None:
    """Locate a complete external yuwen-publish-precheck installation."""
    configured = os.environ.get("YUWEN_PRECHECK_HOME", "").strip()
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path.home() / ".codex" / "skills" / "yuwen-publish-precheck",
        Path.home() / ".agents" / "skills" / "yuwen-publish-precheck",
        Path(__file__).resolve().parents[2] / "yuwen-publish-precheck",
    ]
    required = ("SKILL.md", "scripts/scan.py", "references/judgment.md")
    for candidate in candidates:
        if candidate and all((candidate / item).is_file() for item in required):
            return candidate
    return None


def find_humanizer() -> Path | None:
    """Locate the external humanizer-zh skill without exposing local paths."""
    configured = os.environ.get("HUMANIZER_ZH_HOME", "").strip()
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path.home() / ".codex" / "skills" / "humanizer-zh",
        Path.home() / ".agents" / "skills" / "humanizer-zh",
        Path(__file__).resolve().parents[2] / "humanizer-zh",
    ]
    for candidate in candidates:
        if candidate and (candidate / "SKILL.md").is_file():
            return candidate
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查热点到成稿Skill可用的数据源；不打印密钥，不执行登录")
    parser.add_argument("--timeout", type=float, default=20.0, help="Agent Reach Doctor超时秒数")
    parser.add_argument("--compact", action="store_true", help="输出单行JSON")
    parser.add_argument("--show-paths", action="store_true", help="排障时显示命令绝对路径；默认隐藏")
    return parser.parse_args()


def executable_candidates(name: str) -> list[Path]:
    suffix = ".exe" if os.name == "nt" else ""
    home = Path.home()
    candidates = [home / ".local" / "bin" / f"{name}{suffix}"]
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.extend((Path(appdata) / "Python").glob(f"Python*/Scripts/{name}.exe"))
    return candidates


def find_executable(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in executable_candidates(name):
        if candidate.is_file():
            return str(candidate)
    return None


def run_doctor(
    executable: str,
    timeout: float,
    command_paths: list[str],
) -> tuple[dict[str, Any] | None, str | None]:
    env = os.environ.copy()
    extra_path = [str(Path(path).parent) for path in command_paths]
    env["PATH"] = os.pathsep.join([*dict.fromkeys(extra_path), env.get("PATH", "")])
    try:
        completed = subprocess.run(
            [executable, "doctor", "--json"],
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)

    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        return None, stderr or stdout or f"doctor exit={completed.returncode}"
    try:
        return json.loads(stdout), None
    except json.JSONDecodeError as exc:
        return None, f"doctor returned invalid JSON: {exc}"


def summarize_channels(doctor: dict[str, Any] | None) -> dict[str, Any]:
    if not doctor:
        return {}
    return {
        name: {
            "status": value.get("status"),
            "active_backend": value.get("active_backend"),
        }
        for name, value in doctor.items()
        if isinstance(value, dict)
    }


def main() -> int:
    args = parse_args()
    commands = {name: find_executable(name) for name in COMMANDS}
    doctor = None
    doctor_error = None
    if commands["agent-reach"]:
        doctor, doctor_error = run_doctor(
            commands["agent-reach"],
            args.timeout,
            [path for path in commands.values() if path],
        )

    command_report = {name: {"available": bool(path)} for name, path in commands.items()}
    yuwen_precheck = find_yuwen_precheck()
    humanizer = find_humanizer()
    if args.show_paths:
        for name, path in commands.items():
            command_report[name]["path"] = path

    output = {
        "checked_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "credentials": {"tianapi_key_configured": bool(os.environ.get("TIANAPI_KEY", "").strip())},
        "commands": command_report,
        "agent_reach": {
            "doctor_ran": doctor is not None,
            "error": doctor_error,
            "channels": summarize_channels(doctor),
        },
        "review_engines": {
            "yuwen_publish_precheck": {
                "available": yuwen_precheck is not None,
                "complete_install": yuwen_precheck is not None,
                "supported_platforms": ["抖音", "小红书", "微信视频号"],
            }
        },
        "writing_engines": {
            "humanizer_zh": {
                "available": humanizer is not None,
                "complete_install": bool(
                    humanizer
                    and (humanizer / "SKILL.md").is_file()
                    and (humanizer / "LICENSE").is_file()
                ),
            }
        },
    }
    if args.show_paths and yuwen_precheck:
        output["review_engines"]["yuwen_publish_precheck"]["path"] = str(yuwen_precheck)
    if args.show_paths and humanizer:
        output["writing_engines"]["humanizer_zh"]["path"] = str(humanizer)
    print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if commands["agent-reach"] or os.environ.get("TIANAPI_KEY") else 1


if __name__ == "__main__":
    raise SystemExit(main())
