# PTTI Web MVP user test plan

## Sprint 0.4 seed-user status and invitation

As of 2026-10-12, no seed users are available or recruited and no real user sessions have been run. Initial target is 1–3 seed users, then the larger target below: 5 fans, 3 athletes/enthusiasts and 2 coaches. Do not count developer or agent checks as participant sessions.

For this local-only build, invite participants to use the device where `http://127.0.0.1:4174/` is already running. Do not expose the dev server to a public network. A facilitator can share this invitation:

> 想请你用 5 分钟试用一个乒乓球找赛网页。请按页面提示自己搜索比赛、查看官方来源并试着打开；我会观察哪里不清楚。无需提供姓名、联系方式或账号信息。反馈只保存在这台设备的浏览器里，不会自动发送到线上。

Have the participant operate the mouse/keyboard themselves. Use the five-minute flow below. Record only a participant code and the requested task outcomes. If the publisher asks for login, payment, location permission, regional verification or a CAPTCHA, stop there and record only the visible gate type; do not enter credentials, personal data or payment information. Export the local JSON only with the participant's agreement.

## Optional remote preview — plan only, not deployed

If seed users cannot attend the device running localhost, the lowest-scope preview is to build only `products/ptti-web` and host its static `dist/` output on Cloudflare Pages Free with the generated `pages.dev` HTTPS address. Cloudflare currently lists Pages Free at $0/month; its documentation lists up to 500 builds/month and 20,000 files on Free. No custom domain needs to be purchased for a small trial. Recheck plan terms and limits before any deployment: [Pages pricing](https://www.cloudflare.com/en-ca/developer-platform/products/pages/) · [Pages limits](https://developers.cloudflare.com/pages/platform/limits/).

This would be a public URL, not a private invitation site. A safe preview would contain only the Web build, its four public match records, source links and authored text/placeholder. Do not deploy the monorepo root, desktop assets, private videos, databases, secrets, authenticated APIs or Vision services. Keep feedback in browser `localStorage`; do not add a form endpoint, analytics SDK or server-side feedback store. Participants would export JSON only with consent and hand it directly to the facilitator. Hosting infrastructure can still process ordinary request metadata such as client IP and request time; Cloudflare's documentation describes HTTP request logs and available fields. See [request logs](https://developers.cloudflare.com/logs/reference/).

Deployment remains gated on explicit user approval because anyone with the `pages.dev` URL could access the preview and the hosting provider would process network request metadata. No account, project, URL or deployment has been created for this plan.

## Recruitment target

- 5 ordinary table tennis fans
- 3 athletes or table tennis enthusiasts
- 2 coaches

These are recruitment targets, not completed interviews. No participant responses have been collected for this MVP.

## Session tasks

1. Find the WTT Finals Doha match involving Fan Zhendong and Wang Chuqin.
2. Say who hosts its official source and whether playback has been tested.
3. Open the source link and report what actually happens in that browser and region.
4. Find a women’s singles match using the discipline filter.
5. Explain anything confusing or frustrating, then say whether you would return to PTTI.

Do not sign in for a participant, bypass a regional restriction, or enter a payment flow. If a source asks for an account, subscription or location verification, record that outcome and stop at that gate.

## Five-minute tryout flow

Run this with a real participant. The facilitator may read the task aloud but should not guide the participant through the interface unless they ask for help. Observe what they do; do not record a success result unless it happened.

| Time | Participant task | Observe / record |
| --- | --- | --- |
| 0:00–0:30 | Open PTTI and explain what they think the site can do. | Whether they identify “看比赛” and notice the search prompt. |
| 0:30–1:30 | Use the first-screen “查找比赛” action, search `樊振东` or `Fan Zhendong`, then find Fan Zhendong vs Lin Gaoyuan. | Whether search and results are understandable; which language/input they choose. |
| 1:30–2:30 | Read the card’s source and playback status, then open its official video-page link. | Exact destination and visible outcome in that participant’s browser/region. Do not call a page load playback evidence. |
| 2:30–3:30 | Return to PTTI, reset filters, choose 女单 / Women’s Singles, and identify one match with a direct video page and one without a match-specific route. | Whether they distinguish the WTT YouTube page from an event/source page; note confusion. |
| 3:30–5:00 | Open “反馈建议”, select the issue/outcome that matches their actual session, and save feedback locally. | Confirm the page says data stays in this browser. Ask about return intent; submit only the participant’s real response. |

After the session, use the blank record below. Do not enter names or contact information. If the participant agrees, use the Export control to save the local JSON record for analysis; the app does not send it anywhere.

## Blank session record

Use a participant code such as `F01`, `A01` or `C01`. Do not record names, email addresses, phone numbers, account credentials, exact home location or other unnecessary personal data.

| Field | Record |
| --- | --- |
| Participant code / role |  |
| Date and browser/device class |  |
| Found requested match? (yes / partly / no) |  |
| Correct official source identified? (yes / no) |  |
| What happened after opening source? |  |
| Did participant understand playback was unverified? (yes / no) |  |
| Where was the experience confusing or slow? |  |
| Would participant use PTTI again? (yes / unsure / no) |  |
| Short factual observation, with no invented interpretation |  |

## In-app feedback

The Feedback page is a lightweight exit form. It stores only role, task outcome, source-click outcome, playback-status clarity, optional friction text, return intent and a timestamp in that browser's local storage. It sends no network request. The user may export the local entries as JSON. Only submit feedback after a real session; the test target shown in the app is a task prompt, not a report of completed testing.
