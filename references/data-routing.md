# 数据路由与降级

## 来源类型

| `source_type` | 含义 | 可支持的表述 |
|---|---|---|
| `hotlist_api` | 带平台、排名或热度字段的热榜接口 | “进入某平台热榜”“排名第 N” |
| `platform_search` | 平台内关键词搜索、推荐流或账号内容 | “在某平台检索到”“相关内容有互动” |
| `platform_detail` | 指定作品、正文、评论或互动详情 | “该作品显示……” |
| `web_search` | 通用网页搜索结果 | “近期相关报道/页面显示……” |
| `page_read` | 已知 URL 的网页正文读取 | “该页面正文提到……” |

网页搜索、页面缓存和搜索摘要都不能升级为平台热榜证据。

## 平台入口

| 数据目标 | 首选入口 | 补充入口 | 关键限制 |
|---|---|---|---|
| 抖音热榜 | 天行 `douyinhot` | Exa/Jina查背景 | Agent Reach 当前不提供抖音热榜；网页结果不能补排名 |
| 微博热榜 | 天行 `weibohot` | Exa/Jina查事件正文 | 网页读取不等于微博原生搜索 |
| 全网热榜 | 天行 `nethot` | Exa搜索、Jina读正文 | 标注网页发布日期和可能缓存 |
| 小红书 | Agent Reach；先查 `xiaohongshu.active_backend` | OpenCLI / xiaohongshu-mcp | 需用户已有登录态；先搜索取得完整URL/xsec_token，再读详情；控制频率 |
| B站 | Agent Reach `bili-cli` | OpenCLI字幕、B站搜索API | 不用yt-dlp读B站；Windows乱码时按GB18030解码CLI字节输出 |
| YouTube | Agent Reach `yt-dlp` | OpenCLI字幕、显式授权的转录 | `doctor`可用不代表目标视频一定有字幕 |
| V2EX | Agent Reach公开API | 无 | 请求时数据，无需登录 |
| GitHub | Agent Reach `gh` | Exa查官方文档 | 搜索和仓库事实优先GitHub原始数据 |
| RSS | Agent Reach `feedparser` | Jina读正文 | 新鲜度受源站更新时间影响 |
| 普通网页 | Exa搜索 | Jina读取已知URL | Jina可能返回缓存快照，记录提示 |

目标发布平台和来源平台可以不同。例如微博热榜可以转成抖音口播，但必须写明“来源：微博热榜”，不能写成“抖音正在热议”。

## Agent Reach验收

1. 多后端或登录态平台先运行 `agent-reach doctor --json`。
2. `active_backend`有值时使用该后端；为`null`时只在任务确实需要该平台时做一次只读验证。
3. 成功标准是返回与查询相关的非空内容，不是命令存在、退出码为0或Doctor发现了配置。
4. 不把登录Cookie、Token、代理地址或完整环境变量写入输出。
5. 平台失败最多按Agent Reach对应reference的既定重试链处理；链路耗尽后记录失败，不无限重试。

## 降级链

按序尝试，成功即停：

1. 目标平台的热榜或平台内入口。
2. 同一主题的另一已验证平台入口，用作交叉证据。
3. Exa搜索官方、媒体或行业页面，再用Jina读取正文。
4. 仍无可靠证据时放弃“实时热点”表述，改为常青选题或明确报告覆盖不足。

## 证据强度

- `strong`：请求时热榜API，或平台原生结果且有可核验排名/互动字段。
- `medium`：平台正文、评论或可信页面正文，可核验URL和时间。
- `weak`：搜索摘要、缓存页或缺少时间/互动字段的结果。

选题筛选可以使用弱证据发现线索，但最终事实主张应尽量由中强证据支撑。
