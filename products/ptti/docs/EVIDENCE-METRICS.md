# Evidence-aware metric audit, analytics 0.1.1

Invalid match-state imports return INVALID_DATA and no saved analysis. Values unavailable under a gate are null, never fake zero. Each rate exposes numerator, denominator, eligible_rows, excluded_rows, unknown, unclear, not_applicable, missing, minimum_denominator, denominator_source and evidence_state. Field summaries retain row-label counts and unresolved conditional eligibility. Old 0.1.0 saved analyses are not rewritten; reimport to apply the new gates.

| Metric | Numerator | Denominator / eligible rows | Exclusions / uncertainty | Minimum |
|---|---|---|---|---|
| Points won | point wins | all validated points | unknown core winner rejects | 1 |
| Serve win | wins on own serve | own service points | unknown core identity rejects | 1 |
| Receive win | wins on opponent serve | opponent service points | unknown core identity rejects | 1 |
| Third-ball attack | confirmed yes | classified yes+no own serves | unknown/unclear/missing excluded, N/A separate | 5 classified |
| Third-ball conversion | final point wins following yes | confirmed yes attacks | unresolved attack eligibility separate, N/A excluded | 5 yes attacks |
| Mean rally | sum numeric contacts | positive numeric contacts | uncertain/missing excluded, N/A outside eligible uncertainty | 5 numeric |
| Short/medium/long | numeric rallies 1–4/5–8/9+ | numeric rallies | same as mean | 5 numeric |
| By server/receiver | wins in group | validated group points | no uncertain core identity accepted | 1/group |
| By serve placement/type | wins in observed category | own serve group | uncertain not a category; field quality gate uses all own serves | 5/group |
| By receive type | wins in observed category | receive group | mapped subtype warnings; uncertainty excluded | 5/group |
| By phase | wins in phase | annotated phase group | missing historical phase never inferred | 5/group |
| Winner/error endings | counts of endings among points won | annotated native winner/error rows | research win/loss not mapped | 1 count, no invented ratio |
| Score progression | confirmed post-point score | every validated point | core unknown rejects, no reconstruction | 1 |
| Runs | consecutive winners | ordered points, reset by game | no missing points filled | 1 |

AVAILABLE means descriptively calculable under the product gate, not scientifically validated. INSUFFICIENT_EVIDENCE means low confirmed count or excessive unresolved evidence. NOT_AVAILABLE means absent field; INVALID_DATA means validation failed.

Tactical metrics additionally require `(unknown+unclear+missing)/eligible ≤30%`. Protocol uncertainty is separately reported as `(unknown+unclear)/eligible`. N/A is excluded from both numerator and denominator and counted separately. Third-ball side/outcome quality denominator uses only confirmed yes attacks; attack unknown/unclear means unresolved eligibility, never an all-point denominator.

Five is a conservative product display threshold, **not a validated scientific sample size**. The 30% guard adopts protocol feasibility caution, not a significance/reliability proof. Facts/interpretations require an available metric. No confidence intervals, significance tests or new tactical analyses are added.
