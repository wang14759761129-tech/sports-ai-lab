# Video Evidence v0.3 Preview 集成验收

构建提交：98101770ae6221208e3503afcc6609714a7ebca5。分支：release-candidate/video-evidence-v0.3-preview。

## 集成
产品分支是稳定化分支直接祖先；以 b950303 的完整产品与修复为基础，无重复补丁、无研究分支合并。来源详见 PTTI_BRANCH_INTEGRATION_AUDIT.md。

## 自动回归
- Python 最终完整回归：483 passed / 0 failed / 0 skipped，199.03 秒。1 条既有 Starlette/httpx 弃用警告。
- 前端逻辑：7 passed / 0 failed；TypeScript + Vite production build 通过。
- pip check、git diff --check 通过；182 个 tracked Python 源文件编译通过，新增构建文件亦 py_compile 通过。
- Ruff / uv 本机未安装；不以其它工作区状态推断。本轮未全仓格式化。
- 原有并发复核、幂等、过滤提升拒绝、审计回滚、CSV 注入、媒体边界、元数据拒绝、源变化/丢失、缓存哈希、编码中断和资源守卫测试均包含在完整回归中。

## Windows 构建
目录：products/ptti/build/video-evidence-v03-98101770ae/dist/PTTI-Video-Evidence-v0.3-Preview。
EXE SHA256：80b30ed3cd2f706bdecdd4a76455486c115013ad28d8ce8767e704bac5b50dda。EXE 8,043,774 bytes；完整目录 196 文件 / 496,689,262 bytes（构建完成时）。
PyInstaller 6.22.3 / psutil 7.2.2，包含 _internal、ffmpeg/ffprobe；不包含 DB、研究视频或权重。依赖系统 WebView2 Runtime。build.log 与 build-info.json 可追溯，source_tree_dirty=false。

## 实际验收分类
原生自动化 PASS：首次启动、中文引导、打开导入表单、出现 Windows 文件选择器、取消返回、重启恢复录像与暂停导入、选择真实录像、内部播放/暂停、60 秒 Seek。独立 FFmpeg 源帧与原生截图肉眼画面对照一致；不是逐帧误差量化。
原生 NOT_TESTED：文件选择器实际选定文件、权限下拉选择、慢放确认、JSON 包文件选择、确认/否决/改时间、人工关键分与专题连续播放的完整鼠标旅程。工具存在模态控件 stale reference / 子窗口命中 / 超出视口等限制，未认定为产品故障。未以浏览器代替原生验收。
打包 API PASS：真实 TRAIN game_1 视频 SHA、冻结候选包、暂停/重启/恢复导入、0 错误；确认/否决/修改时间并保存 UNKNOWN，重复请求幂等；过滤候选提升返回 400；两个人工片段与专题，JSON/CSV/HTML 导出。API 确认行明确标为工程 QA 模拟，不等于真人确认真实击球。
最终实际记录：208 待复核、1 QA 模拟确认、1 QA 模拟否决、556 FILTERED；832 包记录中的重复影子继续保护原记录。恢复导入统计包含重读后跳过已有记录，不等于重复创建。

## 隔离与资源
全新 QA 库：OS Temp/PTTI-v03-QA-20261008-183456/matches.db；启动诊断 environment=TEST。旧 Preview 与已有个人证据未删除。生产库未连接；无 GPU 模型推理、无 GAME_5/官方 TEST 读取。
采样 RAM：系统可用约 2.1–2.9 GB；EXE RSS 142.8–202.0 MB、一次 USS 102.8 MB；一次 WebView2 子进程 RSS 合计约 429 MB。这些是离散采样，不是完整峰值曲线或内存泄漏认证。无自动系统重启。

## 研究保护与 Gate
冻结配置 SHA256：fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3（本轮重新计算一致）。
DESKTOP_INTEGRATION_BUILD_VERIFIED。VIDEO_EVIDENCE_REVIEW_PARTIAL / MANUAL_GUI_CHECK_REQUIRED。HIT_EVENT_V0_3_CONFIG_FROZEN / HIT_EVENT_V0_2_PARTIAL 保持。
未 merge main、tag、Release。只有真人在原生窗口完成清单并记录结果，才考虑 VIDEO_EVIDENCE_PREVIEW_READY。
人工清单见 VIDEO-EVIDENCE-V03-NATIVE-QA.md；本地 QA 目录含 START-QA.cmd、只读诊断、API 证明与截图。
