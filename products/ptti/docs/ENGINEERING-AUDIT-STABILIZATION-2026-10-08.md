# PTTI Engineering Audit & Stabilization Sprint

## 中文交付报告

### 1. 覆盖范围

实际检查了桌面入口、中文导航与复核队列、API、数据库与运动员目录、视频导入/播放接口、Canonical Timeline、Scene/RT-DETR/SAM2/RTMPose 的证据契约、BallTrack worker、Hit 融合边界、chunk/cache/导出、测试与构建系统。下方覆盖表记录每项具体文件及检查深度。

其中复核、视频导入、导出和长视频状态机进行了最小复现与修复；其他视觉模块以源码接口和既有回归为主。没有执行新的模型推理、完整职业比赛评估或原生桌面点击验收，不能把静态检查称作这些功能的现场验收。

### 2. 已确认问题

| 级别 | 问题 | 结果 |
|---|---|---|
| P0 | 过滤候选可经 API 提升为确认，通用编辑绕过专用复核历史 | 服务端禁止绕过；E01 测试通过 |
| P1 | 删除原始 AI 候选造成证据丢失与导入键悬空 | 原始候选保留，使用否决代替删除 |
| P1 | 并发复核丢失一条审计历史 | 读、改、审计在同一写事务内完成，注入审计失败会整体回滚 |
| P2 | 重试相同请求产生重复审计 | 相同状态修改幂等返回，不新增历史 |
| P1 | CSV 外部来源字段可作为公式解释 | 文本转义；原始 JSON 保持完整，六种公式输入通过 |
| P1 | 缺失/错误哈希的 chunk 输出可先被标为完成 | 完成前校验；失败保持 FAILED/PAUSED |
| P2 | 生成短预览却整场载入 CSV | 流式扫描，仅保留三个窗口，帧号和坐标保持一致 |
| P1 | 编码失败发布残缺预览，遗留临时文件 | 临时编码后原子发布，失败清理并保留此前有效预览 |
| P1/P2 | 旧异步响应覆盖新筛选；第二页复核后错跳；失败后继续导航；导入不刷新队列 | 请求代次/视频范围保护、当前页续看、成功通知、操作锁、导入进度刷新 |
| P2 | 已拒绝候选无法从界面更正 | 支持人工再次确认/更正，过滤记录仍锁定 |
| P1 | 非法时长、分辨率或帧率进入视频流程或抛未处理异常 | 入库前拒绝；有效分数帧率保持不变，缺失流时长使用探测到的容器时长 |
| P1 | 桌面环境缺少 psutil，进程树监测实际降级 | 补齐仓库已有 worker 同版本依赖；显式标记降级状态，短时子进程监测通过 |

每项的根因、代码模块和对应测试见下方 E01–E13 表。前端逻辑测试不是原生点击证据。

### 3. 量化优化

6 万行工程 CSV，三个 900 帧窗口、编码器使用测试替身：Python tracemalloc 分配峰值从 **26,086,172 bytes（24.88 MiB）降为 1,633,401 bytes（1.56 MiB）**。仅证明 CSV/窗口处理内存改善，不代表全场推理 RSS、GPU 性能或算法精度。

复核操作、异常筛选和更正按钮有用户可见改动；没有真人计时，因此不声称节省了多少分钟。

### 4. 测试与验证

- 基线实际重跑：451 passed、0 failed。
- 最终完整 Python 回归：**481 passed、0 failed**，167.59 秒，1 条现有 Starlette/httpx 弃用警告。
- 前端异步/决策逻辑：**7 passed、0 failed**；TypeScript 类型检查与 Vite 生产构建通过。
- Git 跟踪的 179 个 Python 源文件全部编译通过；`pip check` 无损坏依赖；`git diff --check` 通过。
- 初次递归语法扫描误入被忽略的 worker 第三方环境，遇到 Windows 长路径字节码写入错误。随后改用 Git 源文件列表，将字节码写入临时目录。没有修改依赖源文件、模型或权重；不把该初次扫描报告成成功。
- Ruff/uv 不在当前环境，前端未配置 ESLint；未引入新的 lint 框架。
- 原生窗口、Save As、真实画面 Seek 误差、打包后重启、GPU 多块恢复仍未验收。

