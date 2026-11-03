# R4 女双专项复核

## 复现与根因
当前 R4 e93f208 的隔离数据库含 18 条公开来源，其中 WD 三条。默认 Preview 和临时原生 QA 库均含三条；从默认库复制出的 TEST 库调用 /api/video-evidence/library 返回 200，WD 恰好三条。前端女双筛选实际展示三条，分页不隐藏它们。没有复现分类映射或内容丢失。
本轮开始未发现正在运行的 PTTI 原生进程，58563、60472 浏览器标签是旧连接，不能作为活动窗口或当前数据库依据。
观看可用性：一条地区受限；一条先出现两段广告，需要使用平台正常提供的跳过按钮才能进入正片。不能证明这就是用户此前操作的全部原因，但已证实并非缺少 WD 记录。

## 实际观看
- O241nV8y4Dc：World Table Tennis，Nagasaki/Shin vs Diaconu/Xiao，WD SF Singapore 2026；官方页正片 5.717423 → 17.399361s，902.881s。四名球员比赛画面可见，BROWSER_IAB，非 PTTI 内播。
- ekvDMPZDF4o：World Table Tennis，Sato/Hashimoto vs Qian/Chen，WD SF Fukuoka 2024；正片起始画面 → 7.289547s，1785.321s，BROWSER_IAB。
- gxLOCVeMCM0：World Table Tennis，Choi/Shin vs Harimoto/Odo，WD Final Ljubljana 2025；官方页明确国家/地区禁止播放。保留记录与历史。
- 东京电视台官方 WD 目录可访问，其官方半决赛页面为 https://www.tv-tokyo.co.jp/wttc2025/movies/wd/detail.html?movid=rIQGl5_irSE 。发布者为已验证的テレ東卓球チャンネル，标题声称フルマッチ；对应 https://www.youtube.com/watch?v=rIQGl5_irSE 在本次会话受地区限制。不新增不可播放内容凑数，不授予 PTTI 嵌入权。

## 修复与隔离
追加三条 WD 官方页复核记录，保留原始 payload 于 evidence_audit，重复应用不追加重复审计。只允许临时 QA repository 执行。两个已知隔离 R4 Preview 数据库分别先备份，再通过临时副本更新，完整性检查 ok。其他分类、收藏、录像、时间轴不变。
实际可观看 WD：官方页短段已核验 2；PTTI 内播 0；原生 Windows 女双播放本轮未验收；已核实完整比赛 0。总数仍 3，不修改前三类别。
没有 UI/播放器代码变化，不需重构或重打 EXE；现有 R4 重开读取已更新的 QA 数据即可。浏览器宿主中已验证女双三张卡片及正确官方链接；点击外链后的系统浏览器目的窗口没有被自动枚举，不声称原生外链验收通过。

## 测试
Python 13 passed（新审计幂等/隔离/分类保留 + 官方外链安全）；前端 28 passed；py_compile 与 git diff --check 通过。本轮没有重新运行全量回归或打包。
冻结研究配置、Production DB、官方 TEST、GAME_5 未访问或修改。Gate 保持 PARTIAL；原生女双点击/播放仍 MANUAL_GUI_CHECK_REQUIRED。
