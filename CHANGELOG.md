# Changelog

## Unreleased

- 增加统一的仓库发布安全扫描器，覆盖工作区、推送范围、可达历史、照片/媒体、二进制、个人信息、凭据、Cookie、私有路径和超大文件。
- 增加安全的本地 `pre-push` Hook 安装脚本：默认不覆盖未知 Hook，`--force` 才允许覆盖。
- GitHub Actions 改为拉取完整历史，并在仓库校验和测试前运行同一份历史扫描器。
