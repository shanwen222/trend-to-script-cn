# Contributing

本项目只维护这一份 Skill 源码。请不要创建第二个仓库、备用扫描器或旁路发布入口，也不要把其他项目的照片、身份素材、历史资料、输出目录或私有资产复制进来。

## 提交前流程

先运行发布安全扫描：

```bash
python scripts/check_sensitive.py --pre-push --json
```

然后只暂存本次明确修改的路径，禁止批量暂存：

```bash
git add path/to/changed-file
git diff --cached --check
python scripts/validate_repository.py
python -m unittest discover -s tests -v
git push origin main
```

首次使用本地克隆时安装 Hook：

```bash
python scripts/install_pre_push_hook.py
```

安装脚本默认不覆盖未知的 `.git/hooks/pre-push`；只有确认旧 Hook 可以被替换时才使用 `--force`。GitHub Actions 会用仓库内同一份扫描器检查完整历史。

## 改动边界

- 不改变本项目自身的业务流程、视觉规则或内容规则，除非任务明确要求。
- 不修改其他项目，包括封面 Skill 项目。
- 不删除或重写历史，不自动撤回远端内容。
- 凭据、Cookie、个人资料和私有资产只在本地运行时使用，不写入源码、测试、截图、Issue 或发布产物。