### 5. 实测资源与真实 DEV 检查

只读探测 GAME_1：1920×1080、120 FPS、H.264、738.325 秒。60–60.5 秒单线程 CPU 解码到空输出成功，耗时 **0.468 秒**，21 次采样的 FFmpeg RSS 峰值约 **37.9 MiB**。没有读取标注、加载模型或生成分发素材，也没有做完整视频解码校验。

资源快照：物理 RAM 约 15.8 GiB，可用约 3.33 GiB；长任务要求约 3.95 GiB，启动守卫返回拒绝。GPU 背景快照为 1,476 MiB 已用、6,424 MiB 可用、6% 利用率。没有长 GPU 推理，故不报告推理 FPS 或内存泄漏结论。

### 6. 研究完整性

冻结配置 SHA256 保持 `fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3`。研究分支仍为 `17574a58078923cbf1828b69e9875e4cd1968411`。未运行 GAME_5、未读其标注或官方 TEST 原始数据，未打开或写入 Production SQLite，未修改 Hit/BallTrack 算法、阈值、权重或指标。

所有 Gate 保持 PARTIAL / FROZEN / MANUAL_GUI_CHECK_REQUIRED；没有 AUTO_READY、合并 main、打 tag 或发布正式版本。

### 7. Git

独立分支 `codex/ptti-engineering-audit-stabilization`，各修复独立提交且可回滚，提交列表见下方。最终交付文档提交后的 HEAD 和工作树状态在聊天汇报中给出。

### 8. 剩余风险

旧短片段缓存及其他模型结果加载器仍需完整的损坏/中断验收；原生窗口实际定位、焦点、对话框和包内环境有待人工检查；多块真实 DEV 推理及进程资源释放有待 RAM 预算充足时测量。这些是未验证风险，不能当作已经复现的模型失败。

### 9. 下一阶段仅三项

1. 以获准使用的视频完成原生 Video Evidence 复核闭环与画面定位验收。
2. 资源守卫允许后，完成受控 DEV 多块运行、模拟中断续跑和工作集趋势验证；不自动恢复 GAME_5。
3. 将其余短片段/模型 worker 的缓存与完成状态校验补齐，保持冻结推理语义。

---

下面保留可复查的技术路径、复现条件和测量口径。

## Verified baseline and boundaries

- Repository workspace: `sports-ai-lab/products/ptti`; starting branch `codex/ptti-video-evidence-v01-resource-hardening`.
- Actual origin verified: `https://github.com/wang14759761129-tech/sports-ai-lab.git`.
- Starting commit: `7d2a06381d08c5a9bec2f8f8744cf71b218c4368`; starting tree clean.
- Independent repair branch: `codex/ptti-engineering-audit-stabilization`.
- Baseline regression actually rerun: **451 passed, 0 failed**, one existing Starlette/httpx deprecation warning, 142.13 seconds.
- Frozen config file SHA256: `fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3`.
- No GAME_5 holdout or annotations, official TEST source data, production SQLite connections/writes, model training, main merge, tag, or release performed.
- Engineering fixtures below are not algorithm evaluation or real-match accuracy evidence.

## Coverage map and initial audit checklist

