# GOAL12.6-F-M：赛事数据内部交接封口

核对日期：2026-10-16（Asia/Shanghai）。数据与代码基线：
`0d0d5b0ade35e3d94d2409ca21ae5a15c1f0dfd3`。

## 正式结论

内部只读交接通过；公开准入不通过。三条记录均未建立正式 Match↔Video
关联，provider_match_id 与 canonical_match_id 均为 null，关联状态 UNKNOWN。
严格公开来源数为 0。没有新增比赛、许可、播放或完整性证据。
本次仅校验现有文件与代码并增加本文档，不改变 Schema、生成器或数据。

| 记录 | source_id | 视频 ID | 身份与日期边界 |
| --- | --- | --- | --- |
| 中国大满贯2025男单决赛 | video-source:youtube:0QgbtsBWZhk | 0QgbtsBWZhk | 官方结果佐证对阵/决赛；日期、开赛时间和官方单场ID未知。现有内部比赛ID仅是未关联候选。 |
| 多哈2025女单决赛 | video-source:youtube:KCGdLksBH7s | KCGdLksBH7s | ITTF日期明确的决赛报道佐证；比赛日期2025-05-25，开赛时间及官方单场ID未知。 |
| 新加坡2026女双半决赛 | video-source:youtube:O241nV8y4Dc | O241nV8y4Dc | 对阵及2026-02-26日期依赖发布者标题/二级目录；完整运动员身份、结果与官方单场ID仍不足。 |

## 交付文件与使用边界

以下路径相对于 Integration 仓库根目录，前缀为 `products/ptti-integration/`：

| 文件 | 用途与版本 |
| --- | --- |
| generated/goal12-6/cinema-source-review-internal.json | San只读UI输入；正式契约 ptti.cinema-source-review/0.1，audience=INTERNAL_REVIEW_ONLY。 |
| contracts/cinema-source-review-v0.1.schema.json | Draft 2020-12运行时结构校验，使用format checker检查日期/URI；不是权利真实性验证器。 |
| contracts/cinema-source-review-v0.1.d.ts | 与上述Cinema JSON对应的TypeScript声明；不能替代运行时校验。 |
| generated/goal12-6/match-identity-evidence.json | 三条来源的事实审计附件；report_id=GOAL12.6-M。没有独立正式JSON Schema，不作为新生产Match协议。 |
| fixtures/goal12-6-match-identity-evidence.json | 人工核查事实和原始元数据观察输入，不由San修改。 |
| GOAL12_6_MATCH_IDENTITY_REPORT.md | 来源链接、排除依据和剩余证据要求。 |

只读取GOAL12-6输出，不回退到GOAL12-3历史附件。多哈记录的新投影已排除
`www.worldtabletennis.com/eventInfo?eventId=3108`：搜索索引出现冲突，尚不知
底层原因。保留历史不是允许重新使用该引用。ITTF tournament ID、WTT event
ID、provider match ID、PTTI source ID各属不同命名空间。

## Cinema JSON完整字段含义

下表中 `[]` 表示列表项；未列为可选的必填项以JSON Schema为准。

