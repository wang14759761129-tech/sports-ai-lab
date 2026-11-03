import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { createArenaChallengeState, createArenaLearningTakeaway, createArenaTakeawayCopyGuard, formatArenaLearningTakeaway, reduceArenaChallenge } from '../src/arena-challenge.mjs';

const first = createArenaChallengeState();
let cases = 1;
assert.deepEqual(first, { selectedChoice: null, attempt: 1, takeawayGenerated: false });

const activeFlickTakeaway = createArenaLearningTakeaway('active-flick');
assert.deepEqual(activeFlickTakeaway, {
  simulated: 'arena.learning.simulated',
  scenario: 'arena.scenario',
  choice: 'arena.choice.activeFlick',
  purpose: 'arena.detail.activeFlick.intent',
  advantage: 'arena.detail.activeFlick.advantage',
  risk: 'arena.detail.activeFlick.risk',
  conditions: 'arena.detail.activeFlick.when',
  question: 'arena.learning.question',
}, 'the learning takeaway reuses the selected simulated tactic explanation');
assert.equal(createArenaLearningTakeaway('untrusted-choice'), null, 'unknown choices cannot generate a takeaway');
cases += 2;

for (const choice of ['active-flick', 'short-touch', 'long-push']) {
  const selected = reduceArenaChallenge(first, { type: 'choose', choice });
  assert.equal(selected.selectedChoice, choice, `${choice} is a playable choice`);
  assert.equal(selected.attempt, 1, 'a choice stays within the current challenge attempt');
  cases++;
}

const rapidChoices = [
  { type: 'choose', choice: 'active-flick' },
  { type: 'choose', choice: 'short-touch' },
  { type: 'choose', choice: 'long-push' },
].reduce(reduceArenaChallenge, first);
assert.deepEqual(rapidChoices, { selectedChoice: 'long-push', attempt: 1, takeawayGenerated: false }, 'the final user choice is the displayed result');
cases++;

const retry = reduceArenaChallenge(rapidChoices, { type: 'retry' });
assert.deepEqual(retry, { selectedChoice: null, attempt: 2, takeawayGenerated: false });
assert.equal(reduceArenaChallenge(retry, { type: 'choose', choice: 'untrusted-choice' }).selectedChoice, null, 'unknown choices are ignored');
cases += 2;

assert.deepEqual(reduceArenaChallenge(first, { type: 'generate-takeaway' }), first, 'a takeaway cannot be generated before a tactic is selected');
const selectedForTakeaway = reduceArenaChallenge(first, { type: 'choose', choice: 'active-flick' });
const generated = reduceArenaChallenge(selectedForTakeaway, { type: 'generate-takeaway' });
assert.equal(generated.takeawayGenerated, true, 'generation is an explicit action');
const changedAfterGeneration = reduceArenaChallenge(generated, { type: 'choose', choice: 'short-touch' });
assert.equal(changedAfterGeneration.takeawayGenerated, true, 'a generated card stays visible when the user changes choice');
assert.equal(createArenaLearningTakeaway(changedAfterGeneration.selectedChoice).choice, 'arena.choice.shortTouch', 'the card follows the latest selection');
assert.equal(reduceArenaChallenge(changedAfterGeneration, { type: 'retry' }).takeawayGenerated, false, 'retry clears the transient card');
cases += 5;

const copyGuard = createArenaTakeawayCopyGuard();
assert.equal(await copyGuard.copy('manual fallback'), 'manual', 'missing clipboard permission has a manual fallback');
assert.equal(await copyGuard.copy('failed copy', async () => { throw new Error('denied'); }), 'manual', 'clipboard failure returns a manual fallback');
let finishStaleCopy;
const staleCopy = copyGuard.copy('old tactic', () => new Promise((resolve) => { finishStaleCopy = resolve; }));
copyGuard.invalidate();
finishStaleCopy();
assert.equal(await staleCopy, null, 'late clipboard results are ignored after choice change, retry or route exit');
let finishSupersededCopy;
const supersededCopy = copyGuard.copy('first request', () => new Promise((resolve) => { finishSupersededCopy = resolve; }));
assert.equal(await copyGuard.copy('second request', async () => {}), 'copied', 'the latest repeated copy request owns the status');
finishSupersededCopy();
assert.equal(await supersededCopy, null, 'an earlier repeated copy result cannot overwrite the latest result');
cases += 5;

const root = new URL('../', import.meta.url);
const out = new URL('.alpha-qa/goal35-arena-learning/', root);
await mkdir(out, { recursive: true });
const bundled = await build({
  stdin: { contents: `export { ArenaChallengeView } from './src/ArenaChallengePage'; export { message } from './src/i18n'; export { renderToStaticMarkup } from 'react-dom/server';`, resolveDir: fileURLToPath(root), loader: 'tsx' },
  bundle: true, platform: 'node', format: 'esm', packages: 'external', jsx: 'automatic', write: false,
});
const kitPath = new URL('arena-kit.mjs', out);
await writeFile(kitPath, bundled.outputFiles[0].contents);
const { ArenaChallengeView, message, renderToStaticMarkup } = await import(pathToFileURL(fileURLToPath(kitPath)).href + `?${Date.now()}`);

