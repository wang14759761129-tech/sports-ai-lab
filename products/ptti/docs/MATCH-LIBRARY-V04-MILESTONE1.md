# PTTI v0.4 Milestone 1：比赛视频库

基线 fbfaad46c4f4ff965484d32b0d458006800ff742。独立分支 feature/ptti-match-library-vision-replay-v0.4；保留旧 Preview、main 与研究冻结版本。

## 数据与来源审计
本机 registry.json：16 名运动员 / 6 场职业比赛，全部 REFERENCE_ONLY，没有已登记可播放职业录像。沿用 2026-10-05 的来源快照，不改历史比赛结果。赛事日期/轮次原本缺失的保持未知，不猜每局比分。
2026-10-08 重新访问 5 个 WTT 来源页只返回 JavaScript shell；ITTF 2026-10-05 报道返回 403。因此本轮不能声称重新独立验证全部比赛结果。UI 显示来源收录日期；已有比赛按 athlete_id 关联。

官方来源：
- WTT eventInfo 3098、3083；description artId 6482、4719、5707。
- https://www.ittf.com/2026/10/05/sora-matsushima-becomes-first-non-chinese-world-no-1-since-2018/
- https://worldcupresults.ittf.com/eventInfo?eventId=3379&selectedTab=Draws&subEvt=MSINGLES

## 官方视频权限策略
[WTT Media Archive 条款](https://media.archive.worldtabletennis.com/terms_of_use)明确内容需授权，禁止未经许可抓取、复制及分发。许可按用途、地域和分发方式约定；联系 media.archive@worldtabletennis.com。本轮仅核查公开政策，不联系他人、付费或抓取媒体。
[WTT 赛事页](https://www.worldtabletennis.com/eventInfo?eventId=2536&innerselectedTab=Completed&selectedTab=Overview)能展示 FULL Match Replay 标题，但没有由此证明 PTTI 的嵌入/下载/逐帧分析权。本轮所有远端保持 SOURCE_LINK_ONLY；不创建 iframe、不访问流或 cookie。
VideoSourceProvider 预留 LOCAL_READY / AUTHORIZED_REMOTE_PLAYABLE / OFFICIAL_EMBED_ALLOWED / SOURCE_LINK_ONLY / RIGHTS_REQUIRED / UNAVAILABLE；当前只实现已确认本地引用及官方来源链接。其它状态须以后有独立许可依据才能启用。

## 产品与数据模型
复用 Professional Registry、EvidenceStore、Repository、既有播放器和审计 schema。Competition 由 competition_level 标识，TournamentEdition 为已有 event_id/名称/日期的目录投影；Match 使用原 ID；Player 使用 athlete_id；VideoAsset 使用 evidence_videos；Game/Point 复用人工 timeline/points；Evidence、专题保持原数据。没有新建第二套数据库或播放器。
首页、运动员比赛目录、比赛详情、可观看本机录像、最近播放与关键分专题已接入。官方资料没有视频时明确提示权限不足，不渲染假播放器。
再次打开索引页会带回已保存的文件夹与来源说明，用户重新确认使用范围即可扫描新增文件；不要求重复选择目录。
文件夹索引单 worker、非递归、逐文件 probe 与 1MB 流式 SHA、最多 500 个候选；后台状态持久化。扫描不会自动注册或关联。用户确认后复用原 registrar，按 SHA/路径识别已登记项，源改变拒绝关联，移动后按哈希重新关联。用户点击“为这场比赛关联视频”或选择已有未关联录像；不会覆盖既有比赛关系。
最近打开的录像保存在隔离 SQLite 的独立轻量索引，首页最多显示12条；不计作实际播放时长。避免随机本机端口导致 localStorage 重启失效。原始比赛不依赖视觉模型或候选 JSON。索引失败不阻止原播放。

## 范围与限制
只交付 Milestone 1。未安装 OCR、新模型或运行 BallTrack；未实现跨比赛比分搜索、原始/Vision同步切换、球速或 RPM。Research TRAIN 演示不能冒充 WTT 录像或绑定无关职业运动员。没有授权职业视频时产品目录仍诚实显示 0 场可内播；合法本机研究素材单独标注且不打包。
冻结 Hit 配置 SHA256：fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3。
Production DB、GAME_5 Holdout、官方 TEST、研究 GT 均不参与本轮。Milestone 2/3 和 3D/旋转技术调查另行推进，不能由本轮界面推断已经实现。
