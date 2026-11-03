# Playback Core 浏览器故障诊断卡｜给 San

适用：Web Pro 本地文件播放。固定 Core：`304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`；源码 SHA256：`a59df06b688d75885bfb8ed51364e73edbaedaaa2b3746b5f7fd1d1edf67caf2`。工具/回归基线：`6eb708b1c656585e6040ff8c467c8698e3cc0fed`，21组低资源回归 PASS；这不代表浏览器解码、真实手机视频或原生 R4 验收。

## 发生一次故障时

记录操作顺序和下表信号，保存一次有界记录后取消队列并暂停；不要反复重载覆盖现场。诊断默认关闭，由开发者为单次复现开启，最多20条事件，结束即停止，不上传。正常取消与正常完成不记作媒体故障。

| 现象 | 最少检查与判断 |
| --- | --- |
| 视频加载失败 | 记录 `loadFile()` 返回码、snapshot.status/error.code、readyState、networkState、MediaError.code。`invalid-file-type`/`empty-file` 是选择校验；`file-read-error` 是本地读取/URL/加载失败，不能推断断网；`unsupported-media`/`decode-error` 不能单独证明具体编码不支持或文件损坏。若一直 loading，记录停留时长与是否收到 metadata/canplay，不伪称 Core 有加载超时。 |
| Seek失败 | 记录请求秒数、请求前后当前位置、seeking、返回码及是否收到 seeked。手动 Seek 必须走 `controller.seek()`：合法范围会裁剪并取消旧队列，但同步返回成功不证明画面已更新。队列定位的 `seek-failed`/`seek-timeout` 分开记录；默认等待5000ms，后台调度可能延迟，不保证精确落帧。 |
| 旧队列仍控制位置 | 用本地递增编号区分媒体代次和任务代次；记录取消触发点、task.done 的 status/reason、后续是否又跳转。用户 Seek 为 `manual-seek`；换片为 `video-replaced`；新任务替换为 `playlist-replaced`。边界/Target改变由 San 先 cancel 再更新资格，Core 不会监听外部草稿。仅 pause 不等于 cancel。 |
| 导航重入异常 | 记录路由类别变化、cancel→pause 调用顺序、返回后的任务/播放状态。保留挂载的工作区可以保留媒体和笔记，但不能自动恢复旧队列；用户再次点击 Play 可普通观看。真正卸载时应 cancel、unsubscribe、release。检查旧异步回调是否仍更新新页面状态。 |
| 资源未释放 | 区分“保留挂载并暂停”与“真正 release”。后者检查 src属性已移除、所属URL已撤销、订阅/事件监听已解绑、旧任务已结束；currentSrc更新可能异步，记录观察时点。仅在开发环境已有计数器时记录创建/撤销和订阅/解绑计数。浏览器内存未立即下降不能单独证明泄漏；需要重复同一生命周期后的持续增长证据。 |

## 日志字段白名单

每次复现头部仅记录：San提交、Core提交/源码哈希、浏览器及OS版本、前台/后台标签状态。每条仅记录：相对时间ms、操作名/事件名、路由类别、本地媒体代次/任务代次、status、is_playing、playback_rate、current_time_seconds/duration_seconds（按0.1秒取整，非有限值记null）、playlist.status/current_index/total、error.code、task.done.status/reason，以及相关媒体状态码。需要媒体匹配判断时只记 true/false/unknown。

不要直接序列化 `getSnapshot()`：其中含文件信息。禁止记录文件名、绝对路径、blob/官方URL、文件字节或哈希、完整session_id、point_id、笔记、令牌、视频画面或音频。截图仅在用户同意后裁切/遮盖私人信息；诊断记录由用户主动决定是否分享。诊断用代次编号不代表媒体SHA验证或授权证明。

## 归属与下一轮触发条件

San负责路由、授权/边界资格、数据版本和过期UI回调；Core负责媒体会话、队列、Seek、错误分类和资源生命周期。官方平台登录、地区或网络限制走外链链路，不能归为本地Core解码故障。原生R4另行取证。

只有收到实际浏览器失败证据后再启动Core修复：版本身份＋最短操作顺序＋期望/实际行为＋上述有界日志（有条件时附脱敏截图）。先定位San调用或Core行为；确认可复现P0/P1后做最小修复及对应回归。无失败证据时保持固定Core，待命。
