# GOAL106 single-video QA (not a release entry)

Run in a PowerShell window, using existing Python (standard library only):

```powershell
cd C:\PTTI-Worktrees\goal99-r4-cinema-evolution
python products/ptti/qa/goal106/serve.py
```

Open **http://127.0.0.1:58306/** in a normal Windows desktop browser. Keep the
console running; Ctrl+C stops it. If the port is occupied, stop here or explicitly
choose a free port using `--port`; do not terminate another application's process.
Do not open the HTML using file://. No persistent server is started automatically.
Only two fixed routes are served. No backend import or DB is involved. No image
or video is proxied, saved, or added to the frontend public/dist folders.

## Manual verification

1. Read the data disclosure, click Load. The iframe is 640×360 with controls and
   no overlay. Observe whether its preview and YouTube attribution actually show.
2. Click the official play control. Record actual match image and two advancing
   time readings; if it fails, record the precise message/code. Do not infer
   playback from iframe load, title, or a still preview. Errors 101/150 can mean
   embedding disabled; 153 can mean missing Referer/client identity. Do not
   bypass either. Unknown errors stay unknown.
3. Open the permanent official watch link, independently confirm the page opened
   and whether playback works there. Copy and paste the link to verify recovery.
   Opening the page is separate from watching the video.
4. To test network failure, use the browser's normal DevTools Network Offline
   mode, unload/reload the iframe, then restore Online. The external link and
   copy field must remain present, although external navigation also needs a
   working network. Cross-origin frames may show their own error without firing
   a parent error event; the 15-second notice never claims successful loading.
5. Unload the iframe. Fill observed statuses/notes and export the JSON. This is a
   manual report, not independent proof, Windows Native evidence, or a permission
   change. No data is uploaded. Do not insert secrets/private details in notes.

No simulated provider response or forced disabled-embedding test is used. If the
actual provider does not reject embedding, mark that branch NOT_TESTED. Offline
code tests do not establish that a browser applied all policies or rendered the
player correctly.

## Photo wall decision remains separate

- Original eight cards used standalone remote CDN `<img>` URLs. Technical
  reachability is not a display permission, and this experiment does not request
  them.
- Official iframe embedding is a documented display mechanism without a Data
  API key/Cloud setup for basic viewing. It is **not** permission to extract its
  preview, crop the player into a thumbnail, or overlay a card over its controls.
- A separate, precise policy basis for standalone remote thumbnail display in
  PTTI discovery cards is still unestablished. Existing API runtime is preserved
  but Cloud remains paused. Thus zero of eight standalone covers are restored
  by this experiment. Successful player viewing would qualify only this detail
  experiment, not change catalog permissions or the four-column homepage.
- WebView/Windows support, application identity/Referer and provider restrictions
  require their own real validation. This does not replace the R4 player.

Official references checked 2026-10-25:
https://developers.google.com/youtube/player_parameters
https://support.google.com/youtube/answer/171780?hl=en
https://www.youtube.com/static?template=terms

## Lightweight checks

```powershell
python products/ptti/qa/goal106/test_spike.py
node --check products/ptti/qa/goal106/spike.js
```

The loopback HTTP tests exercise real serving, route refusal, response bytes and
security headers. Source assertions cover fixed identity, size and evidence
labels only; they are not browser/playback tests. The QA directory is outside
Vite's entry/public directories; no application source or media gate is changed.
