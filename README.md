# Trend to Script CN / 热点到成稿

> v0.1.0 public beta

输入行业、发布平台、篇幅和内容目标，把实时热点或用户素材转成有来源、能长尾、经过自然化和发布前审核的平台文案。

它不是“万能爆款提示词”。它解决的是中文自媒体里容易断开的几步：热点证据、行业关联、短视频前三秒钩子、钩子兑现、去 AI 味和发布审核。

## 工作流

```mermaid
flowchart LR
    A["输入<br/>行业·平台·篇幅·目标"] --> B["来源预检"]
    B --> C["实时热榜 / 平台证据 / 网页核验"]
    C --> D["事实锁与热点长尾化"]
    D --> E["A-R-C-T-P-S 策略<br/>3个钩子候选·前三秒硬门槛"]
    E --> F["平台初稿与质量门"]
    F --> G["Humanizer-zh"]
    G --> H["事实·钩子·回报复查"]
    H --> I["yuwen-publish-precheck"]
    I --> J["最终稿与覆盖报告"]
```

## 主要能力

- 区分热榜 API、平台搜索、正文读取和普通网页证据，不把网页摘要冒充平台热度。
- 把短期热点转成“热点内核 → 常青张力 → 行业桥接 → 可复用回报”。
- 用 A-R-C-T-P-S 决策层选择钩子、冲突、信任材料和观众回报；抖音、视频号等短视频要求第一个口播字进入钩子，并通过自然朗读三秒检查。
- 调用外部 Humanizer-zh 自然化，再检查事实锁和钩子兑现是否被破坏。
- 调用外部玉文引擎完成词面、语义、修复和复审；零敏感词不等于审核通过。
- 数据源失败时返回明确的 `coverage_gap`，不伪造实时性。

## v0.1.0 支持边界

| 发布平台 | 文案适配 | 实时/平台证据入口 | 完整发布前审核 |
|---|---|---|---|
| 抖音 | 口播、标题、简介、标签 | 天聚数行（TianAPI）抖音热榜；网页背景核验 | 玉文支持 |
| 小红书 | 标题、正文、标签、封面短句 | Agent Reach；通常需要用户已有登录态 | 玉文支持 |
| 微博 | 短帖、话题、讨论引导 | 天聚数行（TianAPI）微博热榜 | 暂不支持，明确标记 |
| 微信视频号 | 口播、标题、简介、封面文案 | 用户材料、网页或其他已验证来源 | 玉文支持 |

B站、YouTube、V2EX、GitHub、RSS 等可以作为补充证据来源，但 v0.1.0 不宣称完整覆盖所有发布平台，也不保证推荐量或过审。

## 安装

### 必需条件

- 能加载 Agent Skills 的 Codex 或兼容宿主。
- Python 3.10+，用于来源检查、天聚数行（TianAPI）采集和仓库测试。

克隆后，把整个目录复制到宿主的 Skills 目录：

```powershell
git clone https://github.com/shanwen222/trend-to-script-cn.git
Copy-Item -Recurse -Force .\trend-to-script-cn "$env:USERPROFILE\.codex\skills\trend-to-script-cn"
```

```bash
git clone https://github.com/shanwen222/trend-to-script-cn.git
cp -R trend-to-script-cn ~/.codex/skills/trend-to-script-cn
```

重新打开任务后，可显式调用 `$trend-to-script-cn`。

### 外部能力

| 能力 | 是否必须 | 配置 | 缺失时 |
|---|---|---|---|
| 天聚数行（TianAPI） | 可选 | 设置 `TIANAPI_KEY` | 不生成抖音/微博实时榜单，改用已验证材料或常青选题 |
| Agent Reach | 可选 | 按上游安装；部分平台需要登录态 | 跳过对应平台内搜索并记录覆盖缺口 |
| Humanizer-zh | 可选；`naturalness=required` 时必须 | 安装外部 Skill | `auto` 交付未自然化草稿；`required` 停止正式稿 |
| yuwen-publish-precheck | 可选；`publish_precheck=required` 时必须 | 安装外部 Skill | `auto` 标记未完成正式审核；`required` 停止最终稿 |

