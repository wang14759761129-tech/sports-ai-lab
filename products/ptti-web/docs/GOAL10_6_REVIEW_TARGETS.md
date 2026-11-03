# GOAL 10.6-W — Review Targets 本机接入

实际 San 基线：`55024045089037c8f3aff3f05866befa83b6453d`，保留上一轮已提交的UX和错误反馈。主Dex协议及Golden来源固定为提交 `6ea97363b83940e8699fb7a2f40ef4b00a795418`，不是从当前Integration未提交状态猜测。

## 可以照着操作的路径

1. 打开 `http://127.0.0.1:4174/` → 专业分析 → 视频逐分复盘。
2. 用原生文件选择器导入 `scripts/fixtures/review-targets/quick-input.json`。
3. 导入 `scripts/fixtures/review-targets/targets.json`。页面显示输入精确匹配、Dataset ID及规范化输入SHA。
4. 选择本机 `.alpha-qa/goal10-6-SYNTHETIC-TEST-PATTERN-60s.mp4`（Chrome测试生成的原创测试图案，不是真实比赛录像）。
5. 选择观察对象A，点击“3–4次触球后结束”。来自主Dex的逐分ID末尾必须是 **p002、p004、p006**，失分3条，N=3，未知2条不计入N。
6. 点第2分，核对4–5.5秒，分别确认起止边界并保存；点第4分，同样核对8–9.5秒、分别确认并保存。仅这2分取得当前会话回放资格；第6分仍说明“尚未在当前视频会话确认并保存两端边界”。
7. 选择0.5×，点击“连播2段”。仅播放p002、p004。暂停、恢复、取消及手动Seek沿用Playback Core。
8. 撤销任一边界：活动队列取消，可回看数减少，主Dex分组和得分记录保留。修改得分、技术字段、阶段、时间数值、规则或增删记录：旧Review Targets立即失效，不能再驱动回放。基础计数模式可由用户明确选择。

以上JSON为SIMULATED_ONLY，视频为自制测试图案。时间数字仅用于测试，不能移用到真实比赛。

## 真正消费的字段与数据边界

- `contract_version=ptti.review-targets/0.1`；核对`input_contract_version`和`statistics_contract_version`。
- `dataset_id / dataset_class / match_id / source_id`必须与原始Quick输入对应。源权限保持UNKNOWN、媒体哈希/时间线为空、Vision为NOT_TESTED，不能接受报告自行提升媒体权限。
- `canonical_input_sha256`严格匹配原始Quick输入经主Dex算法规范化后的UTF-8 JSON：`sort_keys=True, ensure_ascii=False, separators=(',', ':')`。原始文件键顺序与缩进不影响此哈希。它不是原文件字节哈希、媒体哈希、签名或真实性证明。
- Golden的实际匹配值：`ac38316ea8dd90fb82ecf9fce565e2fe9ec2e3166e90250ae535e138ca7bdad5`。
- 原始Quick输入保留于页面内存，不能用自动补齐UNKNOWN后的导出替代它进行哈希。当前已保存记录及规则另做对应检查；边界确认/session标志不属于源数据内容，不能因此让报告失效，也不能从报告取得这些资格。
- Review Targets驱动筛选时直接使用`review_targets[].point_ids`及角色/阶段。核验各分组的ID、胜者、观察阶段、分区、计数、有效分母、未知项和重复引用，冲突即拒绝，不静默改用Web计数。
- `playback_eligibility`必须是`NOT_EVALUATED_CURRENT_SESSION`。队列为正式候选ID与当前`playbackBindings`中BOUND记录的交集，仍需本机会话身份、真实有效范围及两端人工确认。
- 正式视图涵盖**整份输入**，基础模式是已有Web本局轻量展示，两者有独立入口和清楚标签。多局输入不擅自把整份输入的分母改为某一局。
- 小样本提示使用报告的`display_caution_threshold`及`sample_status`。本Golden阈值5、目标N=3，显示样本不足；UNKNOWN不纳入已观察阶段的N。基础模式仍采用已有固定5阈值。