| Area | Files/surface actually inspected | Verification and limits |
|---|---|---|
| Windows entry/pywebview | `apps/desktop.py` source/frozen environment selection, localhost startup, dialog bridge, server teardown | Static inspection and existing desktop tests; no native window clicks or fresh Windows package |
| TypeScript/Vite/navigation | `frontend/src/main.tsx`, `VideoEvidencePlayer.tsx`, `HitCandidateReviewQueue.tsx`, `package.json` | Review workflow examined in detail; TypeScript/Vite and new async logic tests; no complete visual inspection |
| Python API | `backend/main.py`, `video_evidence.py`, `vision_api.py`, `preview_api.py`, `player_motion_api.py` | Core evidence routes checked deeply; other route boundaries sampled, not a full penetration test |
| Library/athlete registry | `backend/repository.py`, `professional.py`, existing seed and library tests | Guarded SQLite/schema/seed interfaces inspected; production data not opened |
| Video intake/playback | `video_evidence.py` registration, SHA/relink, HTTP Range, `vision/quality.py` | Public API regressions and real GAME_1 media probe/short CPU decode; WebView seek image accuracy unverified |
| Canonical timeline | `backend/evidence_fusion.py` CanonicalVideoTimeline, `backend/fullmatch.py` mapping | Read-only review plus existing 120→30 FPS/VFR/chunk tests; frozen inference mapping unchanged |
| Scene bootstrap | `scene_bootstrap.py`, `person_scene.py`, `hybrid_scene.py`, `vision_v2.py` | Candidate/role/provenance contracts inspected; no Grounding DINO inference |
| RT-DETR | `person_detector.py`, scene worker launch boundaries | Person schema and pinned-runtime interfaces checked; no GPU detector run |
| SAM2 tracking | `sam2_player_tracking.py`, `player_tracking_loop.py`, `anchor_guided_tracker.py` | Role/object-ID/recovery and stored-artifact contracts inspected; no propagation or new footage evaluation |
| RTMPose | `player_motion.py`, `player_motion_api.py`, worker interface | Crop/global coordinates, quality gating and worker lifecycle sampled; no pose inference |
| BallTrack | `vision_worker/balltrack.py`, `background.py`, `vision/runner.py`, runtime requirements | Sequential decode, bounded history/batch, no-grad and cache surfaces inspected; checkpoint/model/threshold unchanged |
| Hit fusion | `evidence_fusion.py`, `hit_event_v02.py`, frozen config | Read-only boundaries and existing tests; no research evaluation or decoder tuning |
| Human review | `video_evidence.py`, player/queue frontend | Transaction, idempotency, audit history and correction restrictions reproduced and repaired |
| Long-video/chunks | `fullmatch.py`, `full_match_pipeline.py` | Artifact validation, resume, guard and preview paths reproduced/tested; no actual multi-chunk GPU run |
| JSON/CSV/HTML | Evidence export functions and existing product export routes | CSV injection/repeatability and raw-history preservation tested; HTML escaping inspected |
| DB/config/log/cache | `database.py`, `repository.py`, chunk manifest and resource logs | Isolation, rollback, corruption and fallback tests; historical production lineage remains outside scope |
| Test/build/dependencies | `pytest.ini`, `tests/conftest.py`, `requirements.txt`, preview builder | Full isolated regression, compile/build checks; Ruff/uv absent, no ESLint configured; PyInstaller not run |

Priority was given to reproducible data integrity, state-machine, resource and user-flow defects. No broad module rewrite or cosmetic redesign was performed.

## Confirmed bugs and fixes

