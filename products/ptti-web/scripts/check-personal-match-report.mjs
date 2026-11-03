import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { createPersonalMatchReport, resolvePersonalReportSelection, serializePersonalMatchReport, PERSONAL_MATCH_REPORT_VERSION } from '../src/personal-match-report.mjs';
import { calculateOneGame, createOneGameExport, expectedOneGameServer } from '../src/my-match-one-game.mjs';
import { createQuickPointId } from '../src/local-video-review.mjs';
import { createWatchCopyGuard } from '../src/watch-copy-guard.mjs';

const session = { session_id: 'local-session:synthetic-qa', dataset_id: 'HUMAN_QUICK_DRAFT:synthetic-qa', dataset_class: 'HUMAN_QUICK_DRAFT',
  contract_version: 'ptti.quick-annotation/0.2', match_id: 'LOCAL_QUICK_MATCH:synthetic-qa', source_id: null,
  binding_status: 'LOCAL_SESSION_ONLY', media_status: 'ready', duration_seconds: 90,
  file: { name: 'PRIVATE-DO-NOT-EXPORT.mp4', type: 'video/mp4', size: 4096, last_modified_ms: 1 } };
const context = { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' };
const pointsFor = (winners, firstServer = 'PLAYER_A') => winners.map((winner, index) => ({
  point_id: createQuickPointId(session.match_id, 1, index + 1), game_number: 1, point_number: index + 1,
  winner, server: expectedOneGameServer(firstServer, index + 1), start_seconds: null, end_seconds: null,
  bound_video_identity: '', start_confirmed: false, end_confirmed: false,
  observed_tactics: { serve_side: 'unknown', serve_length: 'unknown', third_ball_attack: 'unknown' },
}));
const regular = pointsFor([...Array(10).fill('PLAYER_A'), ...Array(8).fill('PLAYER_B'), 'PLAYER_A']);
const winners = [...Array.from({ length: 14 }, (_, i) => i % 2 ? 'PLAYER_B' : 'PLAYER_A'), 'PLAYER_A', 'PLAYER_B', 'PLAYER_B', 'PLAYER_A', 'PLAYER_A', 'PLAYER_B', 'PLAYER_B', 'PLAYER_A', 'PLAYER_A', 'PLAYER_A'];
const deuce = pointsFor(winners);
const protectedInput = JSON.stringify({ session, regular, deuce, context });
const normal = createPersonalMatchReport(session, regular, context);
assert(normal.ok);
assert.deepEqual(normal.value.calculated_results.final, { score: { player_a: 11, player_b: 8 }, winner: 'PLAYER_A', status: 'GAME_COMPLETE' });
assert.equal(normal.value.data_facts.recorded_point_count, 19);
assert.equal(normal.value.data_facts.actual_game_coverage_independently_verified, false);
assert.equal(normal.value.calculated_results.longest_scoring_runs.find((row) => row.side === 'PLAYER_A').length, 10);
assert.equal(normal.value.calculated_results.longest_scoring_runs.find((row) => row.side === 'PLAYER_B').length, 8);
assert(normal.value.calculated_results.key_stages.every((row) => row.sample_count === null));
const result = createPersonalMatchReport(session, deuce, context); assert(result.ok);
const report = result.value;
assert.deepEqual(report.calculated_results.key_stages.map((row) => [row.first_point, row.last_point, row.sample_count]), [[15, 18, 4], [19, 20, 2], [21, 24, 4]]);
const ranges = report.calculated_results.key_stages.flatMap((row) => Array.from({ length: row.sample_count }, (_, i) => row.first_point + i));
assert.equal(new Set(ranges).size, ranges.length, 'key stages have no duplicated points');
assert.deepEqual(report.calculated_results.key_stages.map((row) => row.outcomes.PLAYER_A.won), [2, 1, 3]);
assert.deepEqual(report.calculated_results.serve_receive, calculateOneGame(deuce, context.first_server).serve_receive, 'rates reuse GOAL44 without a second analyzer');
assert.deepEqual(report.calculated_results.final.score, { player_a: 13, player_b: 11 });
assert.equal(report.data_facts.server_confirmed_point_count, 24);
const tiedRuns = createPersonalMatchReport(session, pointsFor([...Array.from({ length: 5 }, () => ['PLAYER_A', 'PLAYER_A', 'PLAYER_B', 'PLAYER_B']).flat(), 'PLAYER_A', 'PLAYER_A']), context);
assert(tiedRuns.ok);
assert.deepEqual(tiedRuns.value.calculated_results.longest_scoring_runs.map((row) => row.first_point), [1, 3], 'tied longest runs use one earliest representative per side');
assert(tiedRuns.value.training_questions.length <= 7);
const skippedSeven = createPersonalMatchReport(session, pointsFor([...Array(9).fill('PLAYER_A'), ...Array(9).fill('PLAYER_B'), 'PLAYER_A', 'PLAYER_A']), context);
assert(skippedSeven.ok);
assert.equal(skippedSeven.value.calculated_results.key_stages[0].status, 'NOT_REACHED', '9:7 does not prove an earlier exact 7:7');
assert.equal(skippedSeven.value.calculated_results.score_progression[16].phase, 'EARLY_GAME');
assert.equal(skippedSeven.value.calculated_results.score_progression[18].phase, 'AFTER_9_9');
const partial = createPersonalMatchReport(session, deuce.slice(0, 14), context); assert(partial.ok);
assert.equal(partial.value.calculated_results.final.winner, null);
assert.equal(partial.value.calculated_results.key_stages[0].sample_count, 0);
assert.equal(partial.value.calculated_results.serve_receive.status, 'GAME_IN_PROGRESS');
const unknown = createPersonalMatchReport(session, pointsFor(winners, 'UNKNOWN'), { ...context, first_server: 'UNKNOWN' }); assert(unknown.ok);
assert.equal(unknown.value.calculated_results.serve_receive.players, null);
assert.equal(unknown.value.data_facts.server_confirmed_point_count, 0);
assert(!unknown.value.training_questions.some((row) => row.kind === 'SERVE_RECEIVE'));
const unknownFirst = createPersonalMatchReport(session, deuce, { ...context, first_server: 'UNKNOWN' }); assert(unknownFirst.ok);
assert.equal(unknownFirst.value.unknowns.server_information, 'FIRST_SERVER_UNKNOWN');
assert.equal(unknownFirst.value.calculated_results.serve_receive.players, null);
assert.equal(createPersonalMatchReport(session, [], context).issue, 'no-points');
for (const invalid of [null, 'invalid', [null], [{ ...regular[0], point_number: 2 }], [{ ...regular[0], winner: 'UNKNOWN' }], [...regular, { ...regular.at(-1), point_number: 20 }], [{ ...regular[0], server: 'PLAYER_B' }]]) {
  assert.equal(createPersonalMatchReport(session, invalid, context).ok, false);
}
assert.equal(serializePersonalMatchReport(session, deuce, context, 'key:invented').ok, false);
assert.equal(createPersonalMatchReport({ ...session, match_id: 'LOCAL_QUICK_MATCH:another' }, deuce, context).ok, false);
assert.equal(createPersonalMatchReport({ ...session, source_id: 'video-source:youtube:fake' }, deuce, context).ok, false);
assert.equal(createPersonalMatchReport({ ...session, dataset_id: 'HUMAN_QUICK_DRAFT:C:\\private\\file' }, deuce, context).ok, false);
const selected = report.training_questions[0].question_id;
const selection = { key: JSON.stringify(report), questionId: selected };
assert.equal(resolvePersonalReportSelection(report, selection), selected);
assert.equal(resolvePersonalReportSelection(normal.value, selection), null, 'edited records invalidate a previous choice');
assert.equal(resolvePersonalReportSelection({ ...report, evidence_identity: { ...report.evidence_identity, session_id: 'local-session:new' } }, selection), null, 'another media session cannot inherit a choice');
const exported = serializePersonalMatchReport(session, deuce, context, selected); assert(exported.ok);
const json = JSON.parse(exported.text);
assert.equal(json.schema, PERSONAL_MATCH_REPORT_VERSION);
assert.equal(json.evidence_identity.public_match_id, null);
assert.equal(json.evidence_identity.public_video_source_id, null);
assert.equal(json.selected_question_id, selected);
assert.equal(json.confirmation_status, 'USER_RECORDED_NOT_INDEPENDENTLY_VERIFIED');
assert.equal(json.media_scope, 'LOCAL_SESSION_ONLY');
assert.equal(json.source.type, 'USER_MANUAL');
assert.equal(json.unknowns.technique_diagnosis, 'NOT_SUPPORTED');
assert.equal(json.evidence_identity.local_match_id, session.match_id);
assert.equal(json.calculated_results.key_stages.reduce((n, row) => n + (row.sample_count ?? 0), 0), 10);
assert.doesNotMatch(exported.text, /PRIVATE-DO-NOT-EXPORT|C:\\|file_name|file_path|start_seconds|end_seconds|bound_video_identity|video_bytes/);
const timed = deuce.map((row, index) => index === 0 ? { ...row, start_seconds: 1, end_seconds: 2, start_confirmed: true, end_confirmed: true, bound_video_identity: session.session_id } : row);
const timedOutput = serializePersonalMatchReport(session, timed, context); assert(timedOutput.ok);
assert.doesNotMatch(timedOutput.text, /start_seconds|end_seconds|start_ms|end_ms|bound_video_identity/);
assert.equal(createOneGameExport(session, deuce, context).value.schema, 'ptti.my-match-one-game/0.1');
assert.equal('training_questions' in createOneGameExport(session, deuce, context).value, false);
assert.equal(JSON.stringify({ session, regular, deuce, context }), protectedInput, 'no input object or user store is changed');

const guard = createWatchCopyGuard(); let copied;
assert.equal(await guard.copy('synthetic summary', async (text) => { copied = text; }), 'copied');
assert.equal(copied, 'synthetic summary');
assert.equal(await guard.copy('synthetic summary', async () => { throw new Error('denied'); }), 'manual');
assert.equal(await guard.copy('synthetic summary'), 'manual');
let finish; const old = guard.copy('old', () => new Promise((resolve) => { finish = resolve; })); guard.invalidate();
assert.equal(await guard.copy('new', async () => {}), 'copied'); finish(); assert.equal(await old, null);

const root = new URL('../', import.meta.url); const out = new URL('.alpha-qa/goal46/', root); await mkdir(out, { recursive: true });
const kit = await build({ stdin: { contents: `export { PersonalMatchReportView, formatPersonalMatchSummary, trainingQuestionText, serializePersonalReportForLocale } from './src/PersonalMatchReport'; export { renderToStaticMarkup } from 'react-dom/server'; export { message } from './src/i18n';`, resolveDir: fileURLToPath(root), loader: 'tsx' }, bundle: true, platform: 'node', format: 'esm', packages: 'external', jsx: 'automatic', write: false });
const kitFile = new URL('report-kit.mjs', out); await writeFile(kitFile, kit.outputFiles[0].contents);
const { PersonalMatchReportView, formatPersonalMatchSummary, trainingQuestionText, serializePersonalReportForLocale, renderToStaticMarkup, message } = await import(kitFile.href + `?${Date.now()}`);
for (const locale of ['zh-CN', 'en']) {
  const text = formatPersonalMatchSummary(report, locale, selected);
  assert(text.includes('13:11')); assert(text.includes('DATA FACT')); assert(text.includes('CALCULATED RESULT')); assert(text.includes('TRAINING QUESTION'));
  assert(text.includes('★')); assert(!text.includes('undefined')); assert(!text.includes('PRIVATE-DO-NOT-EXPORT'));
  assert(report.training_questions.every((q) => trainingQuestionText(q, locale).length > 20));
  const localized = serializePersonalReportForLocale(session, deuce, context, locale, selected); assert(localized.ok);
  const localizedJson = JSON.parse(localized.text);
  assert.equal(localizedJson.presentation.locale, locale);
  assert.equal(localizedJson.presentation.summary_text, text);
  assert.equal(localizedJson.presentation.training_questions.length, report.training_questions.length);
  assert.doesNotMatch(localized.text, /PRIVATE-DO-NOT-EXPORT|C:\\|bound_video_identity|start_seconds|end_seconds/);
  await writeFile(new URL(`synthetic-report-${locale}.json`, out), localized.text);
  for (const sample of [normal.value, report, partial.value, unknown.value]) {
    let chosen; let copies = 0; let exports = 0; let journals = 0;
    const view = PersonalMatchReportView({ report: sample, locale, selectedQuestionId: null, disabled: false, onSelect: (id) => { chosen = id; }, onCopy: () => copies++, onExport: () => exports++, onOpenJournal: () => journals++, status: 'manual', manualText: formatPersonalMatchSummary(sample, locale, null) });
    const visit = (node) => {
      if (!node || typeof node !== 'object') return;
      if (node.type === 'input' && node.props.type === 'radio' && !chosen) node.props.onChange();
      if (node.type === 'button') node.props.onClick();
      for (const child of [node.props?.children].flat(Infinity)) visit(child);
    }; visit(view);
    assert(sample.training_questions.some((q) => q.question_id === chosen));
    assert.deepEqual([copies, exports, journals], [1, 1, 1]);
    const html = renderToStaticMarkup(view);
    assert.match(html, /readonly=""/i); assert(html.includes('type="radio"')); assert(!html.includes('undefined'));
    assert(!/<video|<iframe|<img/.test(html));
    if (sample.calculated_results.final.winner === null) assert(!html.includes(message(locale, 'myMatch.finalWinner').split('{')[0]));
    await writeFile(new URL(`${locale}-${sample.data_facts.recorded_point_count}-${sample.data_facts.first_server}-OFFLINE.html`, out), html);
  }
}
const [logic, component, local, app] = await Promise.all(['src/personal-match-report.mjs', 'src/PersonalMatchReport.tsx', 'src/LocalVideoReview.tsx', 'src/App.tsx'].map((file) => readFile(new URL(file, root), 'utf8')));
assert.doesNotMatch(logic + component, /fetch\s*\(|XMLHttpRequest|sendBeacon|localStorage|sessionStorage/);
assert.match(component, /textarea readOnly value=\{manualText\}/);
assert.match(component, /currentRequest\.current === key/);
assert.match(component, /finally.*revokeObjectURL/);
assert.match(component, /disabled \|\| !active/);
assert.match(local, /selection=\{reportSelection\} onSelect=\{setReportSelection\}/, 'question choice lives in the already persistent workspace');
assert.equal((local.match(/\{personalReport\}/g) ?? []).length, 2, 'same report is available in My Matches and Pro Lab');
assert.match(app, /onOpenJournal=\{\(\) => changePage\('train'\)\}/);
await writeFile(new URL('synthetic-report.json', out), exported.text);
await writeFile(new URL('README.txt', out), 'SYNTHETIC QA FIXTURES ONLY. These reports emulate manual annotation for automated tests. No real user match, media, GUI observation, download, or player result is represented.\n');
console.log('PASS: Personal Match Report normal/deuce/partial/unknown games, disjoint key intervals, real denominators and runs, unsafe/stale input rejection, versioned private export, unchanged One Game evidence, clipboard success/failure/stale-result protection, and 8 bilingual offline view renders/actions. GUI/download/real media NOT_TESTED.');
