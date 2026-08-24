#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch and normalize TianAPI hot-search data for the trend-to-script-cn skill.

The API key is intentionally supplied at runtime through TIANAPI_KEY or --api-key.
It is never written to the output JSON or printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://apis.tianapi.com"
ENDPOINTS = {
    "douyin": ("抖音", f"{API_BASE}/douyinhot/index"),
    "weibo": ("微博", f"{API_BASE}/weibohot/index"),
    "nethot": ("全网", f"{API_BASE}/nethot/index"),
}
DOUYIN_LABELS = {"0": "", "1": "热", "3": "荐", "17": "新"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="采集并归一化天行数据热搜")
    parser.add_argument("--api-key", help="天行数据 API Key；优先使用 TIANAPI_KEY 环境变量")
    parser.add_argument("--num", type=int, default=30, help="每个平台条数，范围 1-50")
    parser.add_argument("--interval", type=float, default=3.0, help="请求间隔秒数，默认 3 秒")
    parser.add_argument("--timeout", type=float, default=15.0, help="单次请求超时秒数")
    parser.add_argument("--output", help="输出 JSON 路径；默认 output/热搜_YYYY-MM-DD.json")
    parser.add_argument("--check-config", action="store_true", help="只检查 Key 是否可用，不请求接口")
    return parser.parse_args()


def get_api_key(cli_key: str | None) -> str:
    key = os.environ.get("TIANAPI_KEY", "").strip() or (cli_key or "").strip()
    if not key:
        raise RuntimeError("缺少天行数据 API Key：请设置 TIANAPI_KEY，或传入 --api-key。")
    return key


def request_json(url: str, api_key: str, num: int, timeout: float) -> dict[str, Any]:
    query = urlencode({"key": api_key, "num": num})
    request = Request(f"{url}?{query}", headers={"User-Agent": "trend-to-script-cn/0.1"})
    with urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if data.get("code") != 200:
        raise RuntimeError(f"API 返回错误 code={data.get('code')} msg={data.get('msg', '')}")
    return data


def number_text(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{int(value):,}"
    return str(value or "")


def normalize(platform: str, raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    label, _ = ENDPOINTS[platform]
    items: list[dict[str, Any]] = []
    for rank, item in enumerate(raw_items, start=1):
        if platform == "douyin":
            title = str(item.get("word", "")).strip()
            hotness = number_text(item.get("hotindex"))
            tag = DOUYIN_LABELS.get(str(item.get("label", "")), str(item.get("label", "")))
            extra = {}
        elif platform == "weibo":
            title = str(item.get("hotword", "")).strip()
            hotness = str(item.get("hotwordnum", "")).strip()
            tag = str(item.get("hottag", "")).strip()
            extra = {}
        else:
            title = str(item.get("keyword", "")).strip()
            hotness = number_text(item.get("index"))
            tag = str(item.get("trend", "")).strip()
            brief = str(item.get("brief", "")).strip()
            extra = {"brief": brief} if brief else {}
        if title:
            items.append({
                "rank": rank,
                "title": title,
                "hotness": hotness,
                "platform": label,
                "tag": tag,
                **extra,
            })
    return items


def fetch_all(api_key: str, num: int, interval: float, timeout: float) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    results: dict[str, list[dict[str, Any]]] = {}
    failures: dict[str, str] = {}
    for index, (platform, (_label, endpoint)) in enumerate(ENDPOINTS.items()):
        if index:
            time.sleep(max(interval, 0))
        try:
            data = request_json(endpoint, api_key, num, timeout)
            raw_items = data.get("result", {}).get("list", []) or []
            results[platform] = normalize(platform, raw_items[:num])
        except Exception as exc:  # keep partial results from other platforms
            failures[platform] = str(exc)
    return results, failures


def build_output(results: dict[str, list[dict[str, Any]]], failures: dict[str, str], today: str) -> dict[str, Any]:
    fetched_at = datetime.now().astimezone().isoformat(timespec="seconds")
    items = []
    for platform in ENDPOINTS:
        for item in results.get(platform, []):
            items.append({
                "source_type": "hotlist_api",
                "provider": "天行数据",
                "query": None,
                **item,
                "engagement": None,
                "url": None,
                "fetched_at": fetched_at,
                "freshness": "request_time",
                "evidence_strength": "strong",
            })
    summary = {}
    for platform, (label, _endpoint) in ENDPOINTS.items():
        platform_items = results.get(platform, [])
        summary[label] = {
            "count": len(platform_items),
            "top3": [item["title"] for item in platform_items[:3]],
        }
    return {
        "meta": {
            "date": today,
            "generated_at": fetched_at,
            "source": "天行数据 API",
            "platforms": [label for label, _endpoint in ENDPOINTS.values()],
            "total_items": len(items),
            "failed_platforms": list(failures),
        },
        "summary": summary,
        "items": items,
        "failures": failures,
    }


def main() -> int:
    args = parse_args()
    if not 1 <= args.num <= 50:
        print("--num 必须在 1-50 之间。", file=sys.stderr)
        return 2
    try:
        api_key = get_api_key(args.api_key)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.check_config:
        print("TIANAPI_KEY 已配置（值已隐藏）。")
        return 0

    today = datetime.now().strftime("%Y-%m-%d")
    output_path = Path(args.output or f"output/热搜_{today}.json")
    results, failures = fetch_all(api_key, args.num, args.interval, args.timeout)
    data = build_output(results, failures, today)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存：{output_path}")
    print(f"成功平台：{len(results)}，失败平台：{len(failures)}，条数：{data['meta']['total_items']}")
    if not results:
        for platform, error in failures.items():
            print(f"{platform}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