| ID / priority | Trigger and root cause | Minimal fix / regression |
|---|---|---|
| E01 / P0 | FILTERED candidate could be confirmed through review API or generic manual PUT; frontend disabling was the only barrier | Server blocks promotion and requires the dedicated review route for modern AI candidates. `test_filtered_ai_cannot_be_promoted_or_edited_through_manual_api` |
| E02 / P1 | DELETE removed an imported raw candidate while its import key remained, so duplicate import could not restore it | Reject deletion of raw AI records; human rejection remains available. `test_ai_raw_record_cannot_be_deleted` |
| E03 / P1 | Simultaneous confirmations/rejections read the same old JSON before separate writes, losing one review-history entry | BEGIN IMMEDIATE before reading, update and audit INSERT in one transaction. `test_concurrent_reviews_preserve_each_prior_decision`, audit-failure rollback test |
| E04 / P2 | Identical retries appended duplicate review/audit records and changed timestamps | Compare normalized intended state and return the existing row for a no-op. `test_identical_review_retry_does_not_duplicate_audit` |
| E05 / P1 security | External source labels beginning with formula characters survived CSV quoting | Prefix dangerous text cells with a literal apostrophe; numeric cells and embedded raw JSON remain preserved. Six parametrized CSV export tests; no actual formula execution attempted |
| E06 / P1 | Executor returned missing or hash-invalid artifacts and runner marked the chunk COMPLETE without verifying them | Validate declared artifacts before completion; incomplete outputs become FAILED/PAUSED. Two `test_new_chunk_with_invalid_artifacts_is_never_committed_complete` cases |
| E07 / P2 resources | Three short preview windows used `list(csv.DictReader(...))` over the entire match | One streaming scan retains only selected windows, preserving frame/coordinate output. Bounded-memory engineering test |
| E08 / P1 | Encoder failure left a partial named preview and temporary source/prediction files | Encode to `.part.mp4`, replace only on success, clean temporaries in finally, preserve an older valid preview. Failure-injection tests |
| E09 / P1 UI | Older video/filter/page responses could overwrite the newer selection and loading state | Generation-and-scope request guard; async reversed-completion tests |
| E10 / P2 UI | Review on a later page reset to page zero; a failed save resolved normally and still advanced; mouse review/import progress did not correctly refresh the independent queue | Retain page/filter scope, advance after successful review notification, refresh from import progress, preserve cursor page, block concurrent/repeated actions. Request/sequence/shortcut logic tests; native click acceptance pending |
| E11 / P2 UI | Rejected suggestions could be selected but their confirmation controls stayed disabled, preventing correction | Explicitly allow human correction of confirmed/rejected records while keeping filtered records locked. `canReviewCandidate` contract test |
| E12 / P1 intake | Zero/negative/nonfinite duration and invalid dimensions were accepted; denominator-zero FPS raised an unhandled error | Reject invalid metadata before registration; preserve valid rational FPS and use probed container duration when stream duration is unavailable. Twelve metadata boundary/control tests |
| E13 / P1 telemetry | Desktop requirements omitted psutil; live environment raised ModuleNotFoundError and silently lacked RSS/USS/process-tree metrics | Pin the already-used worker version `psutil==7.2.2` for desktop, install this small dependency, label fallback explicitly, verify an owned CPU-only child process |

## Commits

- `93b4bc6` — atomic/idempotent human review and raw candidate protection.
- `f4ed6bd` — CSV spreadsheet safety.
- `bed1a17` — checkpoint completion validation.
- `186e522` — bounded preview evidence and atomic encoded publication; overlay subprocesses now use the existing runtime resource monitor.
- `6e43dee` — asynchronous review queue/navigation safety.
- `05dadc6` — video metadata boundary validation.
- `510be48` — audited correction UI for rejected suggestions.
- `aca4a44` — desktop process telemetry dependency and explicit fallback status.
- `2ee2d3f` — preserve legacy raw AI records on deletion requests.
- `d0cbfa0` — hide deletion actions for legacy/raw AI evidence in the desktop UI.

## Measured engineering results

### Preview CSV fixture

Synthetic **engineering-only** CSV: 60,000 rows, 30 FPS timebase, three 900-frame windows. Encoder subprocesses were stubbed so this measures Python CSV/selection allocations only, not video encoding or GPU memory.

- Before: tracemalloc peak **26,086,172 bytes** (about 24.88 MiB).
- After: **1,633,401 bytes** (about 1.56 MiB).
- Selected frame ranges remained 0–899 in each local window; three windows still contain 900 observations each.
- This does not establish full-match RSS stability, inference throughput, or algorithm accuracy.

### Real DEV media compatibility