function elements(node, result = []) {
  if (Array.isArray(node)) { for (const child of node) elements(child, result); return result; }
  if (!node || typeof node !== 'object' || !('type' in node) || !node.props) return result;
  result.push(node);
  elements(node.props.children, result);
  return result;
}

for (const locale of ['zh-CN', 'en']) {
  const actions = [];
  let backCount = 0;
  let journalCount = 0;
  const copiedTakeaways = [];
  const initial = ArenaChallengeView({ locale, state: first, onAction: (action) => actions.push(action), onBack: () => { backCount++; } });
  const initialHtml = renderToStaticMarkup(initial);
  assert.match(initialHtml, /data-arena-simulated="true"/);
  assert.match(initialHtml, /data-arena-score="9:9"/);
  assert.match(initialHtml, locale === 'zh-CN' ? /aria-label="9比9"/ : /aria-label="9 to 9"/);
  assert.match(initialHtml, /真实比赛或录像|Not linked to a real match or video/);
  assert.match(initialHtml, /没有机械的标准答案|no automatic right answer/);
  assert.doesNotMatch(initialHtml, /data-match-id|data-source-id|youtube\.com|<video\b|<iframe\b|LIVE/i);
  assert.doesNotMatch(initialHtml, /下注|充值|提现|兑换|cash out|withdraw|deposit|betting/i);
  cases++;

  const nodes = elements(initial);
  const buttons = nodes.filter((node) => node.type === 'button');
  const backButton = buttons.find((node) => node.props['data-arena-back']);
  backButton.props.onClick(); assert.equal(backCount, 1);
  const choices = buttons.filter((node) => node.props['data-arena-choice']);
  assert.deepEqual(choices.map((node) => node.props['data-arena-choice']), ['active-flick', 'short-touch', 'long-push']);
  for (const button of choices) {
    assert.equal(button.props.type, 'button', 'choice is keyboard operable as a native button');
    button.props.onClick();
    assert.deepEqual(actions.at(-1), { type: 'choose', choice: button.props['data-arena-choice'] });
  }
  cases++;

  const copyByChoice = {
    'active-flick': ['arena.choice.activeFlick', 'arena.detail.activeFlick.intent', 'arena.detail.activeFlick.advantage', 'arena.detail.activeFlick.risk', 'arena.detail.activeFlick.when'],
    'short-touch': ['arena.choice.shortTouch', 'arena.detail.shortTouch.intent', 'arena.detail.shortTouch.advantage', 'arena.detail.shortTouch.risk', 'arena.detail.shortTouch.when'],
    'long-push': ['arena.choice.longPush', 'arena.detail.longPush.intent', 'arena.detail.longPush.advantage', 'arena.detail.longPush.risk', 'arena.detail.longPush.when'],
  };
  const localizedTakeaways = [];
  for (const choice of ['active-flick', 'short-touch', 'long-push']) {
    const next = reduceArenaChallenge(first, { type: 'choose', choice });
    const resultTree = ArenaChallengeView({ locale, state: next, onAction: (action) => { actions.push(action); }, onBack: () => {} });
    const resultHtml = renderToStaticMarkup(resultTree);
    assert.match(resultHtml, new RegExp(`data-arena-result="${choice}"`));
    for (const key of copyByChoice[choice]) assert(resultHtml.includes(message(locale, key)), `localized ${choice} explanation is rendered: ${key}`);
    const resultButtons = elements(resultTree).filter((node) => node.type === 'button');
    assert.equal(resultButtons.filter((node) => node.props['aria-pressed'] === true).length, 1);
    const retryButton = resultButtons.find((node) => node.props['data-arena-retry']);
    let retryAction = null; retryButton.props.onClick();
    const retryTree = ArenaChallengeView({ locale, state: next, onAction: (action) => { retryAction = action; }, onBack: () => {} });
    elements(retryTree).find((node) => node.props?.['data-arena-retry']).props.onClick();
    assert.deepEqual(retryAction, { type: 'retry' });

    let generateAction = null;
    const generateButton = elements(resultTree).find((node) => node.props?.['data-arena-generate']);
    generateButton.props.onClick();
    generateAction = actions.at(-1);
    assert.deepEqual(generateAction, { type: 'generate-takeaway' }, 'takeaway generation is explicit and follows the selected tactic');
    const generatedState = reduceArenaChallenge(next, generateAction);
    const takeawayTree = ArenaChallengeView({
      locale,
      state: generatedState,
      onAction: () => {},
      onBack: () => {},
      onOpenJournal: () => { journalCount++; },
      onCopyTakeaway: (text) => { copiedTakeaways.push(text); },
      copyStatus: 'manual',
      manualCopyText: `manual-${choice}`,
    });
    const takeawayHtml = renderToStaticMarkup(takeawayTree);
    assert.match(takeawayHtml, /data-arena-learning="simulated"/);
    for (const key of [...copyByChoice[choice], 'arena.learning.simulated', 'arena.learning.question']) {
      assert(takeawayHtml.includes(message(locale, key)), `localized ${choice} takeaway includes ${key}`);
    }
    const conditionText = message(locale, copyByChoice[choice][4]);
    assert(takeawayHtml.split(conditionText).length - 1 >= 2, 'the future-practice question is grounded in the same displayed conditions');
    for (const key of ['arena.learning.generate', 'arena.learning.title', 'arena.learning.label.question', 'arena.learning.copy', 'arena.learning.copyManual', 'arena.learning.openJournal', 'arena.learning.journalHint']) {
      assert.notEqual(message(locale, key), key, `${locale} provides translated copy for ${key}`);
    }
    assert.match(takeawayHtml, /textarea[^>]*readonly/i);
    assert.doesNotMatch(takeawayHtml, /data-match-id|data-source-id|rally[_-]?id|localStorage/i, 'a simulated takeaway does not create real content identity or persist itself');
    const takeawayNodes = elements(takeawayTree);
    takeawayNodes.find((node) => node.props?.['data-arena-copy']).props.onClick();
    takeawayNodes.find((node) => node.props?.['data-arena-open-journal']).props.onClick();
    assert.equal(copiedTakeaways.at(-1), formatArenaLearningTakeaway(choice, (key) => message(locale, key)), 'copy exports exactly the currently visible localized takeaway');
    assert.equal(journalCount, localizedTakeaways.length + 1, 'Journal navigation is available without saving the takeaway');
    localizedTakeaways.push(copiedTakeaways.at(-1));
    cases++;
  }
  assert.equal(new Set(localizedTakeaways).size, 3, 'each tactic produces distinct learning text in each language');
  const generatedThenChangedTree = ArenaChallengeView({ locale, state: changedAfterGeneration, onAction: () => {}, onBack: () => {} });
  const changedHtml = renderToStaticMarkup(generatedThenChangedTree);
  assert.match(changedHtml, /data-arena-result="short-touch"/);
  assert(changedHtml.includes(message(locale, 'arena.detail.shortTouch.intent')), 'generated learning updates to the latest selected tactic');
  assert.equal(changedHtml.includes(message(locale, 'arena.detail.activeFlick.intent')), false, 'stale tactic explanation is removed');
  const clearedState = reduceArenaChallenge(changedAfterGeneration, { type: 'retry' });
  const clearedHtml = renderToStaticMarkup(ArenaChallengeView({ locale, state: clearedState, onAction: () => {}, onBack: () => {} }));
  assert.doesNotMatch(clearedHtml, /data-arena-learning=/, 'retry removes the generated learning card');
  cases++;
}

