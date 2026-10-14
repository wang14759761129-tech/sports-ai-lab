# GOAL09：低内存下继续工程，原生启动单独守卫

## 本轮实际增量

1. scripts/windows_rc_diagnostics.py：标准库中文诊断，默认不启动、不创建QA数据库。固定归档Run38410292279的994fac源码和8871bca6 EXE身份，检查全部包文件、额外文件、候选模式、实时RAM及冲突实例。低RAM仍完成诊断，显示缺少的GiB及具体建议。仅显式--launch才进入原有新会话隔离流程，并再次检查进程和2.5GiB守卫。
2. scripts/PTTI-RC-Diagnostics.cmd：可双击的独立诊断入口，默认使用已有项目隔离Python或Codex自带Python；不安装依赖、不改系统环境。结果窗口保留至用户按键关闭，不替换任何桌面图标。Windows实测发现LF批处理解析问题，修正CRLF并加入.gitattributes规则；实际入口回归通过。缺失Python时显示提示并保留窗口。
3. frontend/src/scanPreviewRequest.ts：GET扫描进度的15秒通信超时，覆盖fetch和JSON读取；取消、超时都清理定时器及监听器，不写任务状态，不重新POST导入。后台任务可能仍在工作，界面明确提示并串行重新读取；恢复时清除旧扫描错误，不覆盖其他错误。
4. 日志：%TEMP%/PTTI-Launch-Diagnostics/launch-随机标识.json，只包含版本SHA、状态、错误代码、时间、内存数值、冲突数量及是否启动；不保存路径、媒体、PID、凭据或异常原文。日志不能安全写入时拒绝启动；无法确认启动结果时提示保留现场，不反复启动。

## 双轨规则

A轨：源码、轻量测试、静态检查、诊断及接口准备持续进行；不应用原生启动门槛。
B轨：用户即时授权、完整身份及隔离检查、实时RAM>=2.5GiB、无冲突才启动候选；不自动重试。
本轮未改变打包脚本的既有资源策略；它运行于隔离CI时已有充足资源。没有以RAM不足阻止开发，也没有降低任何既有守卫。

## RAM技术依据与现场

一次只读快照：物理15.797GiB，可用2.746GiB；提交16.29/31.797GiB，未到提交上限。工作集合计包含共享页，不能当成独占物理内存或关闭后的净释放量。
主要工作集：Codex界面约2.86GiB、Node约1.80GiB、Windows服务约1.68GiB、Gemini约0.77GiB、Defender约0.60GiB、codex进程约0.51GiB、OneDrive约0.47GiB、NVIDIA覆盖层约0.44GiB。未发现Python/pytest、PTTI或打包器残留；没有结束任何进程。
没有足够的时间序列、增长复现或回收测量证明内存泄漏。减少同时进行的TS构建、pytest和打包；本轮顺序运行轻量检查，未并行启动额外服务。Web服务及其他工作区保留。
用户可在保存工作后自行退出不用的Gemini（估计0.5–0.75GiB）、NVIDIA覆盖层（0.25–0.4GiB）；OneDrive仅在确认同步完成且暂不需要同步时正常退出（0.3–0.45GiB）。估算不是净释放承诺，不自动操作。
2.5GiB在candidate_qa_launcher.MIN_AVAILABLE_RAM中固定，来源与build_dual_source_v061_preview的保守建议启动余量一致；构建硬运行下限是2GiB。它不是经过普通Cinema、原生GUI或Vision模型各自峰值测量证明的精确需求。保持守卫；以后如评估阈值，必须分别测冷启动/播放/退出/推理峰值及失败条件，不能用无界面健康检查替代。

## 真实结果

- 新增诊断12项测试PASS（包括真实Windows .cmd入口，无EXE执行）。
- 实际诊断及批处理入口PASS：包完整性PASS、冲突0；实测可用1.745GiB、缺0.755GiB，中文提示与脱敏日志成功，候选启动BLOCKED。低于门槛时开发、诊断和测试仍正常完成。
- 前端9个实际组件场景PASS（此前8场景加通信超时、重试、无重扫、过期响应不覆盖、恢复后清除旧错误）。
- TypeScript tsc -b PASS。没有重跑Python全量或已归档版本CI。
- 原失败QA数据库SHA仍为264eb32ff3f9760f6db71e86dd2f0cc04c3d9267c0ccc63584cda05e7d0b9714，未修改数据库或视频。
- 本轮原生启动/播放/算法/截图均NOT_TESTED。

## 使用与下一次集中验收

双击专项worktree下products/ptti/scripts/PTTI-RC-Diagnostics.cmd，只检查并显示结果，不能用旧桌面Candidate QA图标代替。CLI可用现有Python运行scripts/windows_rc_diagnostics.py；默认路径指向Run38410292279候选，--candidate-dir可明确指定待校验目录，身份仍严格固定。
未来获得启动即时授权后，用同一入口的显式--launch启动一份全新OS Temp会话；选择12秒合成视频→读取预览→确认COMPLETED卡片→等用户确认授权登记→播放/暂停/Seek→正常退出及只读完整性检查。失败保留现场，不循环启动。
中文诊断是包外工具，现在即可使用，不必重建994fac候选。新增前端通信超时只在源码，未来新RC才包含它；没有重新打包旧源码的必要。

## 专业分析报告接口边界与协作

预留只读交接字段：target_commit、exe_sha256、source_sha256、rights_status、availability_status、明确分析权限、匹配evidence_id及报告状态。沿用现有视频证据字段和内部QA交接结构；由主Dex确认报告消费接口，不另建重复分析功能。未授权/无匹配可信证据的分析与报告保持NOT_TESTED或禁用；不传绝对媒体路径、数据库、合成素材伪造的真实比赛结果。
主线交接的rc_start_diagnostics.py、collect_rc_diagnostics.ps1、Show-PTTI-RC-Diagnostics.ps1、test_rc_start_diagnostics_goal09.py是未完成草稿，原样保留、不纳入本次提交或测试成绩。其PS5入口已知解析问题不计为可用成果；本轮交付使用独立.cmd入口。
本地仅提交本线路文件；不push、不CI、不运行dev_sync、不改桌面R4/Launcher/正式数据库，不干扰San及主Dex工作区。
