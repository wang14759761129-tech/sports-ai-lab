import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { createElement, Children } from 'react';
import { createWatchCopyGuard } from '../src/watch-copy-guard.mjs';

const root = new URL('../', import.meta.url);
const out = new URL('.alpha-qa/goal33-private-theater/', root);
await mkdir(out, { recursive: true });
const compiled = await build({
  stdin: { contents: `export { PrivateTheaterView } from './src/PrivateTheaterFrame'; export { renderToStaticMarkup } from 'react-dom/server';`,
    resolveDir: fileURLToPath(root), loader: 'tsx' },
  bundle: true, platform: 'node', format: 'esm', packages: 'external', jsx: 'automatic', write: false,
});
const kitFile = new URL('frame-kit.mjs', out);
await writeFile(kitFile, compiled.outputFiles[0].contents);
const { PrivateTheaterView, renderToStaticMarkup } = await import(kitFile.href + `?${Date.now()}`);

let cases = 0;
for (const locale of ['zh-CN', 'en']) {
  for (const focused of [false, true]) {
    let exited = false; let toggled = false; let returned = false; let prevented = false;
    const main = createElement('h1', { id: 'fan-watch-title' }, 'Synthetic source presentation');
    const secondary = createElement('input', { defaultValue: 'Synthetic unsaved feedback', 'aria-label': 'QA feedback' });
    const view = PrivateTheaterView({ locale, sourceId: 'video-source:youtube:0QgbtsBWZhk', focused, secondaryId: 'qa-secondary', main, secondary,
      onBack: () => { returned = true; }, onExitFocus: () => { exited = true; }, onToggleFocus: () => { toggled = true; } });
    const children = Children.toArray(view.props.children);
    const toolbar = Children.toArray(children[0].props.children);
    toolbar[0].props.onClick(); assert.equal(returned, true);
    toolbar[2].props.onClick(); assert.equal(toggled, true);
    assert.equal(toolbar[2].props['aria-pressed'], focused);
    assert.equal(toolbar[2].props['aria-controls'], 'qa-secondary');
    assert.equal(toolbar[2].type, 'button');
    assert.equal(children.at(-1).props.hidden, focused);
    assert.equal(children.at(-1).props.children, secondary, 'focus hides rather than discards feedback/form children');
    assert.equal(children[2].type, main.type);
    assert.equal(children[2].props, main.props, 'main content is retained in either presentation mode');
    view.props.onKeyDown({ key: 'Escape', defaultPrevented: true, preventDefault() { prevented = true; } });
    assert.equal(exited, false, 'do not override an already handled Escape');
    view.props.onKeyDown({ key: 'Escape', defaultPrevented: false, preventDefault() { prevented = true; } });
    assert.equal(exited, focused); assert.equal(prevented, focused);
    const html = renderToStaticMarkup(view);
    assert.match(html, /PRIVATE THEATER/);
    assert(!html.includes('undefined'));
    assert.doesNotMatch(html, /<(?:video|iframe|img)\b/i);
    await writeFile(new URL(`frame-${locale}-${focused ? 'focus' : 'normal'}-server-render.html`, out), html);
    cases++;
  }
}

const guard = createWatchCopyGuard();
const writes = [];
assert.equal(await guard.copy('https://www.youtube.com/watch?v=0QgbtsBWZhk', async (url) => { writes.push(url); }), 'copied');
assert.deepEqual(writes, ['https://www.youtube.com/watch?v=0QgbtsBWZhk']); cases++;
assert.equal(await guard.copy('https://example.invalid/qa', async () => { throw new Error('denied'); }), 'manual');
assert.equal(await guard.copy('https://example.invalid/qa'), 'manual'); cases++;

let finishOld;
const oldSourceCopy = guard.copy('https://example.invalid/source-a', () => new Promise((resolve) => { finishOld = resolve; }));
guard.invalidate(); // source changed, route left or component unmounted
assert.equal(await guard.copy('https://example.invalid/source-b', async () => {}), 'copied');
finishOld(); assert.equal(await oldSourceCopy, null, 'late old-source success cannot show copied on the new source'); cases++;

let failOld;
const oldFailure = guard.copy('https://example.invalid/source-a', () => new Promise((_, reject) => { failOld = reject; }));
guard.invalidate();
assert.equal(await guard.copy('https://example.invalid/source-a', async () => {}), 'copied');
failOld(new Error('old permission failure'));
assert.equal(await oldFailure, null, 'returning to the same source does not revive an earlier request'); cases++;

let finishFirst;
const first = guard.copy('https://example.invalid/qa', () => new Promise((resolve) => { finishFirst = resolve; }));
assert.equal(await guard.copy('https://example.invalid/qa', async () => {}), 'copied');
finishFirst(); assert.equal(await first, null, 'only the latest repeated request can update UI'); cases++;

const [page, frame, css] = await Promise.all(['src/FanCatalogPage.tsx', 'src/PrivateTheaterFrame.tsx', 'src/fan-gold.css'].map((file) => readFile(new URL(file, root), 'utf8')));
assert.match(page, /PrivateTheaterFrame key=\{activeSource\.source_id\}/, 'changing source remounts the focus scope');
assert.match(page, /return \(\) => watchCopyGuard\.invalidate\(\)/, 'source changes and unmount invalidate copy requests');
assert.match(page, /if \(result !== null\) setWatchUrlCopyState\(result\)/);
assert.match(frame, /toggle\.current\?\.focus\(\{ preventScroll: true \}\)/);
assert.doesNotMatch(frame, /localStorage|requestFullscreen|\.play\(|\.pause\(|cancelPlayback|<video|<iframe/);
assert.match(css, /\.theater-secondary\[hidden\] \{ display: none !important;/);
assert.match(css, /@media \(prefers-reduced-motion: reduce\) \{ \.private-theater/);
cases++;
await writeFile(new URL('offline-report.json', out), JSON.stringify({ status: 'PASS', cases, evidence_type: 'OFFLINE_COMPONENT_EVENTS_AND_ASYNC_BOUNDARIES', GUI_VISUAL: 'NOT_TESTED', REAL_PLAYBACK: 'NOT_TESTED', RESPONSIVE_VISUAL: 'NOT_TESTED' }, null, 2));
console.log(`PASS: ${cases} Private Theater offline cases: focus presentation/Escape/back actions, retained children, exact copy URL, denied clipboard fallback, stale/duplicate/unmounted request boundaries and reduced-motion. GUI/real playback/responsive visual NOT_TESTED.`);
