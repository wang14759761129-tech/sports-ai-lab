# San Web Alpha RC · v0.2 对接接口

日期：2026-10-13。只读证据快照：主Dex提交 `486661b65be327af3acb8b7117febe654af4d1a0` 的 `web_consumer.py`、`WEB_CONSUMER.md` 和生成的 Alpha 合同，通过本 Web 仓库的 Git 对象读取，未操作集成工作树。此快照不是对主Dex当前工作区状态的声明。

## 已实现的消费边界

`src/readonly-catalog.mjs` 的 `consumeReadonlyProjection(payload, {view, localReview})` 接收 **主Dex已经通过JSON Schema和引用校验的 Web-safe 投影**，精确要求 `ptti.match-media/0.2`。它是纯消费接口，没有网络、文件、数据库或媒体访问，不重复实现主Dex通用适配器或完整Schema校验。

- 默认 `view: public`，只有 `metadata_listing` 和 `external_viewing` 都是 `ALLOWED` 才保留记录。
- `review` 必须显式指定 `localReview: true`。此参数由本地可信演示代码指定，不由URL/用户数据授权。当前UI不连接此函数，没有review开关或URL参数。
- 不接受本地资产，过滤标识为synthetic的记录；输出白名单没有封面、本地定位符、用户反馈或时间线文件。
- 保留各项版权、地区和每类播放证据原值；没有将外部画面证据转为 Web 站内、Embed、Desktop或Vision PASS。
- 验证精确版本、匹配/来源ID唯一性和引用，拒绝v0.1或缺字段；返回脱离原对象的数据，不修改输入。

## 字段消费与主Dex需要交付的内容

| 上游 v0.2 字段 | Web消费字段/用途 | 缺失或未知处理 |
| --- | --- | --- |
| `contract_version` | `version` | 必须精确v0.2，不降级兼容 |
| `match_id` / `source_id` / `source.match_id` | `id` / `sources.id` / `sources.matchId` | 必须非空、唯一且引用有效，不制造ID |
| `identity_status` | `identityStatus` | 保留 UNKNOWN，与URL能打开无关 |
| `event.event_id/name/year` | 原样 `event` | event_id可为null；不从页面URL推断 |
| `participants`（成员player_id/name/side） | 原样 `participants` | 无稳定身份则不赋予虚构成员ID或比赛双方归属 |
| `participant_names_unassigned` | `unassignedNames` | 保留公开名字，没有该字段则空数组；不把姓名当稳定ID |
| `discipline/round/result` | 原样用于项目/轮次/已记录赛果 | result可为null，不能成为实时比分 |
| `resource_kind` | `sources.kind` | VIDEO_PAGE / OFFICIAL_EVENT_PAGE / ARTICLE / UNKNOWN严格区分，不把UNKNOWN或文章提升为视频 |
| `canonical_url/platform/publisher/verified_at` | 官方来源面板数据 | publisher/date可null；不生成缺失的观看URL |
| `match_link_status` | `sources.matchLinkStatus` | 保留UNKNOWN；来源找到不等于比赛关联已核实 |
| `rights` / `territory` | 原样、独立的决策/地区事实 | 未知继续UNKNOWN；音频与地区可用性不由画面PASS推断 |
| `evidence` 各独立对象 | 原样 `sources.evidence` | page_access、external_video_page、embed_playback、desktop_native_playback不合并、不提升 |
| `local_video_assets` | 必须空 | 非空拒绝，必须先由主Dex消费者剥离 |

对接需要主Dex明确：精确Schema/producer SHA、review与public两个投影的来源与生成方式、稳定match/source ID、可选event/player ID、官方URL和资源类型、match_link_status、版权与地区原值、带核验日期和精确URL/5秒证据的独立external记录。

现有深链使用 fixture ID；未来请提供显式 `legacy fixture ID → stable match_id` 对照及其证据，避免直接去掉命名空间而静默重命名。当前没有启用该替换。赛事分类在已读合同中没有独立字段，缺失时隐藏分类，不从名称制造分类。

## 实际本地样例消费

在 `.alpha-qa/rc/v02-producer/` 中临时保存快照的原始只读消费者与Schema；用原消费者在内存中消费已提交的合同。生成的review/public投影仅保存在被Git忽略的 `.alpha-qa/rc`，不在public或dist。

实际结果：review **4 matches / 4 sources / 0 local assets**；public **0 matches / 0 sources**。本地Web消费边界也保持review4、public0，输入未改变，Native证据仍NOT_TESTED。

- 多哈两场 event_id 为2866，新加坡为2536；重庆仍null。
- 所有 match_link_status 为UNKNOWN，metadata_listing/external_viewing仍UNKNOWN。
- 两条外部视觉证据为EXTERNAL_VIDEO_PAGE_VISUAL_PASS；另外两条NOT_TESTED。
- 该快照重庆文章的resource_kind仍UNKNOWN，待主Dex可靠地交付ARTICLE；Web不修写该字段。

运行已有本地投影检查：

```powershell
npm run check:rc -- --projection .alpha-qa/rc/v02-review.json --local-review
```

常规 `npm run check:rc` 使用明确的合成负向单元输入，不冒充真实比赛结果；review文件未随代码或静态包交付。未来样例到达后先经主Dex原消费者/schema验证，再接入本接口。公开目录在权限未知时必须为空，不能把review复制到public绕过Gate。
