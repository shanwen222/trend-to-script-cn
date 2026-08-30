#!/usr/bin/env python3
"""Install and verify the mandatory upstream Skills for trend-to-script-cn."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "references" / "dependencies.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="安装并检查本 Skill 的强制外部依赖")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只检查，不写入文件；默认模式")
    mode.add_argument("--ensure", action="store_true", help="安装缺失依赖并检查")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args()


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def unique_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.expanduser().resolve()).lower()
        if key not in seen:
            seen.add(key)
            result.append(path.expanduser())
    return result


def skill_roots() -> list[Path]:
    configured = os.environ.get("TREND_TO_SCRIPT_SKILLS_HOME", "").strip()
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    paths: list[Path] = []
    if configured:
        return [Path(configured).expanduser()]
    if codex_home:
        paths.append(Path(codex_home) / "skills")
    paths.extend(
        [
            Path.home() / ".codex" / "skills",
            Path.home() / ".agents" / "skills",
            Path.home() / ".claude" / "skills",
        ]
    )
    return unique_paths(paths)


def required_files_exist(path: Path, required_files: list[str]) -> bool:
    return path.is_dir() and all((path / relative).is_file() for relative in required_files)


def locate_dependency(dependency: dict[str, Any]) -> Path | None:
    for root in skill_roots():
        candidate = root / dependency["name"]
        if required_files_exist(candidate, dependency["required_files"]):
            return candidate
    return None


def target_path(dependency: dict[str, Any]) -> Path:
    return skill_roots()[0] / dependency["name"]


def find_agent_reach() -> str | None:
    executable = shutil.which("agent-reach")
    if executable:
        return executable
    candidates: list[Path] = []
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            candidates.extend(Path(appdata).glob("Python/Python*/Scripts/agent-reach.exe"))
        candidates.append(Path(sys.executable).parent / "Scripts" / "agent-reach.exe")
    else:
        candidates.append(Path.home() / ".local" / "bin" / "agent-reach")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def archive_url(dependency: dict[str, Any]) -> str:
    return f"https://github.com/{dependency['repo']}/archive/{dependency['ref']}.zip"


def download_skill(dependency: dict[str, Any], destination: Path) -> tuple[bool, str]:
    if destination.exists():
        if required_files_exist(destination, dependency["required_files"]):
            return True, "already_present"
        return False, f"已有目录但文件不完整：{destination}；为保护现有文件，未覆盖"

    with tempfile.TemporaryDirectory(prefix="trend-to-script-dependency-") as temporary:
        archive = Path(temporary) / "source.zip"
        try:
            urllib.request.urlretrieve(archive_url(dependency), archive)
            extract_root = Path(temporary) / "extract"
            extract_root.mkdir()
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(extract_root)
        except (OSError, urllib.error.URLError, zipfile.BadZipFile) as exc:
            return False, f"下载或解压失败：{exc}"

        top_levels = [path for path in extract_root.iterdir() if path.is_dir()]
        if len(top_levels) != 1:
            return False, "上游压缩包结构无法识别"
        source = top_levels[0] / dependency["skill_path"]
        if not required_files_exist(source, dependency["required_files"]):
            return False, "上游压缩包缺少 Skill 必需文件"
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination)
        except OSError as exc:
            return False, f"写入 Skill 目录失败：{exc}"
    return True, "installed"


def install_agent_reach_cli(dependency: dict[str, Any], ensure: bool) -> tuple[bool, str]:
    executable = find_agent_reach()
    if executable:
        return True, "already_present"
    if not ensure:
        return False, "agent-reach 命令未找到"
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--user",
        archive_url(dependency),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Python 用户级安装失败：{exc}"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "未知错误").strip().splitlines()[-1]
        return False, f"Python 用户级安装失败：{detail}"
    if not find_agent_reach():
        return False, "安装完成但当前终端找不到 agent-reach；请重启终端后重试"
    return True, "installed"


def check_agent_reach(executable: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {"command_available": bool(executable), "doctor": "not_run"}
    if not executable:
        return result
    try:
        completed = subprocess.run(
            [executable, "doctor", "--json"],
            capture_output=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["doctor"] = "failed"
        result["doctor_error"] = str(exc)
        return result
    if completed.returncode != 0:
        result["doctor"] = "failed"
        result["doctor_error"] = "doctor exit code %s" % completed.returncode
        return result
    try:
        payload = json.loads(completed.stdout.decode("utf-8", errors="replace"))
        result["doctor"] = "passed"
        result["healthy_channels"] = sum(
            1 for value in payload.values() if isinstance(value, dict) and value.get("status") == "ok"
        )
    except json.JSONDecodeError:
        result["doctor"] = "invalid_json"
    return result


def build_report(ensure: bool) -> dict[str, Any]:
    manifest = load_manifest()
    dependencies: list[dict[str, Any]] = manifest["dependencies"]
    report: dict[str, Any] = {
        "manifest_schema": manifest.get("schema_version"),
        "skills_root": str(skill_roots()[0]),
        "dependencies": [],
    }
    for dependency in dependencies:
        existing = locate_dependency(dependency)
        if existing:
            skill_status = {"status": "ready", "path": str(existing), "action": "already_present"}
        elif ensure:
            destination = target_path(dependency)
            ok, action = download_skill(dependency, destination)
            skill_status = {
                "status": "ready" if ok else "failed",
                "path": str(destination),
                "action": action,
            }
        else:
            skill_status = {"status": "missing", "path": str(target_path(dependency))}

        item: dict[str, Any] = {"name": dependency["name"], "skill": skill_status}
        if dependency.get("cli_package"):
            executable = find_agent_reach()
            cli_ok, cli_action = install_agent_reach_cli(dependency, ensure)
            item["cli"] = {"status": "ready" if cli_ok else "failed", "action": cli_action}
            item["doctor"] = check_agent_reach(find_agent_reach())
        report["dependencies"].append(item)

    report["ready"] = all(
        item["skill"]["status"] == "ready"
        and ("cli" not in item or item["cli"]["status"] == "ready")
        for item in report["dependencies"]
    )
    if not report["ready"]:
        report["status"] = "blocked_by_dependencies"
    else:
        report["status"] = "ready"
    return report


def main() -> int:
    args = parse_args()
    report = build_report(ensure=args.ensure)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("依赖状态：%s" % report["status"])
        for item in report["dependencies"]:
            line = f"- {item['name']}: {item['skill']['status']}"
            if "cli" in item:
                line += f"；命令 {item['cli']['status']}"
            print(line)
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
