# CSV 模板：PTTI 新协议 1.0.0-new

文件：`sample/synthetic.csv`。这是合成示例，不能当作真实比赛记录。每行是一分；UTF-8 编码，逗号分隔，表头和枚举值使用英文。历史 v0.3 文件没找到，不保证兼容旧表格。

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
