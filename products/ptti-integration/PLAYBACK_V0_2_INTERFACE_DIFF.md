# Playback ↔ Match Media v0.2 接口差异

审计日期：2026-10-12
范围：只读检查 Playback worktree 与集成分支，不改 Playback/Web 代码，不运行测试或 CI。

## 检查基线

- Integration：`codex/ptti-integration-preview-sprint-0-1`，HEAD `bf652cdb07a18d67e2d573911639a593e722e8e6`，工作树干净。
- Playback：`codex/ptti-playback-recovery-sprint-0-3`，本地 HEAD `d6d62c103adafb2a12a996c8d6e73fffb3d41c63`，工作树干净；本地状态显示比其本地 tracking ref `737a54154182a1d1340cfe8b2fb1708e660645e9` 超前 4 个提交。
- Playback 的本地 ahead 提交尚不能代表获批准的 CI 结果或可交付候选。本轮未触发、重跑或取消 Actions，也未获取候选包。

## API 字段对照

检查了 `backend/video_sources.py` 的 `MatchVideoSource` / `official_source()`、`backend/video_evidence.py` 的本地视频登记与 `GET /api/video-evidence/videos`，以及 Playback 分支 `official_video_sources.json` 中的原生播放证据形状。`MatchVideoSource` 是现有来源模型/投影 helper；本轮未确认其 `/library` router 已挂载为桌面正式 API。不要将模型字段表误当成已发布的 HTTP 契约。

| Playback 字段/行为 | v0.2 对应 | 状态与差异 |
| --- | --- | --- |
| `source_id`, `match_id`, `player_ids`, `tournament_id`, `source_url`, `video_version` | `VideoSource` 身份、比赛关联、来源 URL 与版本 | 大体可映射；`match_id`、球员 ID 可能为空。缺失项须保持未知，不用名称猜测身份。 |
| `timeline_id`, `timeline_mapping_status` | 来源时间轴身份及独立 `timeline_mappings[]` | 官方来源 helper 用 `provider:video_id` 生成 ID，但映射状态是 `NOT_VERIFIED`。它只可作为来源内时间轴标签，不能证明不同来源时间轴对应。Playback 没有 v0.2 要求的完整 mapping ID、from/to、人工核验时间与证据引用对象。 |
| `source_sha256` | `LocalVideoAsset.source_sha256`、Vision 与原生播放证据的来源绑定 | 官方 `MatchVideoSource` 没有源 SHA 字段。Local `evidence_videos` 在登记时为 `source_sha256=null/hash_status=PENDING`，后台散列后才变为 VERIFIED。不能用远程 video ID、文件名或未经验证的值补 SHA。 |
| `fps`, `duration_ms`, `width`, `height`, `codec` | `LocalVideoAsset.timeline.frame_rate`, `duration_ms` 与媒体属性 | Local API 有浮点 FPS 和毫秒时长，但没有显式 `timeline_id` 或 PTS `time_base` 有理数。FPS 不能代替 time base；在来源没有实测/声明 time base 时只能留空，不能据此建立跨来源映射。 |
| `playback_verified`, `provenance.playback_test` | `external_video_page` / `embed_playback` / `desktop_native_playback` 分离证据 | 通用布尔值与自由格式 provenance 不足以表达证据面。`OFFICIAL_PAGE` 外部网页播放只能落到外部播放证据；不得推导嵌入、桌面原生或 Vision 成功。 |
| `provenance.native_playback_test` | v0.2 `desktop_native_playback` | 当前是自由格式对象，不在 `MatchVideoSource` 中有类型约束。9 条官方来源数据里 2 条有此对象、7 条没有；已有对象字段为 `date`, `result`, `version`, `verification`, `error_class`, `error_code`, `observed_message`, `region_restriction_api`。v0.2 需要显式 `status`, `checked_at`，并可绑定 `app_git_sha`, `package_sha256`, `source_sha256`, `evidence_ref`, `notes`。现有记录没有这些绑定字段，不能映射成 `DESKTOP_NATIVE_PLAYBACK_PASS`。 |
| `embed_permission`, `analysis_permission`, `viewing_permission`, `rights_evidence`, `availability_status` | v0.2 独立 `rights`、territory 与播放证据字段 | 权限与播放状态分离的方向一致，但枚举与粒度不同。逐项映射前须采用显式枚举表；不能把 `PUBLIC_PLATFORM_PAGE`、`playback_verified` 或 API 可访问性映成媒体再分发、缩略图、嵌入或 AI 分析许可。 |
| Local `original_path`, `rights_status`, `source_note` | `local_locator_ref`, 本地权益与 provenance | 原路径是本地敏感定位信息，只能映为本地引用；不得输出到 Web。权益状态需逐值映射，`PENDING_REVIEW` 不能变成 `ALLOWED`。 |

### 尚需 Playback 明确的最小字段

