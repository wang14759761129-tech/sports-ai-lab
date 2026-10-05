# 两种 CSV，不要混用

PTTI 0.1.2 支持原生 1.0.0-new 和研究 Protocol v0.3。sample/synthetic.csv 是原生模板；sample/protocol-v0.3-example.csv 是新生成、发球/比分有效的历史格式合成模板。两者都不是实际比赛证据，导入时请勾选“合成示例”。真实比赛请换成自己的记录。

历史格式每行一分，game_number / point_number 从 1 连续编号；server/receiver/point_winner 使用 player/opponent。导入页面 A 姓名=player、B 姓名=opponent。server_score_before/receiver_score_before 是这一分开始前，按该行发球/接发者视角记录的比分，不是 A/B 固定顺序。适配器通过确认的赢家计算结束后比分。

研究字段允许 unknown（未观察到）、unclear（不清楚）、not_applicable（不适用），保留原值。身份或比分未知无法可靠转换，会拒绝而不是补猜。缺少可选战术字段会提示，不会填成 no 或 0。细分类别合并会明确警告，原值保留在逐分表 source_ 列和导出的 provenance。

没有已确认的第三板进攻机会就不计算转换率；win/loss 不等于 winner/error。video_timestamp/notes 保留，不当作自动视频同步。CSV 行号含表头，首行数据是第 2 行。

完整字段见 DATA-FIELDS.md。以下为原生格式的详细说明（严格原始类别，不接受研究不确定标签）：

# CSV 模板：PTTI 新协议 1.0.0-new

文件：`sample/synthetic.csv`。这是合成示例，不能当作真实比赛记录。每行是一分；UTF-8 编码，逗号分隔，表头和枚举值使用英文。历史 v0.3 已恢复，由专用适配器处理，不覆盖原生字段定义。

| 必填列 | 意义 |
|---|---|
| game | 第几局，从 1 开始，顺序连续 |
| point | 本局第几分，从 1 开始，顺序连续 |
| server | 发球方：A 或 B |
| winner | 得分方：A 或 B |
| score_a | 这一分结束后 A 的局内比分 |
| score_b | 这一分结束后 B 的局内比分 |

球员姓名在导入页面填写；CSV 里用 A/B。每局从 0–0 记录，不能从半局开始；11 分以上领先 2 分才能结束一局。两分换发球，10–10 后一分换。最后一局未结束可以导入，但会提示警告。

```csv
game,point,server,winner,score_a,score_b
1,1,A,A,1,0
1,2,A,B,1,1
1,3,B,A,2,1
```

可选列（不知道就留空，不要猜）：

| 列 | 可用值 |
|---|---|
| rally_length | 含发球的触球次数，正整数 |
| third_ball_attack | yes / no，发球方是否第三板进攻；空值表示未知 |
| serve_placement | short_fh / short_bh / short_middle / long_fh / long_bh / long_middle |
| serve_type | backspin / topspin / sidespin / no_spin / mixed |
| receive_type | push / flick / attack / block / other |
| point_phase | serve / receive / third_ball / rally，决定这一分的阶段 |
| outcome | winner / error，得分结束方式，不表示失误者身份 |

fh=正手，bh=反手；short/long=短/长；backspin=下旋，topspin=上旋，sidespin=侧旋，no_spin=不转，mixed=混合；push=搓，flick=挑/拧，attack=进攻，block=挡，other=其他。

第三板 conversion 是“标注第三板进攻后该分获胜”的比例，不是第三板直接得分率。可选项缺失会降低统计样本量。报错行号包括表头，所以第一个数据行是第 2 行。
