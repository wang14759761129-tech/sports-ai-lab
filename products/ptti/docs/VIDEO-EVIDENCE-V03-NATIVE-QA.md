# PTTI 原生 Windows 人工验收（约 8–10 分钟）

版本：0.3-video-evidence-preview；构建提交：98101770ae6221208e3503afcc6609714a7ebca5。
启动：双击本目录 START-QA.cmd。若已有同版本窗口，先退出再启动，避免多实例。
QA 数据库：C:\Users\wang\AppData\Local\Temp\PTTI-v03-QA-20261008-183456\matches.db。不要删除已有保存数据。
视频：C:\Users\wang\AppData\Local\PTTI-Dev\research-datasets\ExtendedOpenTTGames\videos\train\game_1.mp4
AI 包：C:\Users\wang\AppData\Local\Temp\PTTI-v03-QA-20261008-183456\game_1-v03-d.jsonl。
截图目录：C:\Users\wang\AppData\Local\Temp\PTTI-v03-QA-20261008-183456\screenshots。
视频仅限本机非商业研究 QA，不包含在可分发程序目录中。

所有结果由本人填写 PASS / FAIL / NOT_TESTED，未填不算通过。

|分钟|操作|预期|实际结果与备注|
|---|---|---|---|
|0–1|确认窗口标题 v0.3 / 98101770ae。导入视频 → 选择本机视频（可取消后重选），选择上述 MP4；权限选研究素材，勾选许可后登记|Windows 文件选择器工作，进入真实画面|NOT_TESTED：___|
|1–2|播放/暂停；跳到 60 秒；倍速改 0.5×；前后两秒|画面确实改变且能慢放；数字不是唯一证据|NOT_TESTED：___|
|2–3|选择结果包并导入。若已有暂停任务，恢复导入；重复导入相同包|哈希匹配，0 导入错误；同一候选不重复|NOT_TESTED：___|
|3–5|点击候选，播放前后上下文；确认一条、否决另一条；改一个候选时间与 UNKNOWN/Near/Far|视频跳到事件附近；原始时间、人工时间及历史共存；未知不自动猜测|NOT_TESTED：___|
|5–7|标记一个关键片段并保存；再存第二段；选两段存专题，连续播放|片段边界停止/切换正确，无错误串播|NOT_TESTED：___|
|7–8|导出 JSON/HTML/CSV，打开 HTML，查看修改历史|三份报告可读取，过滤记录未当成人工确认|NOT_TESTED：___|
|8–10|完全关闭，再用 START-QA.cmd 启动，找回专题与候选修改|已保存内容和历史恢复，旧 Production 数据不参与|NOT_TESTED：___|

严格逐帧定位尚未认证；按帧率近似移动不等于源 PTS 精确定位。发现错误时记下视频时间、操作和截图。
只读诊断：使用 diagnose-readonly.ps1，参数 ExpectedExePath 指向上述 EXE，ExpectedDatabasePath 指向本 QA 库，ExpectedCommit=98101770ae6221208e3503afcc6609714a7ebca5。此脚本不修复或删除数据。

验收人：___ 日期：___ 总体：PASS / FAIL / NOT_TESTED
