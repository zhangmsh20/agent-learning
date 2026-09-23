# 发布检查清单

- [ ] `python -m unittest discover -s 实操 -p 'test_*.py' -v` 通过。
- [ ] `python -m compileall -q 实操` 通过。
- [ ] `git diff --check` 通过，未包含 `.env`、API key、真实数据或生产日志。
- [ ] README 的安装命令在 Python 3.11+ 可执行。
- [ ] 每个新增平台事实都有校准日期和官方来源。
- [ ] GitHub Actions 对 push 和 pull request 均运行离线测试。
- [ ] 发布说明写清楚教材版本、破坏性变化和已知限制。
- [ ] Knowabit Project 页链接到固定仓库和 Release，不把 raw 文件作为唯一内容源。

## 状态语言

本地测试通过 ≠ 已提交；已提交 ≠ GitHub Actions 成功；Actions 成功 ≠ Knowabit 线上部署完成。