外部项目与许可说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

### 天聚数行（TianAPI） API

本 Skill 可选使用天聚数行提供的实时热榜 API。使用者需自行注册并申请凭据。

官网：[天聚数行 API 平台](https://www.tianapi.com/)

本项目与天聚数行不存在赞助、背书或官方合作关系；使用时请遵守其服务条款、接口限额和数据使用规定。

```powershell
$env:TIANAPI_KEY="your_key_here"
python scripts/tianapi_hotsearch.py --check-config
```

真实 Key 只在运行时读取，不应写入仓库、截图、Issue 或测试数据。

### 无 API 的降级路径

没有 TianAPI Key 时仍可使用本 Skill：

1. 使用用户提供的素材、公开 URL 或可用的 Agent Reach 后端。
2. 有网页证据时只写“近期相关话题”，不声称进入平台热榜。
3. 没有可靠实时证据时改做常青选题。
4. 输出 `source_coverage`，明确哪些来源未覆盖。

## 使用

先检查当前能力：

```bash
python scripts/check_sources.py
```

示例请求：

```text
用 $trend-to-script-cn 为母婴行业生成 5 个抖音选题，每条约 3 分钟口播，
目标是知识解释和账号信任。显示本次实际数据源和发布前审核状态。
```

```text
用 $trend-to-script-cn 研究近 7 天 AI 教育话题，生成小红书图文。
naturalness=required，publish_precheck=required，strategy_mode=debug。
```

## 完整案例

[AI 学习 × 抖音完整案例](docs/examples/ai-learning-douyin.md) 展示了：

```text
输入
→ 当时的热榜证据
→ 长尾化
→ 三个钩子候选与前三秒淘汰测试
→ 模板化初稿问题
→ Humanizer 后稿件
→ 质量评分
→ 玉文审核与语义反例
```

案例是带抓取时间的历史快照，不作为当前实时榜单。

## 输出

每批结果至少包含：

- `source_coverage`：计划来源、成功来源、失败来源和覆盖缺口。
- 热点证据：来源类型、平台、抓取时间、排名/互动字段和 URL。
- 长尾记录：事实锁、热点内核、常青张力、行业桥接和回报。
- 内容策略：钩子候选、前三秒原文与朗读检查、选择理由、结构、信任材料和质量门。
- 平台版本：标题、正文、实际字符数、标签、简介和发布时间建议。
- 自然化状态：外部引擎是否执行、事实锁和钩子回报是否保留。
- 发布审核：平台、状态、问题、修复、复检和人工确认项。

详细字段见 [references/input-output.md](references/input-output.md)。

## 开发与测试

离线仓库校验：

```bash
python scripts/validate_repository.py
```

运行回归测试：

```bash
python -m unittest discover -s tests -v
```

测试包含：

- TianAPI 三种返回结构的归一化和部分失败保留。
- 母婴＋抖音、AI教育＋小红书、命理＋视频号三组行为契约。
- Skill 引用、版本、许可证、第三方声明和凭据泄漏检查。

GitHub Actions 会在 push 和 pull request 时运行相同检查。测试不要求模型生成固定措辞；真实成稿仍需定期做前向测试。

## 项目结构

```text
trend-to-script-cn/
├── .github/workflows/validate.yml
├── agents/openai.yaml
├── docs/examples/
├── references/
├── scripts/
├── tests/fixtures/
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── VERSION
├── README.md
└── SKILL.md
```

## 安全与第三方边界

- 默认只读，不发帖、评论、点赞或自动登录。
- 不保存或输出 API Key、Cookie、Token 和代理凭据。
- 不把搜索摘要、缓存网页或其他平台数据伪装成目标平台热榜。
- 不把心理机制描述成“必火”或确定性流量因果。
- 不把词面扫描零命中写成完整审核通过。

本项目原创部分使用 [MIT License](LICENSE)。Agent Reach、Humanizer-zh、yuwen-publish-precheck 和天聚数行（TianAPI）保留各自许可证、服务条款与数据限制。
