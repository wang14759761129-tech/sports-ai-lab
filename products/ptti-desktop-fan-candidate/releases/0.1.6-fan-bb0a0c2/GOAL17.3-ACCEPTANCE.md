# GOAL17.3 Desktop Fan acceptance

状态：独立 Fan 候选可用；正式激活与 R4 联动保持 BLOCKED。

推荐版本：`0.1.6-fan-bb0a0c2`。直接打开：
`<LOCAL_USER_ROOT>\PTTI\Candidates\GOAL17\0.1.6-fan-bb0a0c2\host\PTTI-Desktop-Fan.exe`

该 EXE 默认使用 4202 和独立 QA 配置，无需 4183 Vite。当前保留单实例 PID 7208。关闭后重开同一 EXE 会复用该 QA 配置；没有导入、同步或修改生产收藏与笔记。

## 固定版本与完整性

- San：`bb0a0c2a5558ff9424e4d89f0eb0724cd77d5284`，构建前后源码树干净。
- 发布清单 SHA-256：`7ae35d13aee3161d6533e937f1b88f4f26f5fdd60b81182a09f520c2a6f28adf`。
- Desktop EXE SHA-256：`c24791e63cf6d4d28f365cc0afa0fabe3535b6033068b3a47f5a24028bdff623`。
- Web 静态目录 SHA-256：`d0b145e6e33836dc34d74953b091f6ccbb832170446fdb25103493700b3e6624`（对排序的 relative-path/SHA-256 JSON 取 SHA-256）。独立 Vite 生产构建与 San dist 的 29 个文件逐字节一致。
- `184` 个打包文件全部校验 PASS；完整逐文件清单见 `release.json`。EXE 为未签名候选。
- Main 比赛基包：`1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930`，GOAL17 比赛增量：`6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a`。
- Main 媒体基包：`c05491a64f59ac922d2d85d081eccf3b2853f717ece82c8bcfa3d05608f2c004`，GOAL17 照片增量：`6afb03bcc99cefaca7d8ca26005b728162fe878317e217bd705a9253fd067dc9`。
- 批准媒体索引：`998acd8bf033bd2c19dcc042ce8b8f682c493261de513c9c816b54dceb889a10`；12 个 WebP 的完整 SHA 见 `media-sha256.json`。

## 实机结果

| 项目 | 结果与证据边界 |
|---|---|
| 最终 0.1.6 启动、首页、七场赛事卡片 | PASS。`24-final-016-home.png`、`25-final-016-match-catalog-top.png`、`26-final-016-match-catalog-doha.png` |
| 17 条来源 | 实际页面显示 17 条来源 PASS；17 条逐一打开 NOT_TESTED。 |
| 六位球员资料照片、加载、署名 | GUI PASS，截图 03–08。拍摄于 0.1.5；0.1.6 复用逐字节相同的 Web 构建，仅修正宿主下载配置。 |
| 王楚钦、孙颖莎、Félix 新照片限制 | 孙颖莎保持 249px 紧凑显示；Félix 保留四人完整场景及上下文署名；王楚钦保留历史资料说明。 |
| 首页、比赛封面与球星推荐卡 | 实际可见区域使用原创视觉。静态检查确认真实照片只在批准球员资料详情页调用；林诗栋和蒯曼保持原创视觉。 |
| 两条新增 Doha 路由 | 实际点击到观看页并显示 `ywX9mUJ8NtI` / `Kbhf47vb3eE` 正确目标 PASS。第三方浏览器打开和播放 NOT_TESTED。 |
| 滚动、导航、返回 | PASS；包括赛事横向滚动和资料页返回。 |
| 窗口布局 | 默认尺寸、最大化渲染 PASS；更窄尺寸拖动未成功形成不同尺寸，标 NOT_TESTED。 |
| QA 收藏、关注、笔记 | 0.1.5 → 0.1.6 保留 PASS；0.1.6 正常关闭重开后仍为 1/1/1 PASS。截图 22–23。 |
| JSON 备份 | 0.1.5 实机发现下载被默认禁止，FAIL 已保留；0.1.6 启用原生保存对话框，实际导出 601 字节，解析/序列化往返 PASS。GUI 导入 NOT_TESTED。 |
| R4 与正式选择器 | 保留入口，宿主在调用选择器和数据库之前返回待审批。Fan → R4 → 返回 BLOCKED。 |

QA 导出文件：`<LOCAL_USER_ROOT>\Downloads\ptti-fan-local-backup.json`，SHA-256 `f1f841a9e00d6a59debfecef164997da29ae3d4cc0a9070158f2dc72db017540`；只含本轮合成测试记录。副本在 artifacts/GOAL17.3/qa-backup-016.json。

## 保护与回退

0.1.3、0.1.4 完整文件校验 PASS，0.1.5 目录保留。没有覆盖运行目录。正式选择器 SHA 保持 `277069C5…E4C3BF2B1`，Native current-preview.json SHA 保持 `B6E7E996…1B424EA9`。4174 初始/最终均无监听；4183 始终为 PID 28932。4200/4201 在用户释放资源期间由有监听变为无监听，本轮未关闭它们。

候选使用 `%TEMP%\PTTI-GOAL16-DesktopFan-QA\Port-4202\WebView2`，正式 WebView2 配置、数据库、媒体、accepted release 和 active pointer 均未修改。资源守卫保持 2.5 GiB；实际启动前自然空闲大于 10 秒。只正常关闭了本轮新建的 QA 窗口。

回退时正常关闭新候选，独立打开保留的 GOAL16 0.1.4；不要同时抢占端口，不删除任何配置。跨 origin/profile 不会自动同步数据，需用户自行审核 JSON 后迁移。正式入口仍需受支持的审批渠道；GOAL16.7 审批包未变，本轮没有重试被策略拒绝的原子替换。

截图目录：`C:\PTTI-Worktrees\ptti-goal16-desktop-candidate\products\ptti-desktop-fan-candidate\artifacts\GOAL17.3\screenshots`。`acceptance.json` 与 `evidence-index.json` 提供逐项状态和证据 SHA。剩余 NOT_TESTED 不构成原生或第三方播放成功声明。
