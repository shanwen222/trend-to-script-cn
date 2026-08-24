from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "tianapi_hotsearch.py"
SPEC = importlib.util.spec_from_file_location("tianapi_hotsearch", MODULE_PATH)
assert SPEC and SPEC.loader
tianapi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tianapi)


class TianApiNormalizationTests(unittest.TestCase):
    def test_normalizes_douyin_without_inventing_fields(self) -> None:
        items = tianapi.normalize(
            "douyin",
            [{"word": "测试热点", "hotindex": 12345, "label": 17}],
        )
        self.assertEqual(
            items,
            [{
                "rank": 1,
                "title": "测试热点",
                "hotness": "12,345",
                "platform": "抖音",
                "tag": "新",
            }],
        )

    def test_normalizes_each_provider_shape(self) -> None:
        weibo = tianapi.normalize(
            "weibo",
            [{"hotword": "微博话题", "hotwordnum": "9988", "hottag": "热"}],
        )
        nethot = tianapi.normalize(
            "nethot",
            [{"keyword": "全网话题", "index": 8877, "trend": "新", "brief": "摘要"}],
        )
        self.assertEqual(weibo[0]["platform"], "微博")
        self.assertEqual(weibo[0]["hotness"], "9988")
        self.assertEqual(nethot[0]["brief"], "摘要")

    def test_partial_failure_remains_visible_in_output(self) -> None:
        results = {
            "douyin": [{
                "rank": 1,
                "title": "测试热点",
                "hotness": "100",
                "platform": "抖音",
                "tag": "",
            }]
        }
        output = tianapi.build_output(results, {"weibo": "timeout"}, "2026-08-22")
        self.assertEqual(output["meta"]["total_items"], 1)
        self.assertEqual(output["meta"]["failed_platforms"], ["weibo"])
        self.assertEqual(output["items"][0]["source_type"], "hotlist_api")
        self.assertIsNone(output["items"][0]["url"])
        self.assertEqual(output["failures"]["weibo"], "timeout")

    def test_blank_titles_are_discarded(self) -> None:
        self.assertEqual(
            tianapi.normalize("douyin", [{"word": " ", "hotindex": 1, "label": 0}]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
