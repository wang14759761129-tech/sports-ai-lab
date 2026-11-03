# 给次Dex：GOAL10.6 FINAL 复验交接

## 版本与本轮结论

原审计基线San `55024045089037c8f3aff3f05866befa83b6453d`没有正式消费路径。正式实现已经在San提交 `0611fb8a006120388e0b4bb4575184e0aa2d2ae2`；本轮保护该提交，仅补充跨端可复现检查和更完整的Chrome验收脚本，不重建产品。

Main交付：`6ea97363b83940e8699fb7a2f40ef4b00a795418`。Playback：`fdaf7dfbc17e18f823f0b71c4c5a2a417ebef759`。不要用旧San提交的搜索结果代表当前源码。

**本轮Main Python → San生产消费函数：PASS。新增FINAL Chrome流程：BLOCKED。** Chrome启动前仅有1.94GiB可用RAM，低于2.5GiB守卫，没有启动Chrome。不得把此前0611的46步Chrome PASS当成本轮新增的换片流程PASS。

## 请检查这些真实生产源码

- `src/review-targets.mjs`：`prepareQuickSource()`按Main算法计算规范化输入哈希；`validateReviewTargets()`核验实际契约、身份、分组及引用；`matchesQuickSource()`核对当前草稿。消费函数Git blob：`ddbb9b2f1caa1e844a0407b54253dd1e7e0e4d73`。
- `src/LocalVideoReview.tsx`：`handleTargetsImport()`读取本机报告并调用该消费函数；`chooseReviewTarget()`直接使用Main `review_targets[].point_ids`，与最新本机BOUND记录求交后调用Playback Core；`invalidateTargets()`取消队列并使旧正式视图失效。
- 同文件`confirmBoundary()`仅改变当前会话资格，保留已知胜负；换片清空旧会话绑定，刷新/导入不恢复旧身份。正式视图失败时保持失配提示，不自动切到基础模式。
- `src/contracts/review-targets-v0.1.d.ts`及stats类型依赖原样取自Main交付。没有独立Review Targets JSON Schema文件；有真实运行时校验，不将TS类型当运行时安全门槛。

## 唯一Golden与身份

San测试输入：`scripts/fixtures/review-targets/quick-input.json`；Main输出副本：同目录`targets.json`。它们与Main提交中的`review-targets-11-8-input.json / output.json`具有相同Git对象，分别为`e7a2a4873cccdc9882355fa69f612fe5728eb1c2`、`65ad0196704e9853688cf2ee910fc94ba12aec21`。

身份：dataset `SIMULATED_ONLY:review-targets-dataset`；match `SIMULATED_ONLY:review-targets-11-8`；game 1；A=player、B=opponent（输入角色，不是已验证运动员）。

规范化SHA：`ac38316ea8dd90fb82ecf9fce565e2fe9ec2e3166e90250ae535e138ca7bdad5`。算法为Python `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')`后SHA-256。它忽略缩进/键顺序，不能冒充原文件字节哈希、签名或媒体哈希。本轮QA回执另记录实际字节哈希，明确与契约哈希分开；这不是新增的生产协议字段或媒体证明。

Main给A的3–4板失分集合（N=3，未知2不计N）：

| 完整point_id | 0611此前Chrome资格证据 |
|---|---|
| `SIMULATED_ONLY%3Areview-targets-11-8/g01/p002` | 人工确认并保存4–5.5秒，参与两段连播 |
| `SIMULATED_ONLY%3Areview-targets-11-8/g01/p004` | 人工确认并保存8–9.5秒，参与两段连播 |
| `SIMULATED_ONLY%3Areview-targets-11-8/g01/p006` | 未确认当前会话双边界，不能进入队列 |

Main的`NOT_EVALUATED_CURRENT_SESSION`保持原意；独立媒体核验0，LOCAL_SESSION_ONLY、UNKNOWN权限和SIMULATED_ONLY不提升。

## 可复现命令及证据

从Web目录执行：

