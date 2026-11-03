# GOAL09.2：下一次独立 Windows RC 构建准备

审核基线：0e63569318c8f118432607c8db21f58b5d32576d。
远端只读核验：994fac25011d44c6e947439c7150bf9cd261f8a2；最近同分支CI均已结束，无运行中构建。
本报告及补充负例的精确目标，以本地提交SHA为准；本轮无push/CI/原生启动。

## 源码与测试

此前扫描竞态修复已在994fac中，15秒通信恢复和中文诊断在0e63569中。本轮只补充7个请求边界测试及超时恢复后授权Gate负例，接入已有test:folder-scan-status，未改工作流或产品权限逻辑。
真实结果：新增7项PASS（fetch及JSON读取超时、开始前/请求中取消、HTTP403、格式错误、完整REVIEW_REQUIRED返回）；实际组件9场景PASS，包含无重扫、无晚到覆盖，且恢复后直接调用登记处理器也不能绕过授权；tsc -b PASS；Vite生产构建PASS（4.78秒）。没有重复跑全量pytest或旧版CI。
中文诊断及实际Windows批处理入口12项PASS沿用GOAL09证据，本轮只读核对源码及CRLF规则，没有重测RAM或运行入口。现有候选包外诊断可用，不代表未来EXE已通过实机验收。

## 草稿保护

以下四份文件由主线交接明确标记为其未完成草稿，未跟踪、未覆盖、未删除、未加入本次提交：
- scripts/rc_start_diagnostics.py — 4c5e3cc888398daceb6577c71cd9d96809badb94981346229753700152c71b2d
- scripts/collect_rc_diagnostics.ps1 — 90ad43105486490fd01d3bb67a5037c09dde10214f4f841823f1fa4ef3162b4a
- scripts/Show-PTTI-RC-Diagnostics.ps1 — c4c15c8ed071599bd91261df04dc085b42187c7a944aed5fa9bdedc27fc78c12
- tests/test_rc_start_diagnostics_goal09.py — 00ea1f59f672a60f477ee3e80f0712032219480a9cf2ef29ed62e062791b6662
跟踪源码提交后应干净；整个工作区仍保留上述4个未跟踪文件，不能声称整体干净。Windows CI使用GitHub检出的已提交树，不会带入这些本地草稿，也不会触发其未完成测试。

## 下一次提交文件范围

相对远端994fac：.gitattributes（仅新增诊断cmd的CRLF规则）；frontend/src/MatchVideoLibrary.tsx、scanPreviewRequest.ts；frontend/scripts/test-library-scan-recovery.mjs、test-scan-preview-request.mjs；frontend/package.json；scripts/windows_rc_diagnostics.py、PTTI-RC-Diagnostics.cmd；tests/test_windows_rc_diagnostics.py；reports/PTTI_GOAL09_DUAL_TRACK.md、本报告。
无Temp数据库、MP4、模型、密钥、正式Launcher、主Dex CSS或San代码。Python/Node依赖锁及工作流未变化。

## 单次CI清单

授权前即时核对精确HEAD、远端994fac祖先、仅上述提交范围、4份草稿哈希及无同分支运行任务。仅普通fast-forward push到codex/ptti-playback-recovery-sprint-0-3；无需force、main合并或手动重跑。
两个现有工作流按分支隔离；本分支只匹配Playback候选。标准windows-2022、contents:read、45分钟上限、固定Python/Node/FFmpeg及哈希校验。
完整pytest及脱敏JUnit、依赖检查、前端9组专项（包含本轮负例）、生产构建、冻结配置/版权/来源/资源安全Gate、PyInstaller、包内前端一致性、120秒非交互真实健康JSON、精确提交和RUNNER_TEMP数据库、正常退出全部通过后才上传候选。失败只上传报告，停下分析，不重跑。
成功后另建Run归档，核验GitHub ZIP digest、EXE/Manifest/build-info及全部文件；保留旧Run38410292279和失败现场。中文诊断是包外sidecar：现有CI候选ZIP不会自动包含新桌面诊断入口。归档时须单独复制工具，并根据已验证的新哈希重新绑定；固定994fac/8871的旧诊断不能冒充可启动未来新包。
本地旧构建证据不冒充新CI成功。预计沿用约8–10分钟的历史耗时，实际以运行记录为准。

## 用户可见差异与回退

旧994fac候选：已包含扫描竞态修复；没有本轮15秒进度通信超时。
新源码：超时准确提示后台可能仍在运行，串行重新读取，不重新扫描或自动登记，恢复后消除旧扫描错误；中文包外诊断显示目标、完整性、RAM缺口、冲突及建议，保留日志和结果窗口。
回退：旧候选包、桌面图标、R4及原QA数据库全部保留；不能把新包与旧会话混用。新候选只使用绑定新哈希的独立启动器和全新OS Temp数据库，原生启动另需即时授权及资源Gate。

## 入口只读结论

PTTI Candidate QA仍指向Run38218170457旧候选。另一个桌面“PTTI Cinema Alpha RC（独立测试）”指向Run38410292279/8871正确EXE，但其脚本直接Start-Process，没有设置PTTI_PREVIEW_QA_DB或新会话，也未做Manifest全量校验；不能确认隔离，不能作为本线验收入口。未运行、未修改该脚本或快捷方式，需要其归属开发线协调修复。
本线PTTI-RC-Diagnostics.cmd默认仅诊断，Windows入口已验证；正式PTTI图标及Web4174/4175入口只读查看，不作修改。
原失败现场数据库SHA仍为264eb32ff3f9760f6db71e86dd2f0cc04c3d9267c0ccc63584cda05e7d0b9714。

结论：已提交源码具备一次独立push+CI构建条件；本地4份主线草稿须保留并明确排除，不满足“整个目录无未跟踪文件”的条件。原生验收/正式发布未通过、未授权；不把桌面入口名字视为隔离证据。
