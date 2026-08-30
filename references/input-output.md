# 输入与输出契约

## 请求参数

```json
{
  "industry": "母婴",
  "platforms": ["抖音", "小红书"],
  "word_count": {"min": 500, "max": 650},
  "duration": "约 2 分钟",
  "content_goal": "热点借势+情绪共鸣",
  "tone": "自然口播",
  "audience": "学龄儿童家长",
  "persona": "亲子内容创作者",
  "strategy_mode": "standard",
  "strategy_strength": "balanced",
  "naturalness": "required",
  "publish_precheck": "required",
  "commercial": "unknown",
  "count": 5,
  "freshness": "today",
  "long_tail": true
}
```

`word_count`可以用整数、区间或视频时长换算；例如“约 2 分钟口播”应转换为合理字数区间，并在输出中报告实际字数。`audience`和`persona`是提高命中率的推荐字段，缺失时可以采用最小假设。母婴内容建议说明孕期、0—3 岁、学龄前或学龄儿童等年龄段。

`platforms`是输出平台，不自动等于来源平台。`word_count`可写整数或`min/max`区间；未指定时根据平台和内容类型选择合理范围并标注假设。`strategy_mode=debug`输出内部决策和评分，`off`跳过策略层。`naturalness=required`和`publish_precheck=required`是本 Skill 的固定质量闸门；旧请求中的 `auto` 只作为兼容别名，实际仍按 `required` 执行，`off`请求被拒绝。任何模式都不能修改事实和风险限定。`commercial`未知时不得擅自判成非商业。

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
          "title": "视频标题（兼容字段）",
          "video_title": "视频标题",
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
          "cover": {
            "main_title": "封面主标题",
            "subtitle": "封面副标题"
          },
          "video_title_suggestions": ["视频标题候选1", "视频标题候选2", "视频标题候选3"],
          "recommended_video_title": "视频标题候选1",
          "tags": ["话题1", "话题2"],
          "description": "视频简介（兼容字段）",
          "video_description": "视频简介",
          "topic_title_suggestions": ["#话题标题1", "#话题标题2", "#话题标题3"],
          "recommended_topic_title": "#话题标题1",
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
        "scope": ["封面主标题", "封面副标题", "视频标题", "口播正文", "视频简介", "话题标题", "标签"],
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

`title` 和 `description` 是旧版兼容字段，分别等同于 `video_title` 和 `video_description`；新结果优先使用语义明确的字段。`video_title_suggestions` 和 `topic_title_suggestions` 是候选集合，必须从中标出一个推荐项或说明选择逻辑。封面主标题负责一眼看懂主题，副标题补充具体回报，不把完整口播塞进封面。话题标题是可搜索/可参与的话题词，不等同于随意堆砌的标签。

平台版本可以比通用核心更口语、更短或更适合图文，但不得改变核心事实和来源平台。`strategy_mode=debug`时保留候选钩子、机制、长尾记录、评分和改写理由。审核引擎修复后的版本覆盖审核前候选稿；修复后不得再进行未经复检的文案改写。
