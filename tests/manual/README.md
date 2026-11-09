# manual/ — 早期 GUI 冒烟脚本（历史存档）

这里的 4 个脚本是 2026-08 开发初期的一次性界面验证脚本，
文件名含义：`A/B/C/D` 是场景编号，`qs/noqs` 表示是否清除 QSettings 界面记忆，
`2102/971` 是当时的字体参数。

**不要把它们当测试用。** 当前自动化验证已由 `tests/` 下的 pytest 套件承担：

```
D:/DevTools/Python3.10/python -m pytest tests/ -q
```

这些脚本依赖旧的字体/缩放实现（早于 `ui/theme.py` 的 QSS 缩放体系），
保留仅作历史参考，运行结果不代表当前行为。