```powershell
npm run check:review-targets-main
npm run check:review-targets
npm run check:playback-adapter
npm run check:local-video
npm run check:loss-insights
npm run build
npm run check:preview
```

上述命令本轮均PASS。Main检查先核验四个生成器/依赖文件与交付Git对象一致，再以`python -B`调用Main实际CLI，输出只写San `.alpha-qa/`，不产生Main字节码文件；实际导入San生产消费函数，不使用test-only oracle。新生成报告与Golden逐字段相等，N=3、ID集合与规范化哈希精确一致。QA脚本离线读取声明的Main目录；Web运行时不跨工作区读文件或调用Python，Vite权限不变。

本轮新鲜回执：`.alpha-qa/goal10-6-final-cross-runtime.json`；新生成的Main输出：`goal10-6-final-main-generated.json`。35项正式契约检查和22项播放适配检查PASS；v0.1/v0.2兼容、基础计数、TypeScript及构建PASS。生产包6文件约606.6KiB，保留>500kB的JS构建提示；公开数据0场，未含Main Golden或私人报告。

RAM足够时，由San运行，或在协调后的独立Web测试副本运行：

```powershell
$env:PTTI_PLAYWRIGHT_MODULE='<本机已安装Playwright的index.mjs绝对路径>'
npm run check:review-targets-browser
```

更新脚本覆盖正确匹配、错版本/身份/哈希、缺失和未知point_id、两段0.5×、暂停/Seek取消、撤销即时失效、主动换片时旧队列停止并归零、重新确认后再允许回放、改赢家导致旧正式视图失效、导出刷新重导不恢复资格及不静默退回基础模式。**新增换片和缺失ID的浏览器证明本轮尚未执行，不能写PASS。**

`.alpha-qa/goal10-6-review-targets-browser.json`现在记录本轮BLOCKED，actions为空。已有桌面/手机/逐分截图属于0611此前运行，禁止冒充本轮新截图。源码独立审计可只读完成；运行测试会写QA、dist等输出，应使用San所有者的执行安排或隔离副本，不竞写其工作树。

## 当前 Gate

正式JSON消费及新鲜跨运行时匹配PASS；扩展后的FINAL Chrome闭环等待RAM条件，BLOCKED。真实视频、真人试用、独立媒体身份、版权及Windows Native仍未验收。本轮不推送、不部署、不启动Native，不修改Main或Playback源码。

## Main acceptance follow-up (5adc46f)

- The Main document inspected San 5502404; formal production consumption was subsequently implemented in 0611fb8 and preserved in 72d013c. Current changes clarify metric populations, without replacing the consumer.
- Formal UNKNOWN-stage scope: all input rows. Basic-mode UNKNOWN-stage scope: known-winner rows in the selected game. Per-stage formal unknown_count also includes unknown winner within the stage plus unknown stage membership; it is not a synonym of either top-level count. Both languages now state these scopes and valid N explicitly.
- Actual Main generator rerun with p014 winner=unknown: formal unknown_stage_count=2, basic unknown_stages=1, both score N=18. San validates the regenerated report; the old report fails canonical-hash matching.
- Canonical hash is computed from parsed, key-sorted, compact UTF-8 JSON per Main. Raw bytes have a separate QA receipt; formatting-only changes do not change canonical identity. Reimport replaces the source context and requires a fresh Targets association.
- Fresh checks: 36 consumer cases PASS; actual Main generation and UNKNOWN-population comparison PASS; 22 playback-adapter assertions PASS; Quick v0.1/v0.2 compatibility PASS; TypeScript/Vite build PASS; static preview public0/privacy check PASS. Existing bundle-size warning remains.
- Fresh Chrome attempt: BLOCKED before browser launch, available RAM 1.00 GiB < 2.5 GiB. No fresh two-clip playback PASS is claimed. Prior 0611fb8 evidence for p002/p004 playback and p006 unconfirmed is historical. Final runtime replacement/missing-ID checks remain pending.
- Independent recheck: run check:review-targets and check:review-targets-main; when RAM permits, run check:review-targets-browser. Local files only; no upload, persistent private storage, CI or deployment.
