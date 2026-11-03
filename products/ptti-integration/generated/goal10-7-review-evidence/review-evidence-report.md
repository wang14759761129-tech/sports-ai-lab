# PTTI 单局复盘证据摘要

> **来源状态：SIMULATED_ONLY。** 本报告使用模拟逐分数据，仅用于验证报告流程。

- 比赛 ID：`SIMULATED_ONLY:review-targets-11-8`
- 数据集 ID：`SIMULATED_ONLY:review-targets-dataset`
- 局号：1；录入点数：19；A:B = 11:8（按逐分序列达到规则终局）
- 输入版本：`ptti.quick-annotation/0.2`；统计版本：`ptti.quick-annotation-stats/0.1`；Review Targets：`ptti.review-targets/0.1`
- 生成时间（UTC）：`2026-10-15T04:25:29Z`
- Canonical SHA-256：`ac38316ea8dd90fb82ecf9fce565e2fe9ec2e3166e90250ae535e138ca7bdad5`
- 原始输入字节 SHA-256：`f77471f5e572242f9308853cfbb55d685739fdec6da6075edc4332e1f88d8c45`（仅证明字节身份）

## 得分与发球

已知得分统计包含没有视频时间的记录；N 为胜者已知的记录数。

| 输入角色 | 得分 | N | 未知胜者 |
|---|---:|---:|---:|
| A（player） | 11 胜 / 8 负 | 19 | 0 |
| B（opponent） | 8 胜 / 11 负 | 19 | 0 |

发球侧依据：`RULE_DERIVED_FROM_DECLARED_GAME_START_AND_FIRST_SERVER`。显式 UNKNOWN 发球方有 19/19 条；在完整开局声明和首发球方已知时由既有规则适配器推导轮换。

| 发球角色 | 得分 / 失分 | 有效发球分母 N | 未知 / 排除 |
|---|---:|---:|---:|
| A（player） | 6 / 4 | 10 | 0 / 9 |
| B（opponent） | 4 / 5 | 9 | 0 / 10 |

发球分母仅含该角色发球且胜者已知的逐分；发球结果不是对发球技术的独立视频观察。

## 人工观察的回合阶段

N 为该阶段中胜者已知的记录数。UNKNOWN 阶段不并入已观察阶段。

| 阶段 | A 胜/负/N | B 胜/负/N | 该组 UNKNOWN |
|---|---:|---:|---:|
| 1–2板 | 11/0/11 | 0/11/11 | 2 |
| 3–4板 | 0/3/3 | 3/0/3 | 2 |
| 5板及以上 | 0/3/3 | 3/0/3 | 2 |

每个表格指标的 `valid/won/lost/unknown/excluded` 完整 point_id 分区见机器报告 `sample.score_by_role`、`sample.service_by_role` 与 `sample.observed_rally_stages`。

UNKNOWN 阶段：2 条（SIMULATED_ONLY%3Areview-targets-11-8/g01/p014, SIMULATED_ONLY%3Areview-targets-11-8/g01/p016），范围为全部输入记录。各阶段的 unknown_count 不可跨组相加。

## 值得人工回看的记录

### B（opponent）｜1–2板

已观察到 11 次失分；该组已知胜负分母 N=11。这是单局描述，不能代表长期倾向。

完整逐分 ID：

- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p001`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p003`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p005`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p007`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p009`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p011`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p013`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p015`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p017`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p018`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p019`

证据：`SIMULATED_ONLY`；播放资格：`NOT_EVALUATED_CURRENT_SESSION`。这些 ID 是待核对记录，尚未确认对应片段可播放。

建议对照对应回合；本报告不推断具体技术、失误原因或训练处方。

### A（player）｜3–4板

已观察到 3 次失分；该组已知胜负分母 N=3。样本不足（N<5），不能据此判断长期倾向。

完整逐分 ID：

- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p002`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p004`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p006`

证据：`SIMULATED_ONLY`；播放资格：`NOT_EVALUATED_CURRENT_SESSION`。这些 ID 是待核对记录，尚未确认对应片段可播放。

建议对照对应回合；本报告不推断具体技术、失误原因或训练处方。

## 时间与证据边界

双方时间边界通过用户报告时长范围检查：12/19；缺少边界：7/19。这些时间仍是 UNBOUND。
有范围检查记录的完整 point IDs：

- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p001`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p002`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p003`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p004`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p005`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p006`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p007`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p008`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p009`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p010`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p011`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p012`

缺少时间边界的完整 point IDs：

- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p013`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p014`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p015`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p016`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p017`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p018`
- `SIMULATED_ONLY%3Areview-targets-11-8/g01/p019`

来源 ID：`未绑定（null）`；版权：`UNKNOWN`；时间轴：`未绑定（null）`；Vision：`NOT_TESTED`；播放资格：`NOT_EVALUATED_CURRENT_SESSION`。

小样本提示阈值为 N<5，是可配置展示提醒，不是统计显著性检验。

报告不包含视频字节或本机路径。A/B 是输入角色，不是已核实运动员身份；SIMULATED_ONLY 不代表真实比赛分析。
