# Video Evidence 本机桌面验收

当前自动化环境不能控制原生 Windows 窗口。下面的步骤用于人工验收源码 Preview；数据库放在系统临时目录，不使用正式库。

在仓库根目录打开 PowerShell：

```powershell
Set-Location .\products\ptti
$qaRoot = Join-Path $env:TEMP 'PTTI-VideoEvidenceReview-QA'
New-Item -ItemType Directory -Force -Path $qaRoot | Out-Null
$env:PTTI_ENV = 'development'
$env:PTTI_DB = Join-Path $qaRoot 'matches.db'
$env:PTTI_EVIDENCE_PREVIEW = '1'
$env:PTTI_AI_EVIDENCE_BRIDGE = '1'
.\.venv\Scripts\python.exe .\apps\desktop.py
```

在打开的 PTTI 窗口里：

1. 进入“视频复盘”，登记一段你有权使用的本地 MP4，确认视频可以播放、暂停、拖动和慢放。
2. 如果有与该视频 SHA256 完全匹配的 TRAIN 冻结 JSONL 结果包，导入后选择“待复核”或“只看异常”。没有匹配结果包时，不要用其他视频的包代替；可以继续检查人工标记流程。
3. 点击一个候选，确认播放头跳到显示的时间；播放前后 0.5 秒，并核对实际画面。时间说明若不是源 PTS，应显示估算或来源未知。
4. 对候选分别做一次人工确认、否决、修改时间/击球方；UNKNOWN 保持 UNKNOWN。检查复核后是否自动聚焦下一条。
5. 用 J/K 切换候选；在文本输入框中按 A/R 时应只输入文字，不应触发复核快捷键。
6. 关闭并重新启动，检查本地复核位置、修正状态和审计历史；分别下载 JSON、CSV、中文 HTML 并确认过滤记录仍标为“算法已过滤”。
7. 检查数据库文件只位于 `%TEMP%\PTTI-VideoEvidenceReview-QA\matches.db`。

请记录实际通过/失败项及视频定位误差。完成这些人工点击前，验收门仍为 `MANUAL_GUI_CHECK_REQUIRED`。