| 字段路径 | 含义、缺失与消费规则 |
| --- | --- |
| contract_version | 精确值ptti.cinema-source-review/0.1；未知版本明确拒绝，不能静默降级。 |
| source_contract_version / input_contract_version | 分别为来源索引与核查输入版本，不是播放器版本。 |
| audience | 仅INTERNAL_REVIEW_ONLY；不能传入公开页面或作为公开目录回退。 |
| generated_at | 投影生成时间；不是重新浏览/播放/授权核验时间。 |
| catalog_snapshot.unique_video_sources / registered_match_records | 内部目录35条来源、6条登记比赛的快照计数，不是已匹配或可播放数量。 |
| catalog_snapshot.canonical_video_match_links / strict_public_video_source_count | 正式关联数和严格公开来源数，本快照均0。 |
| summary.selected_sources / official_pages_http_200 | 本次精选数3、历史HTTP页面探测成功数3；不是比赛画面播放数。 |
| summary.external_visual_playback_pass / canonical_match_links / public_projection_fallback | 分别为0、0、false；不允许从其他计数推导升级。 |
| notice | 必须保留的证据边界说明。 |
| featured_sources[].source_id / catalog_record_id / video_id / platform | PTTI来源键、目录记录键、平台视频ID及平台；精确使用source_id关联审计附件，不用标题/姓名猜测比赛。 |
| original_source_url / watch_entry | 原始官方平台URL与OPEN_OFFICIAL_PLATFORM_URL动作；仅提供明确的外部观看入口，不构造下载/媒体流地址。 |
| publisher_metadata.method / checked_at | 单视频oEmbed查验方式及其实际观察时间。 |
| publisher_metadata.title / author_name / author_url / status | 返回的标题、发布者名称/频道URL及元数据匹配状态；不证明权利人归属、比赛画面或版权授权。 |
| match_claim.event_name / event_year / discipline / round / participants | 有来源的赛事/年份/项目/轮次/对阵文字主张；不自动创建运动员ID或正式比赛身份。女双列表元素为组合标签，不保证完整个人身份。 |
| match_claim.status | 文字主张的佐证等级，保留原始值；不归一化为全局verified=true。 |
| match_claim.match_date.value / status / local_start_time | 日期及证据等级；null表示未获证据。OFFICIAL_REPORT_DATE与SECONDARY_CATALOG_ONLY不等价；开赛时间均null。 |
| match_claim.event_window.start / end / status | 赛事日期窗口及OFFICIAL_EVENT_INFO证据范围；整个对象可null，不能以窗口首/末日补比赛日期。 |
| match_claim.evidence_sources[].role / url / claims | 来源层级、证据URL及其支持的有限事实；官方域名不自动证明视频、版权或全部字段。 |
| match_claim.official_source_references_video_id | 均false；未找到官方单场记录到精确视频ID的直接引用。 |
| match_link.canonical_match_id / status | 均null / UNKNOWN；不能从对阵、赛事或结果自动填入。 |
| match_link.unlinked_review_candidate_match_id | 人工待审线索，可null；不是外键，不可用于正式join或用户比赛标签。 |
| match_link.reason / join_policy | 未关联原因及禁止标题/赛事/姓名自动join的策略。 |
| watch_status.official_page_request / page_checked_at | 历史HTTP_HEAD观察及时间；HTTP_200_PAGE_ONLY不证明画面播放。该时间早于最新oEmbed核查是正常的。 |
| watch_status.external_visual_video_playback / login_or_region_check | 均NOT_TESTED；不以HTTP、缩略图、iframe或metadata状态替代。 |
| watch_status.external_viewing_rights / territory_status / in_app_embedding_permission | 分别为外部观看许可记录、地区状态、嵌入许可；本批均UNKNOWN。 |
| watch_status.latest_recorded_embed_technical_status | 历史技术观察；MS保留BLOCKED_OBSERVED，其余NOT_TESTED；不代表当前重测或权利拒绝结论。 |
| watch_status.in_app_entry / unavailability_or_limit_reason | EXTERNAL_ONLY_PERMISSION_UNVERIFIED及真实限制说明；不能据此显示“内播已通过”。 |
| content_claim.publisher_title_claim / completeness / completeness_status | FULL_MATCH只是标题主张；本批完整性UNVERIFIED，不能进入已验证完整比赛。 |
| rights.public_listing / external_viewing / thumbnail_display / embedding | 每种使用范围分别判断；本批均UNKNOWN，不代表普通平台用户被认定禁止观看，也不构成PTTI用途的已获许可。 |
| rights.local_analysis / redistribution | 本批NOT_GRANTED；不是从外链、人工标注或文件持有推导的许可。 |
| thumbnail.url / display_permission / presentation | URL=null、权限UNKNOWN、PTTI_BRAND_PLACEHOLDER_ONLY；不从视频ID拼接第三方缩略图URL。 |
| featured_sources[].audience / next_evidence_needed[] | 每条的内部用途限制与需要补充的证据清单，不是自动执行授权。 |

## 审计附件完整字段含义

