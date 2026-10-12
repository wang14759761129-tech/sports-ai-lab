# PTTI Web MVP — 5-minute acceptance and user pilot

Updated 2026-10-12 for Sprint 0.5. This document separates founder acceptance from external-user research. Developer or agent checks are recorded only in QA notes and never count as people.

## Session status

| Cohort | Completed sessions | Current status |
| --- | ---: | --- |
| Founder acceptance | 0 | Prepared; not run in this work session |
| External seed users | 0 | No participants available/recruited yet |
| Developer/agent QA | Not a participant count | Automated and browser checks only |

External pilot target: first 1–3 people, then 5 ordinary fans, 3 athletes/table-tennis enthusiasts and 2 coaches. Targets are not results. Do not fill an observation row until a person actually completes the session.

## Founder acceptance — facilitator script

Use the already-running local site at `http://127.0.0.1:4174/`. The founder operates the page. Read only the bold task prompt; do not guide unless asked. Do not count this as an external-user session.

| Time | Read to the founder | Observe and record |
| --- | --- | --- |
| 0:00–0:30 | “请用一句话说说你觉得 PTTI 可以做什么。” | Their first understanding, in their own words. |
| 0:30–1:30 | “请搜索樊振东，找到樊振东对林高远的那场比赛。” | 是否独立找到；从看比赛首次出现到定位卡片的用户点击数；搜索用中文还是英文。输入字符不计点击。 |
| 1:30–2:15 | “请判断这张卡片提供的是什么来源，以及页面有没有说视频已经实测可播放。” | 是否分清具体视频页、官方赛事页、仅查证来源；是否理解播放状态。 |
| 2:15–3:15 | “请打开官方来源，按你平常的方式尝试播放，然后告诉我页面实际发生了什么。” | 到达的页面/发布者、是否开始播放、可见画面和时间轴是否前进；任何登录/地区/付费/验证提示。不要代为登录或绕过限制。 |
| 3:15–3:45 | “请返回 PTTI，找到反馈建议入口。” | 找到反馈页所需时间和点击数；页面是否说清数据只保存在本机。 |
| 3:45–5:00 | “请按刚才真实体验填写反馈，然后导出 JSON。” | 是否保存成功；是否理解导出文件由用户主动保存/交给研究者，网站不会自动发送。不要替对方编写体验。 |

Founder result for Sprint 0.5: **NOT RUN**. Fill the blank founder record only after the founder has completed these actions. A developer verifying the page does not change this status.

## External seed-user invitation

> 想邀请你用 5 分钟试用一个乒乓球找赛网页。请按任务自己搜索、查看官方来源并试着打开；我会观察你实际操作的过程。无需提供姓名、联系方式或账号信息。反馈只保存在当前设备的浏览器里，不会自动发送到线上；如果你愿意，可以在结束时主动导出 JSON 给我。遇到登录、付费、地区验证或验证码时，我们会停在该提示，不会尝试绕过。

For local testing, participant and facilitator must use the device/browser where `http://127.0.0.1:4174/` is running. Do not expose the Vite server to a network. A remote HTTPS preview is not available unless separately approved and deployed.

## External participant five-minute flow

Ask the participant to operate the device. Read the task without pointing at controls. Record actual taps/clicks from the first relevant screen action to the result; typing is not a click. If they ask for help, note the help and do not mark the task independent.

| Time | Participant task | Measure |
| --- | --- | --- |
| 0:00–0:30 | Open PTTI and tell you what they think it is for. | First impression and whether they notice “看比赛”. |
| 0:30–1:30 | Search `樊振东` or `Fan Zhendong` and find Fan Zhendong vs Lin Gaoyuan. | Independent find: yes/partial/no; clicks; completion time; language used. |
| 1:30–2:15 | Say whether its action opens an official video page or an event/source page, and whether playback is confirmed. | Correct interpretation, hesitation, any mistaken expectation. |
| 2:15–3:15 | Open the original publisher page and try playback. | Destination reached; what is visibly observed; any gate. Page load alone is not playback success. |
| 3:15–3:45 | Return to PTTI and find feedback. | Clicks/time; clarity of local-only storage message. |
| 3:45–5:00 | Submit feedback matching their actual session and export JSON if they agree. | Local save/export understanding; participant's own return intent. |

Stop if the publisher requests login, payment, location permission, regional verification, or CAPTCHA. Do not ask for credentials, personal data, payment information or exact location. Note only the visible gate category. Do not record audio, video, screen or names unless a separate, informed consent is obtained; the default protocol is observation notes only.

## Separate blank session records

Use distinct IDs: `FOUNDER-01` for founder acceptance; `F01` for fans, `A01` for athletes/enthusiasts, `C01` for coaches. Never combine their denominators. Do not record names, emails, phone numbers, credentials or precise location.

| Field | Founder record | External participant record |
| --- | --- | --- |
| Participant code / role |  |  |
| Date / device class / browser |  |  |
| Completed tasks |  |  |
| Found requested match independently? (yes / partly / no) |  |  |
| Clicks to locate match (typing excluded) |  |  |
| Correctly classified source and playback status? |  |  |
| Official destination reached? What actually appeared? |  |  |
| Playback observed? (visual/time movement / blocked / not tested) |  |  |
| Visible restriction, if any (category only) |  |  |
| Most confusing step (participant's words or factual behavior) |  |  |
| Feedback saved and JSON exported? |  |  |
| Would use again? (yes / unsure / no) |  |  |
| Help needed / factual notes |  |  |

## Feedback storage and export

The Feedback page writes to this browser's `localStorage`; it does not send submissions to a server. Export is a user-initiated JSON download. The participant may decline export. The facilitator must not inspect or copy entries from another user's browser without their agreement. Do not enter fabricated/synthetic test responses in the app.

## Preview boundary

The current app is local-only at `127.0.0.1:4174`. A participant on another device cannot open that address. The Cloudflare Pages static HTTPS preview is documented in `CLOUDFLARE_PREVIEW_PLAN.md`, but has **not** been deployed; deployment requires the user's explicit approval.
