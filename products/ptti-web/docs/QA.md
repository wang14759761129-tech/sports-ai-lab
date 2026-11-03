# MVP verification record

Checked 2026-10-12 in the independent `products/ptti-web` worktree.

## Automated checks

- `npm run build` — passed; TypeScript check and Vite production build completed.
- `npm run check:sources` — passed, 79 source, route, status and media-boundary checks across four match records.
- `npm audit` during install — 0 vulnerabilities in 22 packages.
- `npm audit --omit=dev` — 0 production dependency vulnerabilities.
- `git diff --cached --check` — passed with no whitespace errors.
- Secret scan — no credential or private-key patterns found. The only `sqlite` match is the README statement that the Web app does not access the desktop database.

## Browser interaction checks

- Player search for `Fan Zhendong` showed the two matching sample cards.
- Women’s singles filter showed the Wang Yidi–Sun Yingsha and Sun Yingsha–Chen Xingtong records.
- The no-route sample showed a clear message and no watch button.
- Cinema, Pulse, Stars and Feedback navigation rendered the expected content; Pulse showed three attributed items and Stars showed three source-backed profiles.
- Feedback storage was empty before testing. No test response was submitted or recorded.
- Outbound Cinema links use `_blank` with `noopener noreferrer`. The YouTube destination opened the named Wang Yidi–Sun Yingsha video on the verified World Table Tennis channel. The player remained at 0:00; playback was not tested.
- Desktop viewport: 1265×715, document width 1250 px.
- Mobile viewport: 390×844, document width 375 px; no horizontal overflow.

## Screenshot status

Desktop and mobile screenshots were captured from the local browser for visual inspection in the current Codex session. The browser safety layer rejected the `data:` navigation used to export those captures as files. No screenshot files are included in this commit, and no alternative export path was attempted.
