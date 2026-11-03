# GOAL 05 · Web 实际消费 Alpha Bridge

日期：2026-10-13。San 基线：`f4d9025c50ee0a3df359ecb44e50da90ee23bb25`。初始工作树干净。只有 `products/ptti-web/**` 修改。

## 输入证据

只读检查主Dex `products/ptti-integration/ALPHA_RC_BRIDGE.md` 及 `generated/alpha-rc/` 两个文件。检查时主Dex本地HEAD为 `8e36b4647dc5044f60f7a1f4b93756590aacf899`，本轮没有在其工作树执行写入或运行其生成脚本。

| 实际文件 | SHA-256 | 实际结构 |
| --- | --- | --- |
| web-internal-review.json | `99446e0c41b39fac7bda87f3c5fe8176e987aca9ff501b00cab8d2d07ae4a5c8` | v0.2，4 matches / 4 video_sources / 0 local assets / 0 timelines |
| web-strict-public.json | `61ad55ef42444dab0316fe2545aacbb4aa59667f053725e933d0917ca57e1873` | v0.2，所有目录数组为空 |

`bridge:import` 已真实从上述源目录运行；复制后字节及HTTP审核响应哈希与源文件一致。审核文件只在被Git忽略的 `.alpha-qa/bridge`，不在生产public目录。

## 活跃数据链

`catalog-mode.ts` → 明确编译模式 → fetch真实JSON → `consumeReadonlyProjection` 版本/ID/引用/权限拒绝 → `projectBridgeMatches` 展示投影 → 已有搜索、详情、PNG和深链。

展示投影只映射声明字段，不重写上游通用适配器：match_id保持原值，sources用source.match_id精确关联，source_id保留；resource_kind和canonical_url决定来源入口；rights与全部独立evidence保留。没有从标题/链接形状推断比赛关联、球员身份或文章来源类型。Legacy fixture不参与数据加载。

外部视觉PASS仅按VIDEO_PAGE、精确请求/最终URL、画面变化、至少5秒、来源及发布者核验字段、有效核验日期和无提示记录判定。不改变原始native/embed/audio/territory状态，也不产生任何版权ALLOWED。

## 可打开的两种演示

- 审核：http://127.0.0.1:4174/ ，`npm run dev:review`，内部测试横幅，4场。
- 审核深链：http://127.0.0.1:4174/?match=web-match%3Adoha-2023-ms-sf-fan-lin 。source_id为 `web-source:doha-2023-ms-sf-fan-lin`，官方URL为 `https://www.youtube.com/watch?v=qIXmFTzXcs0`。
- 严格公开：http://127.0.0.1:4175/ ，`npm run dev:public`，明确0场及权限解释。不因零场回填旧样例。
- 生产构建：同样只读取严格公开JSON。review构建被拒绝；`?review=1`等参数不能切换模式。私有审核路径和旧fixture路径在严格开发服务中404。

| match_id | source_id | 上游资源类型 | 外部视觉证据 |
| --- | --- | --- | --- |
| web-match:doha-2023-ms-final | web-source:doha-2023-ms-final | OFFICIAL_EVENT_PAGE | NOT_TESTED |
| web-match:doha-2023-ms-sf-fan-lin | web-source:doha-2023-ms-sf-fan-lin | VIDEO_PAGE | EXTERNAL_VIDEO_PAGE_VISUAL_PASS |
| web-match:singapore-2021-ws-final-wang-sun | web-source:singapore-2021-ws-final-wang-sun | VIDEO_PAGE | EXTERNAL_VIDEO_PAGE_VISUAL_PASS |
| web-match:chongqing-2025-ws-final-sun-chen | web-source:chongqing-2025-ws-final-sun-chen | UNKNOWN | NOT_TESTED |

## 真实测试结果

`npm run check:bridge` 已通过：

- 源JSON与本机HTTP返回字节匹配；4个match/source ID和引用来自Bridge，当前严格public0。
- 中文/English × 390/768/1440六组：实际审核4场、中文英文搜索、核验筛选、稳定ID深链、键盘Enter、刷新与语言保持、source_id/canonical_url、原始rights/native证据显示、PNG真实下载1200×675、分享文案、44px可见操作和无横向溢出。
- 错误版本、重复match ID、重复source ID、悬空来源引用、不安全URL、非法权限值、本地资产、坏JSON八组：安全错误卡，0卡片；重试后重新读取真实Bridge恢复4场；无JS异常或旧fixture补位。
- public注入UNKNOWN权限的review JSON仍0场；URL开关无法启用review；原始输入不变。
- 错视频ID、推进不足5秒、缺日期、无效日历日期、发布者核查缺失均不取得视觉PASS。
- 实际生产dist在临时loopback/CSP静态服务中为public0，没有review请求或endpoint；审核模式生产构建拒绝。

`npm run build` TypeScript/Vite通过；`check:preview`通过，生产仅5个文件：index、JS、CSS、_headers、data/web-strict-public.json，约314.2KiB。没有review JSON、legacy cinema.json、媒体或私有数据库；旧fixture只移至测试目录，原内容未改。`git diff --check`通过。

本轮不以重复111项旧来源回归作为接入证据；旧浏览器检查入口已转向Bridge测试。历史源/筛选unit fixture继续可追溯。

## 上游缺口及准确处理

- 全部match_link_status UNKNOWN：明确显示未核查，不能按比赛标题升级。
- 重庆 resource_kind UNKNOWN：界面显示类型未核查，不擅自标ARTICLE。请主Dex有证据后补齐。
- 赛事页面与重庆来源publisher为null，显示未核查；两条视频的publisher已有WTT核验值，按原字段展示，不需要补写。
- participants为空、球员稳定ID未提供；展示participant_names_unassigned并说明身份对应未核查。重庆event_id仍null。
- 两个result实际均是正确的 `4–0`（U+2013），保留原值。最初控制台显示乱码的错误反馈已向主Dex撤回；U+FFFD只作为合成负向输入，不当作真实样例缺陷。

上述字段情况已直接通过消息交给主Dex，没有改写其JSON。公开列出/外部观看等权限仍UNKNOWN，需主Dex依法审核才能进入public，不能由San补值。

## 当前Gate

这是真实v0.2本机审核演示，不是公开发布。真人测试0；声音/跨地区/嵌入/Windows原生/Vision本轮无新验收。没有推送、Cloudflare部署、CI触发或Windows候选操作。反馈仍只在浏览器本机保存。
