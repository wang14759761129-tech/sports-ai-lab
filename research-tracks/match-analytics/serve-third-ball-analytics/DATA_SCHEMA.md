# Point-level data schema

**Unit of analysis:** one point = one row.

All categorical fields allow `unknown`, `unclear`, or `not_applicable` where observation is not reliable. **Never guess.**

| Variable | Meaning | Type | Allowed values / example | Why it matters |
|---|---|---|---|---|
| `match_id` | Match identifier | text | `pilot-001` | Groups points by match |
| `game_number` | Game within match | integer | `1` | Game context |
| `point_number` | Point within game | integer | `4` | Reproducible order |
| `server` | Serving side | category | `player`, `opponent`, `unknown` | Defines perspective |
| `receiver` | Receiving side | category | `player`, `opponent`, `unknown` | Defines perspective |
| `server_score_before` | Server score before point | integer/category | `6` or `unknown` | Score pressure |
| `receiver_score_before` | Receiver score before point | integer/category | `5` or `unknown` | Score pressure |
| `serve_side` | Broad service side | category | `forehand`, `backhand`, `unknown` | Tactical context |
| `serve_length` | First/second-bounce length class | category | `short`, `half_long`, `long`, `unclear` | Main exposure |
| `serve_location` | Broad landing zone | category | `forehand`, `middle`, `backhand`, `unknown` | Main exposure |
| `serve_spin` | Observable spin category | category | `backspin`, `sidespin`, `topspin`, `no_spin`, `mixed`, `unknown` | Spin context |
| `receive_type` | First receive action | category | `push`, `flick`, `chiquita`, `drive`, `loop`, `long_push`, `short_touch`, `other`, `unclear` | Immediate response |
| `receive_location` | Broad receive placement | category | `forehand`, `middle`, `backhand`, `unknown` | Placement context |
| `third_ball_attack` | Server's third-ball attack attempt | category | `yes`, `no`, `unclear`, `not_applicable` | Primary outcome process |
| `third_ball_side` | Side used for attack | category | `forehand`, `backhand`, `other`, `unknown`, `not_applicable` | Attack context |
| `third_ball_outcome` | Immediate third-ball outcome | category | `successful`, `unsuccessful`, `unclear`, `not_applicable` | Process detail |
| `rally_length` | Number of ball contacts, serve included | integer/category | `5` or `unknown` | Rally description |
| `point_winner` | Side winning point | category | `player`, `opponent`, `unknown` | Point outcome |
| `point_outcome` | Encoded result | category | `win`, `loss`, `unknown` | Convenient summary |
| `video_timestamp` | Point start timestamp | text | `00:12:08` | Audit trail |
| `notes` | Short evidence note | text | `serve partly occluded` | Preserves uncertainty |

The first implementation uses this compact schema. Extra variables require a documented reason because complexity can reduce consistency.