## 源码与协议资料

- `src/review-targets.mjs`：本机输入规范化、哈希、协议/身份/分组安全校验，当前草稿对应检查。
- `src/LocalVideoReview.tsx`：双文件选择、原输入内存绑定、显式模式、正式point_ids筛选、回放资格交集与编辑失效。没有浏览器调用Python、上传接口或新的持久存储。
- `src/contracts/review-targets-v0.1.d.ts`及其stats类型依赖从上述主Dex提交原样复制，编译后类型擦除；没有运行时跨工作区读文件。主Dex交付的是DTS/Python生成器，没有单独的Review Targets JSON Schema文件，消费者没有杜撰另一个协议。
- `scripts/fixtures/review-targets/`两份JSON从该提交读取原始Git字节，只用于本机文件选择和测试。没有在浏览器自动加载，也不进入dist。Vite目录权限未扩大。

## 实际检查

- `npm run check:review-targets`：**35项PASS**。Main原始哈希、键顺序/缩进、Unicode、安全整数、准确p002/p004/p006、N=3/未知2、坏JSON、错版本/身份/源/哈希、缺失或多余字段、重复/断裂引用、权限提升、分母冲突、得分/规则/时间变动与确认标志分离。
- `npm run check:review-targets-browser`：**Chrome PASS**，46次脚本操作，13,406ms。启动前可用RAM约2.616GiB，高于2.5GiB守卫。实际导入主Dex两文件，拒绝五种错误报告，A/B切换、三条producer IDs、两段0.5×连播、暂停/恢复/Seek取消、撤销后资格2→1且N=19不变、改分前置失效、导出刷新重导后0播放资格全部执行。
- 桌面1366×768、手机390px、中英文PASS；新回看控件至少44px，手机无横向溢出。
- 页面异常0，非本机/写请求0，相关持久存储键0。保留浏览器favicon.ico 404记录，不冒充零控制台记录。
- 现有Quick v0.1/v0.2及Golden输入检查、22项播放适配守卫/错误映射、基础失分计数：PASS。
- TypeScript、Vite生产构建、预览包及`git diff --check`：PASS。dist六个静态文件约606.6KiB；JS约530.94kB，仍有>500kB提示。新增Golden的身份和输入SHA不在dist中；review4/public0保持，测试视频、输入和用户报告均未打包。

浏览器日志：`.alpha-qa/goal10-6-review-targets-browser.json`。
截图：`goal10-6-targets-1366x768.png`、`goal10-6-exact-point-ids.png`、`goal10-6-targets-390.png`（均在`.alpha-qa/`）。测试导出的已编辑Quick为`.alpha-qa/goal10-6-edited-quick.json`，故意不再匹配原Review Targets。

## 限制及下一次生成

浏览器不重写Python分析引擎。当前消费的是版本化Review Targets中的角色得失分、观察阶段、分母、未知数、阈值与候选ID。service分区仅结构校验，不展示或重新推断其发球统计；完整专业stats、关键分、训练诊断、Main observations文本及Vision仍未接入此视图。

修改Quick后，需要用对应的精确Quick JSON重新运行主Dex生成器，再导入这份Quick和新报告。现有Web导出会补齐UNKNOWN字段，可能改变规范化输入SHA，即使看起来没有新增观察；旧报告不能强行关联该新文件。浏览器规范化匹配限制数字为JS安全整数，其他数字编码或非法Unicode按拒绝关联处理，不伪造摘要；普通Quick工作台仍可独立使用。

协议没有独立dataset修订号，当前以输入协议版本、dataset/match/source身份及完整规范化内容SHA绑定修订，不编造版本字段。以上匹配不证明报告作者、标注真实性或媒体身份。真人试用和真实录像仍为未验收，独立媒体核验0、LOCAL_SESSION_ONLY、版权UNKNOWN。未推送、部署或修改Main/Playback源码。
