from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
