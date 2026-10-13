# Cinema 单文件扫描完成后预览恢复修复

故障候选源码：550a410e7fc71eb425f39a618277f209515a4ef8。
EXE：a9928b798bda83e9a5dc5a8f111be503c4cd48723ffd73a65eb9eb721f7d0b23。
本轮没有运行或修改该 EXE，也没有覆盖故障现场。

## 真实证据与根因

- 原 QA 数据库只读 quick_check=ok，1 条 COMPLETED 扫描、1 条 REVIEW_REQUIRED 合成视频候选、无扫描错误；0 已登记录像、0 用户比赛。6 条预置职业比赛资料并非本次导入成果。
- 数据库读取前后 SHA256 均为 264eb32ff3f9760f6db71e86dd2f0cc04c3d9267c0ccc63584cda05e7d0b9714。原 MP4 可访问，当前字节与扫描 SHA 一致；未修改原库或素材。
- 在 OS Temp 隔离数据库副本上，真实 API /library/folders 返回 HTTP 200、数组中含完整 COMPLETED/candidates；两次读取耗时 0.086s、0.065s。/library 汇总返回 HTTP 200，耗时 3.240s。字段与前端一致，待审核候选没有被权限过滤排除。
- 旧 MatchVideoLibrary 每 2s 同时重新请求汇总与扫描列表。Promise.all 等待慢汇总后才提交扫描状态；每次新请求又递增 generation，使未完成的旧响应作废。当汇总持续超过 2s，成功返回的 COMPLETED 也持续被丢弃，页面停留在 RUNNING。
- 实际 TSX 组件回归使用现场脱敏候选和确定性延迟，修复前退出码 1，断言“COMPLETED + REVIEW_REQUIRED 应显示预览”失败；修复后同一断言通过。
- 原生日志只记录 server_started、隔离数据库与版本身份，没有逐条 Cinema HTTP 时间线。因此上述耗时是现场副本实测，不冒充昨晚原生请求抓包；新修复尚未实机验证。

## 最小修复

仅修改 MatchVideoLibrary 的请求调度，不改后端路径、SHA、来源许可、分析 Gate 或数据库守卫：

1. 扫描列表独立提交，不等待汇总；扫描轮询不再重复拉取整个比赛库。
2. 串行轮询，响应结束后再安排下一次；终态结束轮询。
3. 页面生命周期、扫描请求和汇总请求分别判定时效；页面离开时取消轮询请求，过期状态和错误不写回当前页面。
4. 保留原有预览恢复、人工授权及登记锁；没有明确确认不会自动登记。异常请求显示错误，不冒充空列表。

## 实际测试

| 检查 | 结果 |
|---|---|
| 前端原有扫描/恢复/授权断言 | 20 PASS |
| 实际 TSX 组件状态与请求链 | 8 场景 PASS |
| Vision 来源及分析 Gate 专项 | PASS |
| TypeScript tsc -b | PASS |
| Python 视频库和数据库隔离回归 | 54 PASS，155.93s |
| 上轮独立 RC 启动器及检出换行兼容回归 | 8 PASS |
| 新代码 Windows 构建、原生 UI、播放 | NOT_TESTED |

8 场景覆盖：慢汇总、页面刷新恢复、慢扫描请求串行化、FAILED/文件失效、过期响应及离开、HTTP 403、单文件选择及人工授权/路径拒绝/重复点击、目录导入同链路。组件测试运行真实组件源码及渲染分支，用确定性 hook/timer host 驱动，不是 Windows GUI 或媒体解码验收。Python 保留单文件、路径变化、权限、重复登记和数据库保护负例；仅有已有 Starlette/httpx 弃用警告。

## 文件与构建准备

产品修复：frontend/src/MatchVideoLibrary.tsx。
回归及 CI 接入：frontend/scripts/test-library-scan-recovery.mjs、frontend/package.json；沿用现有 test:folder-scan-status 门槛，无工作流改动。
现场脱敏证据与测试记录：CINEMA_GOAL06_1_EVIDENCE.json、CINEMA_GOAL06_1_PYTEST.xml。
同批提交保留上轮已准备、未提交的 scripts/alpha_rc_qa_launcher.py 和 tests/test_alpha_rc_qa_launcher_unittest.py；补充文本校验的 LF/CRLF 兼容测试，避免不同 Git 检出换行导致启动器预检失败。它们仍只绑定现有 550a410 候选，不会自动接受未来新包。

已具备请求下一次 Windows RC 构建授权的源码条件。下一步需要批准精确的新提交推送及一次 CI；构建后重新绑定新包哈希，再另行授权原生验收。现有 EXE 不包含本次修复。

没有 push、CI、安装、原生启动、main 合并、桌面入口更新或生产数据库访问。主Dex CSS、San Web 工作区未改。未执行会安装/激活的 dev_sync，遵循本轮用户禁止部署的范围。
状态：CODE_COMMITTED（以 Git 提交为准）、TESTS_PASSED（上述范围）、DESKTOP_UPDATE_PENDING、NATIVE_GUI_VERIFIED=NOT_TESTED。
