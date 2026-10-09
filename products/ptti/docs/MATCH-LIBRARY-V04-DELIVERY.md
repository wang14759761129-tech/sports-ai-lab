# Match Library v0.4 Milestone 1 交付验收（2026-10-09）

## 用户实际可见
首页为视频优先目录；16名职业运动员、6场真实来源快照；运动员ID关联比赛。王楚钦页面原生查看到2场比赛。职业可播放0场、仅资料6场，均未取得本程序内播视频许可。QA已登记1份12分18.325秒的完整研究录像（Extended OpenTTGames TRAIN game_1），显著标记CC BY-NC-SA 4.0 / 非商业，不绑定无关职业比赛、不随软件分发。

## 自动化与原生证据
Python最终完整回归493 passed / 0 failed / 0 skipped，303.38秒；1条既有Starlette/httpx警告。前端逻辑最终9 passed / 0 failed；TypeScript/Vite构建通过；184个tracked Python源码编译通过，pip check / git diff --check通过。Ruff/uv未安装，不假定其它工作区环境。
真实QA文件夹：C:\Users\wang\AppData\Local\Temp\PTTI-MatchLibrary-v04-QA-zaxpgnqj\合法研究录像。NTFS硬链接只增加本机目录引用，未复制5.57GB视频；源码哈希1297b3db91f2e3e160337643695dff07eabf9785ea2d88c2f7b59687ba511148验证一致。
原生实际点击：启动、首页、引导、文件夹登记面板/系统文件夹选择器打开与取消；索引后的独立录像“确认并观看”；原始视频播放/暂停；运动员搜索与比赛目录。真实画面已播放至约65秒，后续最终构建保留视频优先说明与默认折叠AI。
文件夹首次索引启动使用打包API准备（明确不是原生选择器操作）；Windows选择器真正选定目录因工具缓存控件问题未完整验证。不能宣称完整真人验收。
重启恢复：最新版原生窗口响应，QA库environment=TEST，录像、来源、扫描记录、最近打开时间均恢复。未进行严格逐帧定位误差或真人效率实验；不宣称节省90%时间。

## 构建与资源
构建commit：e0217c73d578ac772c9d7236ca98fed1b4e4ccaf，source_tree_dirty=false；最新文档提交可能领先于构建，但代码来源以上述commit为准。
EXE：C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI-Dev\preview-builds\match-library-v04-e0217c73d5\dist\PTTI-Match-Library-v0.4-Preview\PTTI-Match-Library-v0.4-Preview.exe
SHA256：4b0197d032b377f93245b2abeada76e767f2e2f3fdc8f90c11dc5e422f54fda0
EXE 8056375 bytes，完整目录 496718093 bytes。保留_internal，依赖系统WebView2。无视频、DB、模型权重；旧Preview保持。
最终受监控构建PASS，采样构建进程树RSS最高201,920,512 bytes；起步可用RAM须>=2GiB，运行中低于1.5GiB停止，未降低保护。原生播放另一次采样EXE RSS190,992,384 / USS124,948,480 bytes，WebView2子进程RSS合计504,143,872 bytes；这些是离散采样，不是完整峰值或泄漏认证。没有运行GPU模型。闭合旧QA窗口后对应进程已退出；没有停止用户其它应用。

## 完成范围与Gate
Milestone1代码、自动回归和Windows构建已交付；原生选目录与真人完整核心旅程待验收。
MATCH_LIBRARY_MILESTONE1_PARTIAL / MANUAL_GUI_CHECK_REQUIRED。
DESKTOP_INTEGRATION_BUILD_VERIFIED；研究仍HIT_EVENT_V0_3_CONFIG_FROZEN，Hit产品仍HIT_EVENT_V0_2_PARTIAL。
未实施Milestone2比分搜索、OCR；未实施Milestone3原始/Vision切换或BallTrack Canvas。本轮没有新球路输出、真实km/h、RPM或落点断言。3D/旋转与商业供应商调查延期，未安装新模型。
Production DB、GAME_5 Holdout、官方TEST与冻结算法未参与本轮；冻结配置文件SHA256仍fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3。未合并main/tag/Release。

## 人工验收
本机QA入口：C:\Users\wang\AppData\Local\Temp\PTTI-MatchLibrary-v04-QA-zaxpgnqj\START-QA.cmd；填写C:\Users\wang\AppData\Local\Temp\PTTI-MatchLibrary-v04-QA-zaxpgnqj\ACCEPTANCE.md。需真人在Windows选择已保存的录像文件夹、核对研究权限、重复扫描、确认观看与慢放、退出重开。授权职业媒体不足的任务保持NOT_TESTED/受限，不用研究片段冒充职业录像。
本轮不向外发送任何视频。若分发Preview，只复制完整程序目录；QA媒体/数据库/截图均留在本机。
下一项优先：取得一场明确可本机使用的职业完整录像，并补齐Milestone1真人验收，再进入人工比分索引。
