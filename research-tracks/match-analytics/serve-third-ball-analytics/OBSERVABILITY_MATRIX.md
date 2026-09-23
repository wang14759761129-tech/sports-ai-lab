# Observability matrix — Pilot 1B status

**Assessment status:** NOT COMPLETED. Pilot 1B requires complete-point normal-speed viewing and replay. The local video remains present, but the available browser refused the local-file preview under its security policy and explicitly disallowed alternate UI/workaround access. No second visual pass was performed.

The table therefore records only the existing Pilot 1 Mini Pilot baseline. No field receives a Tier A/B/C classification from Pilot 1B. Tier definitions: A = stable during normal playback; B = stable only with pause/replay/slow review; C = not reliable even after replay. Those judgments remain pending.

Uncertainty is `unknown + unclear / eligible observations`; `not_applicable` is excluded from the numerator and denominator. Pilot 1 recorded 10 points. For all rows below the denominator is 10 only where the field applies to every point or eligibility was not separately coded; third-ball applicability was not established, so the rates are provisional row-based rates and cannot distinguish structural non-applicability.

| Field | Current definition | Pilot 1B tier | Pilot 1 points observable / uncertainty | Uncertainty rate | Reason / replay required? | Interim decision |
|---|---|---|---|---:|---|---|
| `match_id` | Match identifier | Not assessed | 10/10 ID rows present | 0% missing | Assigned from project metadata; no replay | Keep |
| `game_number` | Game within match | Not assessed | 10/10 present | 0% missing | Sample boundary supplied; no replay | Keep |
| `point_number` | Ordered point within game | Not assessed | 10/10 sequential IDs | 0% missing | Ordered in the pilot file; no replay | Keep |
| `server` | Serving side | Not assessed | 0/10 identified; 10 unknown | 100% | Serve action not established in prior sampled inspection; replay test pending | Keep; test |
| `receiver` | Receiving side | Not assessed | 0/10 identified; 10 unknown | 100% | Depends on verified server identity; replay test pending | Keep; test |
| `server_score_before` | Server score before point | Not assessed | 0/10; 10 unknown | 100% | Prior file did not encode point-start score sides; replay/checkpoint needed | Keep; test |
| `receiver_score_before` | Receiver score before point | Not assessed | 0/10; 10 unknown | 100% | Prior file did not encode point-start score sides; replay/checkpoint needed | Keep; test |
| `serve_side` | Broad service side | Not assessed | 0/10; 10 unclear | 100% | Prior sampled review insufficient; replay test pending | Keep; test |
| `serve_length` | Short / half-long / long by bounce/end-line definition | Not assessed | 0/10; 10 unclear | 100% | Requires reliable bounce view; replay test pending | Keep; test |
| `serve_location` | Broad landing zone: forehand / middle / backhand | Not assessed | 0/10; 10 unclear | 100% | Requires visible landing/bounce; replay test pending | Keep; test |
| `serve_spin` | Backspin / sidespin / topspin / no-spin / mixed | Not assessed | 0/10; 10 unknown | 100% | Spin was not inferable in prior sampled inspection; replay test pending | Keep in schema; future/specialized observation candidate |
| `receive_type` | First receive action category | Not assessed | 0/10; 10 unclear | 100% | Full point and replay needed to test | Keep; test |
| `receive_location` | Broad receive placement | Not assessed | 0/10; 10 unclear | 100% | Requires visible receiving contact/placement; replay test pending | Keep; test |
| `third_ball_attack` | Server's intentional attacking third contact | Not assessed | 0/10; 10 unclear | 100%* | Eligible denominator not established because point sequence was not recoded | Keep; test eligibility semantics |
| `third_ball_side` | Side used for the third-ball attack | Not assessed | 0/10; 10 unclear | 100%* | Depends on attack eligibility; replay test pending | Keep; test eligibility semantics |
| `third_ball_outcome` | Immediate third-ball result | Not assessed | 0/10; 10 unclear | 100%* | Depends on attack eligibility; replay test pending | Keep; test eligibility semantics |
| `rally_length` | Ball contacts, serve included | Not assessed | 0/10; 10 unknown | 100% | Requires continuous contact tracking; replay test pending | Keep; test |
| `point_winner` | Side winning the point | Not assessed | 10/10 outcomes recorded | 0% unknown in pilot file | Scoreboard transitions were readable during prior sampled inspection; not a Pilot 1B result | Keep |
| `point_outcome` | Perspective-coded win/loss | Not assessed | 10/10 coded | 0% unknown in pilot file | Derived consistently from recorded winner; not a Pilot 1B result | Keep |
| `video_timestamp` | Point start timestamp | Not assessed | 10/10 broad 5-second inspection intervals | Not a missingness measure | Prior entries are score-transition discovery windows, not exact starts | Modify later if exact boundaries can be reviewed |
| `notes` | Short evidence/uncertainty note | Not assessed | 10/10 populated | 0% missing | Captures limits of prior sampled observation | Keep |

`*` These 100% values describe the prior CSV's `unclear` labels, not an eligible-opportunity rate. A Pilot 1B review must first decide whether a third-ball opportunity exists, then exclude `not_applicable` observations from field uncertainty calculations.

**Conclusion:** Pilot 1B supplies no observed Tier A/B/C classifications. Do not treat this matrix as evidence that replay will or will not resolve any field. Do not expand the sample.
