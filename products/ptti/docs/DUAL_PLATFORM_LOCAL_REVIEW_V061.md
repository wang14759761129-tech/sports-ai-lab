# PTTI v0.6.1 双平台与本地复盘验收记录

日期：2026-10-10

分支：`feature/ptti-dual-platform-local-review-v0.6.1`

代码基线：`0bc84b06b24e019761c46207e4c71ae16db07cb6`
状态：`DUAL_SOURCE_PRODUCT_PARTIAL`

## Before / After / User Value

**Before：** 首页来源卡片以平台链接线索为主；同一场比赛与不同在线视频版本、本地录像的关系及各自许可/时间轴状态不够清楚。

**After：** 运动员可从三列来源流选择本地录像或在线来源。在线来源先显示来源页或获准的官方嵌入；未确认嵌入权限时提供官方页面入口。比赛详情分开展示在线来源和本地录像，并允许用户明确确认来源与比赛、确认本地录像与比赛的关联。每个在线视频和本地文件使用独立时间轴。固定比分按钮复用现有 ScoreMoment；没有已确认索引时保持“尚未索引”。Vision 在无可信轨迹时禁用。

**User value：** 在已测试流程中，用户可以从比赛来源进入实际观看页面；本地研究视频已在 PTTI 原生源码 QA 窗口播放。未知权限不会触发内嵌播放器，在线秒数不会填入本地 ScoreMoment，也不会启用在线 Vision。

## Evidence

| 项目 | 本轮结果 | 证据与边界 |
|---|---|---|
| YouTube 官方页面播放 | 1 个样本实际播放 | `H77vNFk3neg` 在浏览器会话中从 0.02s 播至 122.75s，页面显示时长约 1704.72s。只验证了本次会话中的页面播放；未审看全片，也未验证 PTTI 内嵌播放权限。PTTI 提供官方页面入口。 |
| PTTI 内嵌 YouTube | 0 | 当前来源的嵌入许可没有经过验证，因此产品保持官方页面播放路线。 |
| Bilibili 页面播放 | 1 个受限样本 | `BV1nb421H7jB` 在浏览器页面观察到画面和时间推进（0.47s、124.80s）；同时页面显示登录/试看提示，未确认不受限观看权、完整性或转载权。另一 Bilibili 样本 `BV1Hm4y1g7My` 未能播放。没有绕过登录、试看或平台限制。 |
| PTTI 内嵌 Bilibili | 0 | 嵌入权限仍是 UNKNOWN；产品提供官方页面链接。 |
| 本地研究录像播放 | 1 | `Extended OpenTTGames game_1` 在 PTTI 原生源码 QA 窗口实际播放，时间由 0s 推进至约 98.53s；窗口画面显示球台和运动员。媒体未复制到仓库或预览包。 |
| 同一比赛的真实 B 站 + YouTube + 本地录像关联 | 0 | 没有证据证明本轮样本属于同一场比赛，因此未做真实三来源绑定。隔离 API 测试验证了两种平台来源可以绑定同一个测试 Match ID、保留独立 timeline ID，且重启后保留。该结果是工程合同测试，不是比赛身份事实。 |
| 已确认比分定位 | 0 | 原生播放器五个入口 `0:0`、`3:3`、`5:5`、`9:9`、`10:10+` 均显示“尚未索引”。原生点击 `9:9` 后明确提示没有已确认的一分，没有跳到猜测时间。 |
| 在线来源的 Vision 分析 | 0 | 在线分析许可为 DENIED。 |
| 本地可信 Vision 轨迹 | 0 | `game_1` 当前没有可用的已核验轨迹，Vision 按设计保持禁用。 |

浏览器页面的播放器时间推进是页面级观察。其结果不代表整个比赛可以无限制观看、视频是完整比赛、平台授权了嵌入/下载/分析，或所有 Windows 机器都能使用相同会话。

## Data and licensing boundaries

- 新来源只保存公开页面来源信息和人工确认的 Match 关联；链接不授予许可。
- Bilibili 样本明确保留发布者限制提示；未下载、缓存、截取或重新分发视频。
- YouTube 与 Bilibili 的页面时间轴各自独立；跨来源时间映射为 `NOT_VERIFIED`。
- 本地关联要求可用文件、已验证 SHA256、用户明确确认；不根据文件名自动匹配。
- 在线数据不能作为本地分析资产；在线 ScoreMoment/Vision 均不可用。
- QA 写入使用临时 TEST 数据库；未访问 Production DB、官方 TEST、GAME_5，也未运行模型或改动冻结算法。

## Verification and delivery

- Python 定向测试：27 passed；包含来源映射、重复请求和后端重启持久化合同。出现 1 条 Starlette/httpx 弃用提示。
- 前端测试：`test:feed` 14 passed；`test:review` 9 passed；`test:score` 5 passed；`test:score-observation` 12 passed。合计 40 passed。
- `pip check`：通过；后端两模块 `py_compile`：通过；`git diff --check`：通过（有一条现有 LF/CRLF 提示）。
- Python 全量测试未执行：本轮可用物理内存低于 2 GiB 安全线。Windows EXE 未构建，未生成新 Preview 或 SHA256。
- 原生检查使用源码 QA，不是新 EXE；QA 数据库位于系统临时目录，不随项目提交。浏览器页面播放、原生本地播放及嵌入授权是不同验收项。

## Limitations and next gate

当前不能宣称 Bilibili 或 YouTube 已在 PTTI 内完成获准嵌入播放，也不能宣称样本是已验证完整比赛。真实同场多来源与本地绑定、真实 ScoreMoment 跳转、Vision 轨迹仍未验证。因此保持 `DUAL_SOURCE_PRODUCT_PARTIAL` 与 `SCORE_NAVIGATION_V0_1_PARTIAL`；只有浏览器/源码 QA 和隔离测试证据，不升级 Windows Preview Gate。下一步最有价值的是在内存安全线恢复后构建独立 Preview，再由人工核实一场真实比赛的跨来源身份后完成本地录像关联。

## 2026-10-10 补充验收

- 本轮后端定向回归：`test_match_video_library.py` **17 passed**，1 条现有 Starlette/httpx 弃用提示；夹具使用临时 SQLite 与合成测试文件。
- 本轮前端脚本：feed 14、review 9、score 5、score-observation 12，合计 **40 passed**。feed 合同测试通过 TypeScript 编译 `feedCatalog.ts` 与 `onlinePlayers.ts`；这不是全项目前端 typecheck。
- 本轮 `py_compile`、`pip check`、`git diff --check` 通过；来源清单 JSON 可解析。
- 修正完整比赛分类：只有 `video_source.is_full_match === true` 才进入该分类。平台标题声明、受限片段和未核验的本地文件不会被显示成已验证完整比赛。
- 本轮物理可用内存读数约 0.84–1.46 GiB，未达到 2 GiB 硬门槛；没有运行 Python 全量测试、全项目 TypeScript/Vite 构建或 Windows EXE 打包。没有新 EXE，也没有重试构建。
- 本轮没有进行浏览器或原生桌面自动化。此前记录的源码 QA/网页观察仅作为既有证据，未当成本轮新验收；原生 Preview 手工体验仍待完成。
