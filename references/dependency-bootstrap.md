# 强制依赖与启动引导

本 Skill 的正式交付依赖三个外部 Skill：Agent Reach、Humanizer-zh 和 yuwen-publish-precheck。它们不是可有可无的推荐项，而是质量流程的一部分：分别负责数据获取、中文自然化和发布前审核。

## 首次使用

正常调用本 Skill 时，先运行：

```bash
python scripts/bootstrap_dependencies.py --ensure --json
```

引导脚本只把上游 Skill 安装到宿主的 Skill 目录，不把它们复制进本仓库。默认优先使用 `CODEX_HOME/skills`，没有设置时使用用户目录下的 `.codex/skills`；也会识别已有的 `.agents/skills` 和 `.claude/skills` 安装。

脚本会从 [dependencies.json](dependencies.json) 指定的上游提交安装，避免本地和 GitHub 版本各自漂移。首次安装 Agent Reach 的命令行组件使用用户级 Python 安装，不写入本仓库，也不会读取或输出 API Key、Cookie 或 Token。

如果宿主还缺少 Agent Reach 的系统级工具，脚本会报告缺口；只有用户明确允许后，才可以继续运行上游的 `agent-reach install --env=auto --system`。缺口未解决时不得生成正式稿。

## 质量闸门

引导结果必须同时满足：

1. 三个 Skill 的必需文件都存在；
2. Agent Reach 命令可执行；
3. 能在当前宿主读取三个上游 `SKILL.md`。

任一条件不满足，状态为 `blocked_by_dependencies`，本次只返回安装失败原因和下一步，不返回“可发布”文案。依赖安装成功后，当前任务应立即读取三个上游 `SKILL.md`；如果宿主要到下一轮才刷新 Skill 列表，也必须先暂停正式交付。

## 维护规则

`dependencies.json` 是唯一的依赖版本入口。更新外部组件时，只修改该清单中的提交号，运行仓库测试，再同时提交主仓库；不要在主仓库复制、二次修改或另存外部 Skill。这样本地工作目录和 GitHub 仓库始终使用同一套启动流程。
