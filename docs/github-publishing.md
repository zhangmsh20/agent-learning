# GitHub 发布步骤（需要本人确认后执行）

当前目录已经是一个本地 Git 仓库，默认分支为 `main`，最近提交为课程仓库 v0.1.0。远程仓库尚未创建，也没有执行 push。

## 建议的公开仓库名

```text
zhangmsh20/agent-learning
```

## 使用 GitHub CLI 发布

确认要公开课程后，在本目录执行：

```bash
gh auth status
gh repo create zhangmsh20/agent-learning --public --source=. --remote=origin --push
```

发布后验证：

```bash
git remote -v
gh run list --limit 5
gh release create v0.1.0 --title "Agent Learning v0.1.0" --notes-file CHANGELOG.md
```

## 发布后要回填 Knowabit

只有仓库 URL、默认分支和 GitHub Actions 首次运行都验证成功后，才把固定链接加入 `/projects/agent-learning`：

```text
https://github.com/zhangmsh20/agent-learning
https://github.com/zhangmsh20/agent-learning/releases/tag/v0.1.0
```

这样可以避免网站出现无法验证的占位链接。GitHub 仓库负责教材、实例、测试和 Release；Knowabit 页面只负责介绍和入口。
