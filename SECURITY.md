# Security

本项目是公开仓库。任何准备提交或推送的改动，都必须先运行仓库唯一的发布安全扫描器：

```bash
python scripts/check_sensitive.py --pre-push --json
```

扫描器覆盖工作区、未被忽略的未跟踪文件、推送范围和可达 Git 历史，重点检查个人照片与媒体、历史资料、个人信息、密钥、Cookie、私有路径、嵌入式图片、二进制文件和超大文件。命中时只报告 `source`、`path`、`rule`、`commit`，不回显敏感原文，并返回失败状态。

维护者首次在本地克隆中安装推送前 Hook：

```bash
python scripts/install_pre_push_hook.py
```

未知已有 Hook 默认不覆盖；确认需要替换时才显式使用 `--force`。不要使用 `git push --no-verify` 绕过本地闸门，也不要使用 `git add .` 或 `git add -A`。

如果怀疑内容已经进入远端，请先停止继续推送，保留现状并报告文件路径、提交号和规则名称；不要自行重写历史或撤回远端内容。凭据疑似暴露时，应通过对应服务的官方入口轮换或吊销，并保留审计时间线。
