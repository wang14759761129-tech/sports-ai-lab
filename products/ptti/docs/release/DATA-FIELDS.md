# 数据字段与证据：PTTI 0.1.2

一分一行，UTF-8。原生格式：game、point、server/winner(A/B)、score_a/score_b（结束后比分）。可选 rally_length、third_ball_attack、serve_placement、serve_type、receive_type、point_phase、outcome 使用 CSV-TEMPLATE 中的原生枚举。

历史 Protocol v0.3 的 21 字段：match_id、game_number、point_number、server、receiver、server_score_before、receiver_score_before、serve_side、serve_length、serve_location、serve_spin、receive_type、receive_location、third_ball_attack、third_ball_side、third_ball_outcome、rally_length、point_winner、point_outcome、video_timestamp、notes。

历史 player 是导入页面球员 A，opponent 是球员 B。比分是本分开始前、该行发球者和接发者的各自比分；不会把发球者一律当 A。unknown=未观察到，unclear=不清楚，not_applicable=不适用；原始值和注释都保留。未知身份/比分会拒绝，不补猜。

发球短/长加正手/中路/反手区可转换六区；half_long 无对应产品类别，警告并保留原值。接发 chiquita→flick，drive/loop→attack，long_push/short_touch→push 会合并细类并警告。win/loss 不是 winner/error，不作此映射。第三板即时 successful 不是最终该分获胜，不能混用。

数据显示状态：数据充足=已记录样本可描述，并不代表科学验证；证据不足=样本太少或未知过多；暂无该字段=未提供；无法可靠计算=数据无效。战术分母排除未知/不清楚/不适用；不适用独立计数。第三板条件字段仅以已确认 yes 进攻为分母，机会未确认独立报告。样本门槛 5 是产品保守显示规则，不是科学结论。

Pilot 1C 仅支持该 10 分的比赛状态描述；战术证据不足。Pilot 2 尚未开始。软件数据不能替代测量验证。
