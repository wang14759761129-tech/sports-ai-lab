# PTTI v0.1.1：凯凯快速开始

先解压整个包，打开 `PTTI/PTTI.exe`。需要 Windows 10/11 x64 和 Edge WebView2 Runtime；运行不用 Python、Node、Git、VS Code 或 Codex。

点 **加载合成示例**：生成并保存一个 52 分的合成示例。点比赛卡片进入分析页。颜色区分两个球员，统计下方显示样本数；没有注释的指标会显示 Insufficient data，不会猜测。

点 **导入比赛**：填写比赛名称、Player A、Player B（支持中文），选 UTF-8 CSV，然后 **校验并保存**。errors 会阻止保存，warnings 会解释不完整的数据。`sample/synthetic.csv` 可以作为格式示例，真实数据不要沿用合成比分。

**逐分查看** 可以查每一分；**比赛库** 可以重开保存的比赛。关闭后再打开，检查比赛仍在。数据只在本机，位于 `%LOCALAPPDATA%\PTTI\matches.db`；备份前先关闭 PTTI。

比赛页 **导出 JSON** 保存完整结构化分析；**导出 HTML** 保存可独立浏览/打印的简洁报告。导出文件可能含你的比赛数据，只分享给你想分享的人。当前不支持重新导入 JSON；对方重新分析请使用 CSV。

若打不开或出错，请填 `docs/USER-FEEDBACK.md`，附完整错误截图、Windows 版本；存在 `startup-error.log` 时附错误文本。不要把整份私人比赛数据库当作错误报告发送。

## KAIKAI TEST 01（目前尚未通过）

- 收到完整压缩包并解压整个文件夹。
- 自己的 Windows 电脑能打开 PTTI，没有安装 Python 或 Node。
- 示例能打开，一个 CSV 能成功导入，分析页图表正常。
- 重启应用后比赛仍在；JSON 或 HTML 能保存并打开。

全部完成才算 PASS。任何失败都记录成 bug；测试通过前不开始 v0.2。

历史格式 player=A / opponent=B，比分是发球方/接发方视角的赛前比分；模板 sample/protocol-v0.3-example.csv 是合成例子。两种格式都自动检测；合成 CSV 勾选合成示例。未知/不清楚/不适用保留，证据不足不显示假 0%。研究 Pilot 2 未开始，软件计算不是研究结论。
