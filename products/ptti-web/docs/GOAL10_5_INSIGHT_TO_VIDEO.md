# GOAL 10.5-W — 从失分到回合

基线：`94cd03a8e5548c7231025e9a7550123bb5e06c71`。本轮使用原创测试图案视频与 SIMULATED_ONLY 的 19 分 11:8 草稿，真人试用人数仍为 0。

## 可以操作的路径

1. 打开 `http://127.0.0.1:4174/` → 专业分析 → 视频逐分复盘。
2. 导入本轮生成的 `.alpha-qa/goal10-5-insight-export.json`，选择 `.alpha-qa/goal10-4-SYNTHETIC-TEST-PATTERN.mp4`。它们是本机测试文件，未打入公开生产包。
3. 选择第 2 分，核对 2–3 秒并分别确认起止边界、保存；第 10 分同样核对 20–21 秒、确认并保存。重导不会保留旧视频的播放资格。
4. 在“从失分回看回合”选择 A，点“3–4 次触球后结束”：已记失分 3 分，对应 p002、p008、p010；其中 2 分可回看。p008 没有时间边界，不能连播。
5. 选择 0.5×，点击“回看 2 段”，依次播放 p002、p010。可在同一面板暂停、恢复或取消；手动 Seek 也会取消旧队列。
6. 修改得分或撤销边界时，旧绑定立即失效；保存改分后类别计数及逐分列表更新。修改完成后主动导出草稿。

没有以上本机 QA 文件时，可用已获准使用的本机 MP4 自行记分、记录观察阶段并确认边界；不要将测试视频的模拟时间与真实比赛关联。

## 口径与依赖

- `local-loss-insights.mjs` 只对当前局的已保存有效记录计数。选择 A/B 代表本次视频角色，不识别运动员身份。已知胜者决定得失分，`observed_rally_stage` 原始 v0.2 枚举决定阶段分类。
- UNKNOWN 胜者不进入得失分；UNKNOWN 或缺失阶段不进入三种阶段细分。阶段不会推导第三板进攻、精确板数、旋转或落点。
- 可回看 ID 只来自现有 `playbackBindings`：当前 session 身份匹配、有效时长内的合法时间范围、起止分别人工确认。撤销确认或编辑会清空对应绑定并取消队列；导出、重导不提升来源身份。
- `LocalVideoReview.tsx` 的单分入口调用 `LocalVideoPlaybackController.seek()`；统计入口通过同一选择路径。新类别回放与旧连播都调用 `playRallyPlaylist()`，0.5×调用 `setPlaybackRate()`。
- Vite 的 `@ptti/playback-core` 指向次Dex模块。验收时 Core 提交为 `fdaf7dfbc17e18f823f0b71c4c5a2a417ebef759`，源码 Git blob 为 `370a574aeb9585748f0b9f5a02290eb834db470f`。未修改其次Dex工作树。
- 未导入主Dex M3（`9c34ce0…`）涉及的 Desktop `VideoEvidencePlayer.tsx` 或 `scorePlaylistGuard.mjs`，也未调用其直接单分入口或缓存。
- 当前是 Web 轻量描述性展示。MainDex 的 Insight/专业统计 sidecar 未作为本面板的运行时输入；没有新增专业技战术公式或宣称专业指标已跨端复算。

## 实际验收

- `npm run check:loss-insights`：PASS。19 分样本、A/B 互换、阶段计数、UNKNOWN、局隔离、解绑与改分、输入不变。
- `npm run check:playback-adapter`：PASS，12 项守卫断言；`npm run check:local-video`：PASS，含 v0.1/v0.2、主Dex既有 Golden 输入、未知字段、毫秒、时长与发球轮换。
- `npm run check:loss-insights-browser`：Chrome PASS，52 次脚本动作，18,536ms。实际完成分类筛选、两段0.5×连播、暂停/恢复、主动取消、Seek取消、保存前撤销解绑、改分、导出、刷新重导及0播放资格。耗时仅为自动化测量。
- 截图：`.alpha-qa/goal10-5-insight-1366x768.png`、`goal10-5-insight-390.png`、`goal10-5-insight-390-en.png`。390px无横向溢出，新筛选/观察对象/回看控件触控高度至少44px；中英计数一致。
- 页面异常0，外部请求0，写请求0，标注持久存储键0。日志保留 favicon 404 与换片/刷新时正常取消的本地 blob 请求。
- TypeScript 与 Vite生产构建：PASS。JS约509.72kB，仍有大于500kB的构建提示。`check:preview`：PASS，6个静态文件、约585.4KiB；不含本轮草稿、测试视频或审核JSON。
- 完整 `check:bridge` 最初因4175未启动而止于前置条件，本轮未重跑其全套Fan浏览器流程。另行启动临时本地公开服务完成所需HTTP隔离核验：review4/public0，公开模式拒绝审核JSON、私有QA、新测试fixture及旧数据入口。临时4175服务已关闭。

详细动作、导出路径、计数和异常记录见 `.alpha-qa/goal10-5-insight-browser.json`。测试脚本需要 `PTTI_PLAYWRIGHT_MODULE` 指向本机 Playwright，Chrome和FFmpeg；不会自动上传任何文件。

## 剩余 Gate

独立媒体核验始终0，播放身份是 LOCAL_SESSION_ONLY。真实录像、真实运动员/教练试用、来源版权、跨地区与设备兼容性仍未验收；review4/public0和本机草稿隐私边界保持。公开部署尚未授权。

## Playback × Gemini UX 补充收口（2026-10-15）

以已完成的 `f3d8bee…` 为实际基线，未回退到旧基线。统计行现在同时展示得失分与“当前本机可回看Y段”，有合法片段时显示“▶ 连播Y段”；Y=0时显示确认时间与绑定当前视频的说明，不渲染无效播放按钮。逐分列表提供“可回放 / 仅记分”状态；撤销边界前后状态变化已有浏览器断言。

LOCAL_SESSION_ONLY 的用户说明与来源未独立核验分别展示。UNKNOWN 解释为“未观察 / 未填写”；三类板数阶段仍采用原始机器枚举，不映射为发抢/接抢/相持。本轮没有添加训练诊断或处方。专业 sidecar 仍未作为运行时输入；现有Web小样本提示仍采用固定N<5，尚未消费主Dex sidecar 的可配置阈值，不声称该配置已接入。

只读核对次Dex `fdaf7df…` 的错误码后，Web适配器区分读取中断、读取失败、格式/编码不支持、解码失败、时长不可用、时间越界与会话不匹配；无法识别的错误使用中性提示。主动取消沿用Core的 cancelled 状态，不作为媒体故障。适配器22项断言PASS（原12项守卫加10项错误映射负例）；没有用这些映射测试宣称所有真实编码/损坏媒体均已实测。

TypeScript、构建、Quick v0.1/v0.2检查、失分计数、预览包检查PASS；最新包6文件、约587.9KiB，JS约512.15kB，保留>500kB构建提示。Chrome启动前可用内存约4.02GiB。首次运行在选择视频后等待就绪10秒超时，无页面异常，日志有一次本地blob读取取消；未捕获明确根因。增加失败现场记录后，复跑52次动作、17,712ms完成，中英文、1366×768/390px、分类两段0.5×回放、主动/Seek取消、撤销即变仅记分、导出重导0播放资格均PASS。一次就绪超时保留为稳定性观察项，不宣称已根治。最新截图与JSON证据路径沿用上文。