1. 对每个已散列本地资产，提供稳定 source identity、SHA 与明确 hash 状态；散列未完成时保持 `UNKNOWN/PENDING`。
2. 明确本地时间轴对象：稳定 `timeline_id`、`time_base`（有理数或 null）、`frame_rate`（有理数或 null）、时长。不要从浮点 FPS 推导 PTS time base。
3. 将原生播放证据从自由格式 provenance 拆成有状态、有时间、可绑定应用 commit、包 SHA、来源 SHA 和 evidence ref 的结构；旧记录字段不足时映为 `REVIEW_REQUIRED` 或 `NOT_TESTED`。
4. 明确 API 对应的 schema/contract version 与支持版本列表。集成适配器不得假定桌面 API 已接受 `ptti.match-media/0.2`。

## v0.1 消费者遇到 v0.2

现存 v0.1 JSON Schema 将 `contract_version` 固定为 `ptti.match-media/0.1`，且根对象 `additionalProperties=false`。因此 v0.2 payload 用 v0.1 schema 校验会失败，属于安全拒绝。当前未发现运行时版本协商、v0.2→v0.1 降级或字段过滤 handler；适配器只输出 v0.2。

安全规则：消费者必须先声明/协商精确支持的版本；仅支持 v0.1 的消费者收到 v0.2 时应返回明确的 `UNSUPPORTED_CONTRACT_VERSION`（或等价错误）并停止处理。禁止改写版本号、丢弃未知字段后继续、或静默降级。只有消费者明确实现并测试 v0.2 后才能接受该版本。

## 四条 Web 样本：事实、链接与媒体权限

下表是现有脱敏集成 fixture 的事实记录，不是本轮重新打开的网页。记录公开事实、保存来源 URL 与获准展示/使用媒体是三个独立判断。当前四条样本的 `metadata_listing`、`external_viewing`、`thumbnail_display`、`embedding`、`local_analysis`、`model_training`、`redistribution` 均为 `UNKNOWN`；没有权利授予证据。按现有投影规则，四条都不进入公开 Web payload。外链存在不代表它可以被展示或站内嵌入；不判定为法律上的禁止，仅按项目安全门槛暂不公开投影。

| 样本 | 可保留的事实/页面类型 | 外链与播放证据 | 媒体权限及缺项 |
| --- | --- | --- | --- |
| Doha 2023 男单决赛，Fan Zhendong–Wang Chuqin | 赛事、轮次、对阵和结果仅作为有来源的本地 QA 事实；WTT event page，event ID 2866 | [WTT 赛事页](https://www.worldtabletennis.com/eventInfo?eventId=2866&selectedTab=Overview&innerselectedTab=Completed&subEvt=MSINGLES)；无单场视频 URL，播放 `NOT_TESTED` | 文字目录展示与外链展示尚无审核依据；无缩略图展示许可；嵌入、分析、训练、再分发均 `UNKNOWN`。 |
| Doha 2023 男单半决赛，Fan Zhendong–Lin Gaoyuan | 赛事、轮次和对阵仅作本地 QA 记录 | [YouTube 视频页](https://www.youtube.com/watch?v=qIXmFTzXcs0)；保留既有 handoff 的外部画面观察，不是本轮新测；嵌入/桌面/Vision `NOT_TESTED` | 全部上述媒体/展示权限 `UNKNOWN`；无授权依据或封面许可。 |
| Singapore 2021 女单决赛，Wang Yidi–Sun Yingsha | 赛事、轮次和对阵仅作本地 QA 记录 | [YouTube 视频页](https://www.youtube.com/watch?v=XHGCGiAyKkc)；保留既有 handoff 的外部画面观察，不是本轮新测；嵌入/桌面/Vision `NOT_TESTED` | 全部上述媒体/展示权限 `UNKNOWN`；无授权依据或封面许可。 |
| Chongqing 2025 女单决赛，Sun Yingsha–Chen Xingtong | 有 WTT 文章记录；分类 `ARTICLE`，不得当作比赛视频 | [WTT 文章](https://www.worldtabletennis.com/description?artId=4731)；无单场视频 URL，播放 `NOT_TESTED`；`artId` 不作为赛事 ID | 文章事实可在本地 QA 保留；公开目录展示/链接权限仍 `UNKNOWN`。第三方图像、嵌入、分析、训练、再分发均 `UNKNOWN`。 |

公开投影的最小条件仍是相应权限字段有明确审核记录和 basis；官方来源页只能证明来源，不等于取得媒体权利。未取得许可前不显示第三方缩略图、不嵌入、不下载或用于模型训练。

## 本轮状态与下一步

- 本轮只读审计，没有运行/改动 Playback、Web 或 Integration 代码，没有重跑 Sprint 0.3 的 56 项测试。
- Sprint 0.3 上次记录为 56 项通过；本报告不冒充本轮重测。
- 未推送、未触发 Actions、未做跨线构建、未部署。
- 等待次Dex交付获批准的修复版 CI 结果、实际候选产物和稳定 API 字段定义。届时先核对上述差异和 v0.2 兼容性，再决定是否启动隔离跨线构建。
