# 输入与输出契约

## 请求参数

```json
{
  "industry": "母婴",
  "platforms": ["抖音", "小红书"],
  "word_count": {"min": 500, "max": 650},
  "content_goal": "热点借势+情绪共鸣",
  "tone": "自然口播",
  "strategy_mode": "standard",
  "strategy_strength": "balanced",
  "naturalness": "auto",
  "publish_precheck": "auto",
  "commercial": "unknown",
  "count": 5,
  "freshness": "today",
  "long_tail": true
}
```

`platforms`是输出平台，不自动等于来源平台。`word_count`可写整数或`min/max`区间；未指定时根据平台和内容类型选择合理范围并标注假设。`strategy_mode=debug`输出内部决策和评分，`off`跳过策略层。`naturalness=auto`在引擎可用时调用外接 Humanizer，`required`在引擎缺失时停止正式稿交付，`off`明确跳过；任何模式都不能修改事实和风险限定。`publish_precheck=auto`时对审核引擎支持的平台自动执行完整审核；`required`时缺少引擎或平台不受支持就不交付最终稿；`off`只在用户明确要求时跳过。`commercial`未知时不得擅自判成非商业。

## 来源记录

每条证据使用统一字段：

```json
{
  "source_type": "hotlist_api",
  "provider": "天行数据",
  "platform": "微博",
  "query": null,
  "title": "原始标题",
  "rank": 19,
  "hotness": "302671",
  "engagement": null,
  "url": null,
  "fetched_at": "YYYY-MM-DD HH:mm:ss+08:00",
  "freshness": "request_time",
  "evidence_strength": "strong"
}
```

不存在的字段使用`null`，不从标题猜测排名、热度、互动量或发布时间。

## 结果结构

```json
{
  "meta": {
    "date": "YYYY-MM-DD",
    "industry": "母婴",
    "platforms": ["抖音", "小红书"],
    "assumptions": []
  },
  "source_coverage": {
    "planned": ["tianapi:douyin", "agent-reach:xiaohongshu", "exa:web"],
    "succeeded": ["tianapi:douyin", "exa:web"],
    "failed": [{"source": "agent-reach:xiaohongshu", "reason": "browser extension not connected"}],
    "coverage_gaps": ["未取得小红书平台内结果"],
    "freshness_notes": []
  },
  "hot_topics": [],
  "selected_topics": [
    {
      "title": "选题标题",
      "evidence": [],
      "angle": "热点内核如何转成行业内容",
      "long_tail_treatment": "如何保留事实边界并降低强时效性",
      "content_strategy": {
        "content_type": "科普",
        "audience_tension": "目标观众的具体处境或冲突",
        "viewer_return": "看完获得的判断、方法或解释",
        "mechanisms": [
          {"name": "Attention", "purpose": "为何选它", "support": "由哪段真实材料支撑"}
        ],
        "hook_candidates": [],
        "chosen_hook": "",
        "structure": "",
        "trust_material": [],
        "payoff": "",
        "social_value": "",
        "long_tail": {
          "fact_lock": [],
          "trend_core": "",
          "evergreen_tension": "",
          "industry_bridge": "",
          "evergreen_payoff": "",
          "expiry_note": "",
          "long_tail_pass": true
        }
      },
      "common": {
        "body": "通用核心文案",
        "char_count": 600,
        "hook": "信息缺口"
      },
      "platform_versions": {
        "抖音": {
          "title": "视频标题",
          "body": "口播正文",
          "char_count": 600,
          "first_3s_hook": {
            "text": "前三秒口播原文",
            "mechanism": "认知冲突",
            "cold_audience_clear": true,
            "read_aloud_seconds": 2.8,
            "payoff_location": "正文第3段",
            "passed": true
          },
          "tags": ["话题1", "话题2"],
          "description": "视频简介",
          "publish_time": "21:00-22:00",
          "naturalness_review": {
            "mode": "auto",
            "engine": "humanizer-zh",
            "status": "applied",
            "changes": [],
            "remaining_risks": [],
            "fact_lock_preserved": true,
            "hook_payoff_preserved": true
          },
          "quality_review": {
            "scores": {
              "Hook": 0,
              "Relevance": 0,
              "Tension": 0,
              "Trust": 0,
              "Payoff": 0,
              "Naturalness": 0,
              "Shareability": 0,
              "Integrity": 0
            },
            "average": 0,
            "passed": false,
            "rewrite_reasons": []
          }
        }
      },
      "publish_precheck": {
        "engine": "yuwen-publish-precheck",
        "engine_source": "https://github.com/yuwen-cool/yuwen-publish-precheck",
        "platform": "抖音",
        "status": "passed_after_changes",
        "scope": ["标题", "口播正文", "简介", "标签"],
        "commercial": false,
        "issues": [
          {
            "location": "口播正文第2段",
            "quote": "原文片段",
            "rule_id": "原引擎返回的规则编号",
            "severity": "必改",
            "replacement": "替换文字"
          }
        ],
        "repair_applied": true,
        "recheck_passed": true,
        "checklist": [],
        "boundary": "使用审核引擎返回的边界声明"
      }
    }
  ]
}
```

平台版本可以比通用核心更口语、更短或更适合图文，但不得改变核心事实和来源平台。`strategy_mode=debug`时保留候选钩子、机制、长尾记录、评分和改写理由。审核引擎修复后的版本覆盖审核前候选稿；修复后不得再进行未经复检的文案改写。