const [pageSource, appSource, routeSource, styles] = await Promise.all([
  readFile(new URL('../src/FanCatalogPage.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/App.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/fan-location.mjs', import.meta.url), 'utf8'),
  readFile(new URL('../src/fan-gold.css', import.meta.url), 'utf8'),
]);
assert.match(pageSource, /data-arena-entry[\s\S]*onClick=\{onOpenArena\}/, 'Cinema entry invokes its route callback');
assert.match(appSource, /onOpenArena=\{\(\) => changePage\('arena'\)\}/, 'Cinema connects the entry to the in-product challenge route');
assert.match(appSource, /page === 'arena'[\s\S]*ArenaChallengePage/);
assert.match(appSource, /onOpenJournal=\{\(\) => changePage\('train'\)\}/, 'Arena links to the existing local Journal page without adding storage');
assert.match(routeSource, /'community', 'arena'/, 'challenge has a refreshable in-product route');
cases++;
assert.match(styles, /\.arena-choice:focus-visible/);
assert.match(styles, /@media \(max-width: 600px\)[^{]*\{ \.arena-challenge/);
assert.match(styles, /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.arena-challenge/);
cases++;
const component = await readFile(new URL('../src/ArenaChallengePage.tsx', import.meta.url), 'utf8');
assert.doesNotMatch(component, /localStorage|fanLocalData|saved_match_ids|training_notes|match_notes|coach_notes|fan_notes/);
assert.match(component, /copyGuard\.invalidate\(\)/, 'copy feedback is invalidated when the tactic changes, retry runs, locale changes, or the route unmounts');
assert.match(component, /setManualCopyText\(result === 'manual' \? text : ''\)/, 'clipboard failure exposes the current text for manual copy');
assert.match(component, /navigator\.clipboard\?\.writeText/, 'clipboard is used only from the explicit copy action');
cases++;
await writeFile(new URL('offline-report.json', out), JSON.stringify({ status: 'PASS', cases, evidence_type: 'OFFLINE_COMPONENT_RENDER_AND_ACTIONS', GUI_VISUAL: 'NOT_TESTED', REAL_PLAYBACK: 'NOT_TESTED', RESPONSIVE_VISUAL: 'NOT_TESTED' }, null, 2));
console.log(`PASS: ${cases} Arena offline cases cover simulated content, three native choices and explanations, rapid selection, retry, bilingual rendering, route entry, keyboard semantics, narrow layout, reduced motion and no user-data/media/rights side effects. GUI, real playback and responsive visual remain NOT_TESTED.`);
