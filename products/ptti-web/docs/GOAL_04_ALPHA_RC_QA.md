# GOAL 04 · 球迷端 Alpha RC

2026-10-13；基线 `46f1826d80edf19147cc492e26c5461048841608`，起始工作树干净。

## 可演示观看路径

打开 http://127.0.0.1:4174/ → 搜索樊振东/Fan Zhendong → 男单/已核验官方视频 → 对林高远的详情 → 看来源类型和画面核验范围 → 前往准确的官方YouTube单场页 → 返回PTTI → 下载PNG信息卡并复制分享文案/页面链接 → 再次打开深链恢复同一场比赛 → 本机反馈/主动导出JSON。

直达：http://127.0.0.1:4174/?match=doha-2023-ms-sf-fan-lin 。localhost链接不能使异地用户访问网站；分享文案另包含官方原始地址，可按平台合法条件打开。没有自动发送给其他人。

## 实际实现

- `MatchDetail.tsx` 独立详情组件：比赛双方、赛事和项目/轮次形成首屏身份块；桌面并排显示官方来源面板，手机纵向排版。
- 中文使用既有搜索别名映射展示运动员中文名，并保留英文原名，不制造身份ID。
- 来源类型与核验状态在观看按钮之前；长证据/地区/嵌入说明用原生details展开，减少阅读负担。报道按钮明确“非视频”，无单场地址不生成播放入口。
- 分享信息卡使用PTTI文字品牌、fixture数据，PNG 1200×675。无肖像、WTT封面、下载视频、外部字体/图片；Canvas直接绘制，CSP无需放宽。
- 复制文案包含官方地址、比赛页面深链和核验范围；复制受限时可手动选择文案，图片导出失败时明确提示改用文字/链接。
- 修复分享后刷新可能停留在页面下方的问题；恢复选中比赛时焦点到标题并回到首屏。
- 只读v0.2消费边界和字段说明见 [对接文档](GOAL_04_V02_CONSUMER.md)。尚未替换当前四场fixture数据源，review不会由URL启用或进入public/dist。

## 实际测试结果

| 检查 | 结果 |
| --- | --- |
| TypeScript / Vite production build | PASS |
| check:reproducible | 同一已安装工具链连续两次构建，5个文件SHA-256完全一致 |
| check:sources | 111项PASS，四场原始fixture/URL/版权状态未改 |
| check:feedback / check:watch-filter / check:match-location | PASS |
| check:rc | 分享文案范围、v0.2精确版本、权限UNKNOWN、显式本地review、输入不变、断裂引用、本地资产拒绝及Native未升级PASS |
| 实际producer快照消费 | 采用486661b原消费者进行Schema验证与投影；review4场4来源0资产/public0；Web边界保持上述结果 |
| check:alpha | HTTP/JSON/结构/缺字段错误恢复（中英文8组）、禁用存储、键盘、反馈无网络写入PASS |
| 390 / 768 / 1440 × zh-CN / en | 六组PASS：双语姓名搜索、筛选、空结果、深链/刷新/历史、语言保持、复制正确链接/分享文案/手动复制、PNG真实下载（签名与1200×675验证）、44px可见操作、16:9列表占位、无水平溢出 |
| 首屏官方入口 | 六组中按钮y坐标非负且低于650px；修复英文手机按钮偏低以及刷新滚动恢复问题后PASS |
| check:preview | 5静态文件约317.1KiB；_headers存在；无数据库、视频、凭据标记、未许可图片或review样例 |
| CSP生产模拟 | 本机loopback静态服务器应用_headers后，六组交互与Canvas PNG导出正常；真实Cloudflare HTTP仍NOT_TESTED |
| git diff --check | PASS |

测试使用独立浏览器上下文，未写入真实用户现有反馈。截图实际保存并查看：`.alpha-qa/rc/detail-390.png`、`detail-768.png`、`detail-1440.png`、`fan-lin-share.png`。这些开发QA产物在本Web目录被忽略，未进入提交或部署包。

运行：

```powershell
npm run build
npm run check:rc
npm run check:sources
npm run check:feedback
npm run check:watch-filter
npm run check:match-location
npm run check:preview
npm run check:reproducible
$env:PTTI_PLAYWRIGHT_MODULE = '<已安装Playwright index.mjs绝对路径>'
npm run check:alpha
```

本机开发4174保留运行；测试生产服务器只在临时loopback端口启动并自行关闭。没有公开部署、推送、触发CI、跨分支合并或Windows候选操作。

## 真实用户及发布Gate

两位球友的 [三分钟独立任务与空白记录](GOAL_04_TWO_FAN_PILOT.md) 已准备，实际招募/试用 **0/2**；创始人验收仍0。测试不是分享意愿或留存证明。

外部视频本轮没有重新播放核验；旧画面证据日期仍2026-10-12。声音、跨地区、嵌入和Windows Native/Vision均未验证。v0.2快照权限UNKNOWN导致公开目录为空；没有任何ALLOWED由San补写。主Dex仍需提供当前冻结版本、正式投影、稳定身份映射和ARTICLE分类。