| 字段路径 | 含义与边界 |
| --- | --- |
| report_id / reviewed_at / audience / method | 审计批次、核查时间、内部范围与核查方法；没有新视频实播。 |
| policy_reference.url / document_date / checked_at | 平台政策链接、文档日期与本次查阅时间，分别保存。 |
| policy_reference.interpretation / per_video_rights_upgraded | 条款范围摘要及false；不能自动作为三条视频的独立授权。 |
| cinema_contract_version / public_admission | 附件对应Cinema版本；BLOCKED_NO_SCOPED_PERMISSION_AND_CANONICAL_BINDING。 |
| summary.reviewed_sources / fresh_oembed_metadata_http_200 | 已核查3条、单项元数据请求成功3条；不替代画面验证。 |
| summary.canonical_match_video_bindings / strict_public_sources / external_visual_playback_pass / desktop_native_playback_pass | 均0，限本批数据；不能借用无关Windows测试升级。 |
| records[].source_id / video_id / watch_url / canonical_match_id | 与Cinema条目精确对应；canonical_match_id为null。 |
| oembed_observation.checked_at / http_status / title / author_name / author_url / embedded_html_present | 实际元数据响应；HTML存在为true也不证明成功嵌入或许可。 |
| identity.provider_match_id / provider_match_id_status | 官方单场ID未知：null / UNKNOWN；事件编号不能代填。 |
| identity.registered_match_review_candidate | 同Cinema的未关联内部候选；仅第一条有值，禁止自动join。 |
| identity.event_reference / event_reference_scope | 赛事层参考URL及命名空间/范围；不是视频或单场身份。 |
| identity.event_and_pair_confidence / recorded_result | 赛事对阵佐证等级和记录结果；女双结果null，不能填0:0或根据视频标题推导。 |
| identity.match_date / match_date_status / local_start_time | 与Cinema日期事实一致；OFFICIAL_DATED_FINAL_REPORT对应Cinema的OFFICIAL_REPORT_DATE，仅为该批明确映射；UNKNOWN/null保留。 |
| identity.official_match_record_video_binding / binding_reason | UNKNOWN与具体缺口；不以元数据标题相符提升。 |
| supporting_sources[].url / role / supports[] / does_not_establish[] | 证据地址、层级、支持事实及不能证明的事项，必须同时读取。 |
| excluded_or_limited_sources[].url / status / reason | 冲突或有限用途的证据，不用于完成正式关联。列表可空。 |
| excluded_or_limited_sources[].observation_method / observed_title | 仅多哈冲突项具有的可选观察详情；SEARCH_INDEX_RESULT_NOT_LIVE_RENDER不能标成真人原生窗口观察。 |
| next_evidence[] | 对应来源剩余人工核查事项。 |
| rights.* | 与Cinema六项权限逐项一致，不能合成一个permission=true。 |
| download_permission | UNKNOWN_NO_SCOPED_LICENSE_EVIDENCE；不能由外链或嵌入许可推导下载许可。 |
| playback.metadata_lookup | PASS_METADATA_ONLY，严格只指元数据查验。 |
| playback.external_visual / embedding / desktop_native / vision | 本批全部NOT_TESTED，四类证据互不替代。 |
| playback.region / completeness / historical_embed_status | UNKNOWN / UNVERIFIED / 对应来源历史观察；不是本轮播放新证据。 |
| playback.oembed_html_is_not_playback_or_permission | true是证据边界声明，不是许可。 |

## 缺失处理与只读消费约定

1. 先对Cinema输入做精确版本与Schema校验；缺少必填字段、非法类型/枚举或
   未知版本均拒绝该输入，不使用TypeScript强制断言绕过。
2. 审计附件只用于显示来源和缺口。其结构本轮已逐条比较，但没有独立生产
   Schema；缺少附件字段时显示缺失/UNKNOWN，不给Cinema记录补可信值。
3. 不用`value || fallback`给权限、时间、比分、运动员ID或关联字段补成已确认
   数据。null不等于0，UNKNOWN不等于false，也不等于ALLOWED。
4. 当前适配器缺权限时默认UNKNOWN；缺内容类别默认UNKNOWN，缺完整性默认
   UNVERIFIED，缺地区默认UNKNOWN，缺历史技术观察默认NOT_TESTED。日期、
   对阵及发布者等必要观察缺失时拒绝；正式match链接固定null/UNKNOWN。
5. 上游只在存在明确分项许可及issuer/evidence_ref/verified_at时才产生ALLOWED。
   本批来源未满足；精选生成器还拒绝public_listing=ALLOWED的意外输入，要求
   重新核查策略。本交接不宣称现有软件能自动鉴定权利证据真伪。
6. source_id是两文件唯一连接键；URL、姓名、日期、结果都不能代替身份关系。
   缺来源/重复来源或不匹配URL不建立回退关联。任何更新需新证据与重新校验。
7. San只在其自己的工作区实现消费；本交接没有改变San运行代码，也没有证明
   San UI已接入或浏览器播放已通过。

## 封口核验与文件身份

本轮未重跑历史33项测试；该数字仅属于GOAL12.6-M。
本轮只读产物校验实际通过：现有Cinema Schema（含format checker）、三记录
字段集一致、精确source/video/URL对应、逐项权限一致、未关联与公开0约束、
离线生成结果与已提交JSON完全相同。未发起网络复核，证据时间未更新。

| 文件 | SHA-256（字节身份，不证明真实性或许可） |
| --- | --- |
| match-identity-evidence.json | 8a429a9c2109251c0d0115b9726c3d04fd8ca25c5db1b5d2bcfd89defbe7b6f0 |
| cinema-source-review-internal.json | 5e50ee10df4c97da5702bb4344fd5446e0ae4703648b1110ac186cdbb8ba6089 |
| cinema-source-review-v0.1.schema.json | 6617021f0fa3fe4d2841b7f4caa3538985768a58f33ea3cae68af5cda7e801ec |
| cinema-source-review-v0.1.d.ts | c67e75a61124773c863bf568740d40b958cf830c3d2c0688d5f7bd413f47c9c1 |

剩余Gate：三场正式Match↔Video关联、各用途分项许可、实际播放/地区/完整性
核验、San真实消费验收。本文档的内部交接通过不改变这些Gate。
