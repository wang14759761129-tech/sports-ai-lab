# Video Evidence v0.2 原生 Windows 验收

当前预览：

`C:\PTTI-VEAB-491ed7a\video-evidence-ai-bridge-491ed7ae4e\dist\PTTI-Video-Evidence-AI-Bridge-Preview\PTTI-Video-Evidence-AI-Bridge-Preview.exe`

建议仅使用临时 QA 数据库：

`C:\Users\wang\AppData\Local\Temp\PTTI-VEAB-QA-Retake-20261008\matches.db`

研究视频：Extended OpenTTGames TRAIN `game_3.mp4`，CC BY-NC-SA 4.0，仅研究/非商业使用。已核对 SHA256：

`e0f6a1ddbb838ac6acc67fb50f763728b589ec8f8cb7ababd9fa95f13c853e49`

本地冻结候选包：

`C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI-Dev\evidence\hit_v0_3_desktop_packages\game_3-v0.3-d.jsonl`

候选包 SHA256：`5ece775cd5ec63ad0c78be3754d173f20d6f5cce526fbfe6af492c17b6fe064b`。其 manifest 绑定到上面的 game_3 视频 SHA；导入结果应显示 267 条建议、741 条过滤记录。

请在 Windows 桌面上亲自操作原生预览窗口。浏览器中的同一页面不能替代下列验收。

## 人工验收步骤

1. 双击上面的 Preview EXE。确认窗口标题为 `PTTI · AI 证据复盘 Preview`，窗口能响应，且没有独立控制台窗口。
2. 在“视频证据”中首次导入本机 `game_3.mp4`。确认视频状态可用、时长约 618 秒，并通过界面或诊断脚本核对 SHA256。
3. 在原生窗口中播放、暂停、拖动进度条；如界面提供慢放，分别试用慢速和恢复正常速度。确认画面确实变化，时间位置与画面相符。
4. 导入与该视频 SHA256 绑定的 Hit Candidate JSONL 包。确认来源为 Extended OpenTTGames TRAIN、许可为 CC BY-NC-SA 4.0，并看到导入批次完成且错误为 0。
5. 点选至少两条不同时间的候选。每次确认视频画面实际跳到候选附近；只看时间数字变化不算通过。记录可观察到的误差范围。
6. 修改一条候选的人工时间并保存；随后确认另一条候选，再否决第三条。确认原始 AI 时间仍可查看、人工时间单独保留，UNKNOWN 没有自动变成 Near/Far。
7. 对同一视频和同一候选包再导入一次。确认没有重复生成建议；已否决项仍只在否决状态中。
8. 打开过滤记录，确认 741 条记录可审计且没有进入已确认列表。
9. 手工创建一个逐分/关键分片段，添加到“关键分复盘”合集；至少加入两个片段并从合集连续播放。确认每个片段边界能停止在所设结束点之后约 0.5 秒。
10. 正常退出并重新打开 Preview。确认视频、导入批次、候选复核状态、逐分和合集均保留。
11. 关闭程序后，将**测试副本**视频移动到另一目录，再通过界面重新关联。确认 SHA256 相同后恢复可用；不要移动或删除唯一原件。移动后的路径可用诊断脚本再次校验。

## 诊断脚本

需要 PowerShell 7（`pwsh`）。从产品目录运行以下只读检查。将 `-CandidatePackagePath` 替换成上一步实际选择的 JSONL 文件路径；如果暂时没有候选包，可省略该参数。

```powershell
$video = 'C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI-Dev\research-datasets\ExtendedOpenTTGames\videos\train\game_3.mp4'
$package = 'C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI-Dev\evidence\hit_v0_3_desktop_packages\game_3-v0.3-d.jsonl'
pwsh -NoProfile -File .\scripts\qa_video_evidence_v02_native.ps1 `
  -ExpectedExePath 'C:\PTTI-VEAB-491ed7a\video-evidence-ai-bridge-491ed7ae4e\dist\PTTI-Video-Evidence-AI-Bridge-Preview\PTTI-Video-Evidence-AI-Bridge-Preview.exe' `
  -ExpectedDatabasePath "$env:TEMP\PTTI-VEAB-QA-Retake-20261008\matches.db" `
  -VideoPath $video `
  -ExpectedVideoSha256 'e0f6a1ddbb838ac6acc67fb50f763728b589ec8f8cb7ababd9fa95f13c853e49' `
  -CandidatePackagePath $package
```

脚本仅检查指定预览进程、窗口响应、版本提交、TEST 数据库路径、生产库未访问状态、视频 SHA256，以及候选包首行中的来源视频 SHA256；不会写数据库或改动视频。它不能替代人工确认播放画面、跳转精度、慢放、原生文件选择器和重启后的实际 UI 状态。

## 结果记录

逐项填写 `通过 / 失败 / 待人工`，并记录实际视频 SHA、候选包 SHA、候选时间、画面定位误差、复核点击数及操作耗时。真人耗时只能由实际人工计时得出；自动化测试结果不能推算成节省的复盘时间。

效率测试固定选取该包中前 10 条建议，按相同顺序完成定位、确认/否决、给其中一条添加“关键分”标签、加入合集，然后从合集重新找到并播放该片段。分别记录：

| 指标 | 自动化 | 真人原生窗口 |
|---|---:|---:|
| 10 条候选总点击数 | 未测 | 待实测 |
| 候选点击至正确画面延迟（中位数 / 最大值） | 未测 | 待实测 |
| 单条确认/否决所需操作数 | 未测 | 待实测 |
| 添加标签及收藏所需操作数 | 未测 | 待实测 |
| 从合集找回并播放耗时 | 未测 | 待实测 |

本轮未完成真人原生窗口计时，不报告复盘时间节省比例。
