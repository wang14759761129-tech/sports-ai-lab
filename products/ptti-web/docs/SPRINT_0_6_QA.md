# Sprint 0.6 QA record

Date: 2026-10-12
Worktree: `C:\PTTI-Worktrees\web-mvp-v0-1`
Branch: `codex/ptti-web-mvp-v0-1`

## User-facing changes

- Cinema defaults to a watchable-first ordering: the two records with prior official-page visual playback evidence appear first.
- The hero action “只看已核验视频” jumps to and applies the verified-video filter. The count follows the current search, discipline, event, and platform filters.
- Route type and playback evidence are separate: match video page, event page, source-only, and playback-unconfirmed filters cannot promote a source into a verified video.
- Chinese and English controls have matching labels; either search name form is accepted. The selected language survived a page reload in the local browser.
- Match cards use a CSS-authored PTTI placeholder at 16:9 and no third-party cover or media embed.
- Mobile navigation, feedback, language and watch-filter controls have at least 44px height. The search controls use the same minimum height at 390px.

## Source and playback evidence

| Sample | Destination type | Current status | Correct UI action | Evidence boundary |
| --- | --- | --- | --- | --- |
| Fan Zhendong vs Lin Gaoyuan | Official single-match YouTube video page | `PLAYBACK_PASS` from prior browser verification | Open official video page | In the specified test browser, picture changed and timeline advanced from 0:02 to 1:01. This is not PTTI embed permission, territory-wide availability, or confirmed speaker output. |
| Wang Yidi vs Sun Yingsha | Official single-match YouTube video page | `PLAYBACK_PASS` from prior browser verification | Open official video page | In the specified test browser, picture changed and timeline advanced from 0:02 to 0:20. This is not PTTI embed permission, territory-wide availability, or confirmed speaker output. |
| Fan Zhendong vs Wang Chuqin | Official WTT event page | Playback `NOT_TESTED` | View official event page | The supplied link is the event page; it is not represented as a single-match video. |
| Sun Yingsha vs Chen Xingtong | WTT report/article used as evidence | Playback `NOT_TESTED` | View source only | No single-match viewing address is supplied. |

The automated page check confirmed that the first two primary destinations are the supplied official YouTube URLs with `target="_blank"` and `rel="noopener noreferrer"`; event/source-only cards do not receive a video action. Their destination pages were not reopened in this Sprint 0.6 browser pass.

## Browser QA

Local development app: `http://127.0.0.1:4174/` (kept open). A temporary production build smoke check ran at `http://127.0.0.1:4175/` and the temporary preview process/tab was closed afterward.

| Viewport | Result |
| --- | --- |
| 1440px desktop | PASS: all four cards rendered, 16:9 placeholder measured 650×365, no horizontal overflow or text clipping. |
| 768px tablet | PASS: cards rendered in two columns, placeholder ratio 1.778, no horizontal overflow or text clipping; controls at least 44px. |
| 390px mobile | PASS: single-column cards, placeholder ratio 1.778, no horizontal overflow or sampled text clipping; navigation, locale, feedback, filters, and match buttons at least 44px. Cinema, Pulse, Stars, and Feedback layouts were visited. |

The mobile screenshot was visually inspected in the browser. No separate screenshot file was exported. Browser automation is product QA only; actual participant counts remain **0 founder / 0 external users**.

## Automated checks

| Check | Result |
| --- | --- |
| `npm run build` | PASS — TypeScript and Vite production build. |
| `npm run check:sources` | PASS — 111 checks over 4 match records. |
| `npm run check:feedback` | PASS — local storage append/restore, issue categories, malformed-data recovery. |
| `npm run check:watch-filter` | PASS — false-positive playback gate, route mapping, bilingual search/status filters, reset, links, 16:9 placeholder. |
| `npm run check:preview` | PASS — 5 static files, 296.8 KiB; `_headers` present; no database, video, recognized credential marker, remote script/style, embed, or unapproved cover field. |
| `npm audit --audit-level=low` | PASS — 0 vulnerabilities. |
| `git diff --check` | PASS — no whitespace errors; Git emitted line-ending conversion notices for edited text files. |

The production build itself loaded in a browser with four records, the expected official route links, and successful zh-CN / English switching. The app's own static assets and source data are same-origin by design. `_headers` was checked in the build output, but Vite does not apply Cloudflare Pages headers: actual deployed CSP/HTTP response headers are **NOT_TESTED** because no deployment was authorized.

## Public preview and release gates

- Only `products/ptti-web/dist/` is proposed for a future static preview. No Cloudflare project, GitHub App permission, upload, public URL, or deployment was created.
- The existing Cloudflare plan documents Direct Upload without GitHub repository access, public URL/request-metadata disclosure, no automatic feedback collection, and rollback/removal steps. Account-specific log retention remains **UNKNOWN**.
- External destination availability outside the prior test browser, local embed permission, actual sound output, and region availability remain **NOT_TESTED**.
- No human usability results exist yet. The tester/user count is 0.