Read-only Extended OpenTTGames TRAIN `game_1.mp4`, local licensed research source; annotations not used.

- ffprobe: 1920×1080, 120 FPS, H.264, 738.325 seconds, 88,599 reported frames; probe 0.129 seconds.
- Single-thread CPU decode to null output: source interval 60.0–60.5 seconds, return code 0, empty error output.
- Wall time: **0.468 seconds**. Sampled FFmpeg RSS peak: **39,702,528 bytes**, about 37.9 MiB; 21 samples.
- This validates a representative interval, not whole-file integrity or the complete pipeline. No new video artifact was distributed.

### Resource snapshot

- Physical RAM: 16,962,326,528 bytes, about 15.8 GiB.
- Available RAM: 3,574,829,056 bytes, about 3.33 GiB; short decode minimum 3,525,853,184 bytes.
- Long-job required available RAM: 4,240,581,632 bytes, about 3.95 GiB. Guard result: **denied / RESOURCE_GUARD_BEFORE_WORKER**.
- Diagnostic process RSS 31,821,824 bytes; USS 18,984,960 bytes. These are the diagnostic process, not an inference worker.
- RTX 5060 Laptop snapshot: 1,476 MiB used, 6,424 MiB free, 6% utilization, 57°C. This is background system load, not this sprint's model inference.
- No long GPU task or multi-chunk DEV inference launched; no inference FPS or leak diagnosis is claimed.

## Final verification

Final full regression after telemetry and legacy-compatibility repair: **481 passed, 0 failed**, one existing Starlette/httpx warning, 167.59 seconds.

- Before the final dependency fix: 479 passed, 0 failed, one existing Starlette/httpx warning, 165.27 seconds.
- Current frontend review logic: **7 passed, 0 failed**; these exercise shared async/decision logic, not native user clicks.
- TypeScript typecheck and Vite production build passed; 179 tracked Python source files compiled successfully to an isolated temporary bytecode directory; pip dependency check passed.
- Ruff/uv are absent from the current environment; no ESLint task/dependency is declared. No new lint framework installed.
- No new Windows executable built and no native pywebview/Save As/actual-seek interaction certified.

## Remaining risks and gates

Potential risks are distinct from reproduced bugs:

1. The older short-clip `vision/runner.py` cache still relies on artifact presence rather than the full-match hash/commit discipline. Corruption recovery under actual model execution was not tested here; do not silently invalidate/recompute frozen research caches.
2. RT-DETR/SAM2/pose output loaders and lifecycle paths received contract/static inspection, not complete live-model fault injection. File-existence completion checks and process-exit races deserve further isolated tests.
3. Native WebView2 seeks, focus handling, file dialogs, restart persistence and package/source-mode behavior still need actual Windows interaction. Shared logic tests and a browser build are not substitutes.
4. Whole DEV multi-chunk working-set baselines, worker release after interruption and real GPU resource trends remain unmeasured because the RAM guard denied startup. No memory leak is asserted from available-RAM fluctuation alone.

Gates remain:

- Research: `HIT_EVENT_V0_3_CONFIG_FROZEN`.
- Hit product: `HIT_EVENT_V0_2_PARTIAL`.
- Video Evidence: `VIDEO_EVIDENCE_REVIEW_PARTIAL` / `MANUAL_GUI_CHECK_REQUIRED`.
- Long video: `LONG_VIDEO_RESOURCE_PARTIAL` / `RESOURCE_VALIDATION_INCOMPLETE`.

## Three next priorities

1. Native Video Evidence review acceptance on an authorized video: correct visual seek, confirm/reject/correct, current-page navigation, restart and exports. Use the existing isolated manual QA checklist.
2. Once the resource guard permits startup, controlled DEV multi-chunk inference plus forced interruption/resume and working-set trend measurements. GAME_5 is not automatically resumed.
3. Bring remaining short-clip/model-worker artifact completion and corruption handling up to the verified chunk standard without changing frozen inference semantics.
