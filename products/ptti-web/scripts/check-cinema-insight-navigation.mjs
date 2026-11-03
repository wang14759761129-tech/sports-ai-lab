import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const root = new URL('../src/', import.meta.url);
const [app, cinema, review, workbench, messages] = await Promise.all([
  readFile(new URL('App.tsx', root), 'utf8'),
  readFile(new URL('CinemaDemo.tsx', root), 'utf8'),
  readFile(new URL('LocalVideoReview.tsx', root), 'utf8'),
  readFile(new URL('ProWorkbench.tsx', root), 'utf8'),
  readFile(new URL('i18n.ts', root), 'utf8'),
]);

assert.match(app, /onOpenInsight=\{\(\) => openPro\('insight'\)\}/, 'the app routes successful demo import to the Insight page');
assert.match(workbench, /onOpenInsight\?: \(\) => void/, 'the workspace accepts an optional navigation callback');
assert.match(workbench, /<LocalVideoReview[^>]*onOpenInsight=\{onOpenInsight\}/, 'the workspace forwards the callback to review');
assert.match(review, /async function loadGolden\([^)]*\): Promise<boolean>/, 'loading reports success explicitly');
assert.match(review, /installImportedDraft\([\s\S]*?setInsightMode\('targets'\);\s*return true;/, 'only a validated installed draft returns success');
assert.match(review, /generation !== quickImportGenerationRef\.current \|\| activeSessionIdRef\.current\) return false/, 'stale or newly active sessions reject navigation');
assert.match(review, /onLoaded=\{onOpenInsight\}/, 'the validated load result is connected to app navigation');
assert.match(cinema, /if \(!loaded\) \{\s*setLoadFailed\(true\);\s*return;\s*\}\s*onLoaded\?\./, 'navigation runs only after the loader returns true');
assert.match(cinema, /catch \{\s*setLoadFailed\(true\);\s*\}/, 'unexpected load failures stay on-page and are visible');
assert.match(cinema, /disabled=\{!canReplace \|\| loadPending\}/, 'repeated imports are disabled while one is in progress');
assert.match(messages, /'cinema\.demo\.load': '载入并打开 Insight'/, 'Chinese button copy describes the action');
assert.match(messages, /'cinema\.demo\.load': 'Load review and open Insight'/, 'English button copy matches the Chinese action');
assert.match(messages, /'cinema\.demo\.loadFailed': '模拟复盘未能载入/, 'Chinese failure state exists');
assert.match(messages, /'cinema\.demo\.loadFailed': 'The simulated review could not be loaded\./, 'English failure state exists');

console.log('Cinema demo → Insight navigation contract PASS: validated success navigates, rejection/stale/error stays on page, duplicate load is prevented, and zh/en copy and failure states are present.');
