from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_sensitive import scan_bytes, scan_text


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class ContractFixtureTests(unittest.TestCase):
    def load_fixtures(self) -> list[dict]:
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(FIXTURES.glob("*.json"))
        ]

    def test_three_public_beta_scenarios_exist(self) -> None:
        fixtures = self.load_fixtures()
        self.assertEqual(
            {fixture["id"] for fixture in fixtures},
            {
                "maternal-douyin",
                "ai-education-xiaohongshu",
                "fortune-wechat-video",
            },
        )

    def test_scenarios_declare_workflow_invariants(self) -> None:
        required = {
            "requires_source_coverage",
            "requires_fact_lock",
            "requires_actual_char_count",
            "requires_quality_review",
            "requires_naturalness_status",
            "requires_publish_precheck",
            "publish_precheck_platform_supported",
        }
        for fixture in self.load_fixtures():
            with self.subTest(fixture=fixture["id"]):
                request = fixture["request"]
                expected = fixture["expected_invariants"]
                self.assertTrue(required.issubset(expected))
                self.assertTrue(all(expected[name] for name in required))
                self.assertLess(request["word_count"]["min"], request["word_count"]["max"])
                self.assertIn(request["naturalness"], {"auto", "required"})
                self.assertIn(request["publish_precheck"], {"auto", "required"})
                self.assertTrue(expected["preferred_sources"])
                self.assertTrue(expected["forbidden_claim_types"])

    def test_short_video_scenarios_require_first_three_second_hook(self) -> None:
        fixtures = {item["id"]: item for item in self.load_fixtures()}
        self.assertTrue(
            fixtures["maternal-douyin"]["expected_invariants"]["requires_first_3s_hook"]
        )
        self.assertTrue(
            fixtures["fortune-wechat-video"]["expected_invariants"]["requires_first_3s_hook"]
        )
        self.assertFalse(
            fixtures["ai-education-xiaohongshu"]["expected_invariants"]["requires_first_3s_hook"]
        )

        strategy = (ROOT / "references" / "content-strategy.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("短视频前三秒硬门槛", strategy)
        self.assertIn("自然朗读计时", strategy)

    def test_risk_specific_routes_are_preserved(self) -> None:
        fixtures = {item["id"]: item for item in self.load_fixtures()}
        self.assertIn(
            "medical_if_health_claims",
            fixtures["maternal-douyin"]["expected_invariants"]["risk_routes"],
        )
        fortune_forbidden = " ".join(
            fixtures["fortune-wechat-video"]["expected_invariants"]["forbidden_claim_types"]
        )
        self.assertRegex(fortune_forbidden, "生死|疾病")
        self.assertRegex(fortune_forbidden, "收益")

    def test_skill_reference_links_exist(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        links = re.findall(r"\[[^\]]+\]\((references/[^)]+)\)", skill)
        self.assertGreaterEqual(len(links), 7)
        for link in links:
            with self.subTest(link=link):
                self.assertTrue((ROOT / link).is_file())

    def test_platform_publish_asset_fields_are_documented(self) -> None:
        contract = (ROOT / "references" / "input-output.md").read_text(encoding="utf-8")
        platform = (ROOT / "references" / "platform-output.md").read_text(encoding="utf-8")
        for field in (
            "cover",
            "main_title",
            "subtitle",
            "video_title_suggestions",
            "video_description",
            "topic_title_suggestions",
        ):
            with self.subTest(field=field):
                self.assertIn(field, contract)
        self.assertIn("封面主标题建议", platform)
        self.assertIn("视频简介建议", platform)
        self.assertIn("话题标题建议", platform)

    def test_mandatory_dependency_gate_is_documented(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        bootstrap = (ROOT / "scripts" / "bootstrap_dependencies.py").read_text(encoding="utf-8")
        manifest = (ROOT / "references" / "dependencies.json").read_text(encoding="utf-8")
        self.assertIn("bootstrap_dependencies.py --ensure --json", skill)
        self.assertIn("blocked_by_dependencies", skill)
        self.assertIn("dependencies.json", bootstrap)
        for dependency in ("agent-reach", "humanizer-zh", "yuwen-publish-precheck"):
            self.assertIn(dependency, manifest)

    def test_public_beta_packaging_is_present(self) -> None:
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.2.0")
        self.assertTrue((ROOT / "LICENSE").is_file())
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        for dependency in ("Agent Reach", "Humanizer-zh", "yuwen-publish-precheck", "天聚数行（TianAPI）"):
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, notices)

    def test_publish_security_gate_is_documented_and_wired(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("check_sensitive.py --pre-push --json", skill)
        self.assertIn("不要使用 `git add .`", skill)
        self.assertIn("check_sensitive.py --pre-push --json", readme)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("python scripts/check_sensitive.py --history", workflow)
        self.assertIn("scripts/check_sensitive.py", (ROOT / "hooks" / "pre-push").read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "scripts" / "install_pre_push_hook.py").is_file())

    def test_clean_worktree_scan_passes(self) -> None:
        scanner = ROOT / "scripts" / "check_sensitive.py"
        result = subprocess.run(
            [sys.executable, str(scanner), "--worktree-only", "--repo", str(ROOT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_scanner_detects_media_headers_and_mixed_binary_secrets(self) -> None:
        github_token = b"ghp" + b"_" + (b"A" * 24)
        findings = scan_bytes(
            b"\x89PNG\r\n\x1a\n\x00\xff" + github_token,
            source="worktree",
            path="portrait.bin",
            commit="",
        )
        rules = {finding.rule for finding in findings}
        self.assertIn("png_header", rules)
        self.assertIn("nul_byte_binary", rules)
        self.assertIn("github_token", rules)
        self.assertTrue(all(github_token.decode() not in str(finding) for finding in findings))

    def test_sensitive_scanner_detects_secrets_and_personal_data_without_echoing_values(self) -> None:
        github_token = "ghp" + "_" + ("A" * 24)
        email = "test" + "@" + "example.com"
        mobile = "138" + "00123456"
        sample = "token" + "=" + '"' + github_token + '" email=' + email + " phone=" + mobile
        findings = scan_text(sample, source="test", path="sample.txt")
        rules = {finding.rule for finding in findings}
        self.assertIn("github_token", rules)
        self.assertIn("email", rules)
        self.assertIn("mainland_mobile", rules)
        self.assertTrue(all(github_token not in str(finding) for finding in findings))
        self.assertTrue(all(email not in str(finding) for finding in findings))

    def test_sensitive_scanner_allows_documented_placeholders(self) -> None:
        findings = scan_text(
            'TIANAPI_KEY="your_key_here" TOKEN="placeholder"',
            source="test",
            path="example.txt",
        )
        self.assertEqual(findings, [])

    def test_deleted_history_media_and_secret_are_detected(self) -> None:
        scanner = ROOT / "scripts" / "check_sensitive.py"
        with tempfile.TemporaryDirectory(prefix="trend_scan_") as directory:
            repo = Path(directory)
            self._run_git(repo, "init")
            token = "ghp" + "_" + ("B" * 24)
            (repo / "portrait.jpg").write_bytes(b"\xff\xd8\xff\x00")
            (repo / "old_secret.txt").write_text("token=" + token, encoding="utf-8")
            self._run_git(repo, "add", "portrait.jpg", "old_secret.txt")
            self._run_git(repo, "commit", "-m", "old materials")
            first_commit = self._run_git(repo, "rev-parse", "HEAD")
            (repo / "portrait.jpg").unlink()
            (repo / "old_secret.txt").unlink()
            self._run_git(repo, "add", "-u", "portrait.jpg", "old_secret.txt")
            self._run_git(repo, "commit", "-m", "remove old materials")
            second_commit = self._run_git(repo, "rev-parse", "HEAD")
            result = subprocess.run(
                [sys.executable, str(scanner), "--history", "--repo", str(repo), "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            rules = {item["rule"] for item in payload["findings"]}
            self.assertIn("jpeg_header", rules)
            self.assertIn("github_token", rules)
            self.assertTrue(all(item["commit"] for item in payload["findings"]))
            self.assertNotIn(token, result.stdout)
            push_input = f"refs/heads/main {second_commit} refs/heads/main {'0' * 40}\n"
            pushed = subprocess.run(
                [sys.executable, str(scanner), "--pre-push", "--repo", str(repo), "--json"],
                input=push_input,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertNotEqual(pushed.returncode, 0)
            pushed_payload = json.loads(pushed.stdout)
            self.assertTrue(any(item["source"] == "pre-push" for item in pushed_payload["findings"]))
            self.assertIn(first_commit, {item["commit"] for item in pushed_payload["findings"]})
            self.assertNotIn(token, pushed.stdout)

    def test_install_hook_does_not_overwrite_unknown_hook(self) -> None:
        installer = ROOT / "scripts" / "install_pre_push_hook.py"
        with tempfile.TemporaryDirectory(prefix="trend_hook_") as directory:
            repo = Path(directory)
            self._run_git(repo, "init")
            target = repo / ".git" / "hooks" / "pre-push"
            target.write_text("#!/bin/sh\necho unknown\n", encoding="utf-8")
            original = target.read_text(encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(installer), "--repo", str(repo)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            forced = subprocess.run(
                [sys.executable, str(installer), "--repo", str(repo), "--force"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
            installed = target.read_text(encoding="utf-8")
            self.assertIn("scripts/check_sensitive.py", installed)
            self.assertIn("--pre-push", installed)

    @staticmethod
    def _run_git(repo: Path, *args: str) -> str:
        environment = os.environ.copy()
        test_email = "test" + "@" + "example.com"
        environment.update(
            {
                "GIT_AUTHOR_NAME": "Test User",
                "GIT_AUTHOR_EMAIL": test_email,
                "GIT_COMMITTER_NAME": "Test User",
                "GIT_COMMITTER_EMAIL": test_email,
            }
        )
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout.strip()


if __name__ == "__main__":
    unittest.main()
