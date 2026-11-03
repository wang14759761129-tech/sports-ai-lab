import { defineConfig } from 'vite';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { consumeReadonlyProjection } from './src/readonly-catalog.mjs';
import { consumeMatchLibrary } from './src/match-library.mjs';
import { verifyPinnedPlaybackCore } from './src/playback-core-pin.mjs';
export default defineConfig(({ command, mode }) => {
  const review = mode === 'internal-review';
  const localRC = mode === 'local-rc';
  if (localRC && (command !== 'build' || !process.env.PTTI_RC_BUILD_OUT || !process.env.PTTI_PLAYBACK_CORE_SOURCE)) throw new Error('Use the recorded RC builder and isolated output/source snapshot.');
  if (command === 'build' && review) throw new Error('Internal review cannot be built into a public artifact');
  const pinnedCore = verifyPinnedPlaybackCore(process.cwd(), process.env.PTTI_PLAYBACK_CORE_SOURCE ?? null);
  const playbackCoreSource = resolve(pinnedCore.sourcePath);
  if (!existsSync(playbackCoreSource)) throw new Error(`Pinned Playback Core source not found: ${playbackCoreSource}`);
  const playbackCoreDirectory = dirname(playbackCoreSource);
  const strictPath = resolve('public/data/web-strict-public.json');
  if (command === 'build') {
    const input = JSON.parse(readFileSync(strictPath, 'utf8'));
    const safe = consumeReadonlyProjection(input);
    consumeMatchLibrary(JSON.parse(readFileSync(resolve('public/data/match-library-strict-public.json'), 'utf8')), 'STRICT_PUBLIC');
    if (safe.matches.length !== input.matches.length || safe.matches.reduce((n, m) => n + m.sources.length, 0) !== input.video_sources.length) throw new Error('Strict public file contains unauthorized records');
  }
  return {
    define: { __PTTI_CATALOG_MODE__: JSON.stringify(review ? 'review' : 'public'), __PTTI_LOCAL_RC__: JSON.stringify(localRC), __PTTI_PLAYBACK_CORE_COMMIT__: JSON.stringify(pinnedCore.coreCommit), __PTTI_PLAYBACK_CORE_SOURCE_SHA256__: JSON.stringify(pinnedCore.sourceHash) },
    ...(localRC ? { build: { outDir: resolve(process.env.PTTI_RC_BUILD_OUT!), emptyOutDir: true } } : {}),
    resolve: { alias: [{ find: '@ptti/playback-core', replacement: playbackCoreSource }] },
    server: { host: '127.0.0.1', port: review ? 4174 : 4175, strictPort: true, fs: { allow: [resolve(process.cwd()), playbackCoreDirectory], deny: ['**/.env*','**/.git/**','**/.alpha-qa/**','**/scripts/fixtures/**'] } },
    preview: { host: '127.0.0.1', port: 4175, strictPort: true },
    plugins: [{ name: 'loopback-alpha-bridge', configureServer(server) {
      server.middlewares.use((req, res, next) => {
        let path; try { path = decodeURIComponent((req.url || '').split('?')[0]); } catch { res.statusCode = 400; res.end(); return; }
        if (path === '/__ptti/match-library.json') {
          if (!review || req.headers['x-ptti-review'] !== 'local-only' || req.headers.host !== '127.0.0.1:4174' || (req.headers.origin && req.headers.origin !== 'http://127.0.0.1:4174') || (req.headers['sec-fetch-site'] && req.headers['sec-fetch-site'] !== 'same-origin') || !['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress || '')) { res.statusCode = 404; res.end(); return; }
          res.setHeader('Cache-Control', 'no-store'); res.setHeader('Content-Type', 'application/json; charset=utf-8');
          try {
            const raw = readFileSync(resolve('.alpha-qa/match-library/internal-review.json'));
            const receipt = JSON.parse(readFileSync(resolve('.alpha-qa/match-library/import-receipt.json'), 'utf8'));
            if (createHash('sha256').update(raw).digest('hex') !== receipt.artifacts['internal-review'].sha256) throw new Error('Snapshot bytes changed');
            consumeMatchLibrary(JSON.parse(raw.toString('utf8')), 'INTERNAL_REVIEW'); res.end(raw);
          } catch { res.statusCode = 503; res.end('{}'); } return;
        }
        if (path === '/__ptti/demo-review.json') {
          if (!review || !['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress || '')) { res.statusCode = 404; res.end(); return; }
          res.setHeader('Cache-Control', 'no-store'); res.setHeader('Content-Type', 'application/json; charset=utf-8');
          try {
            const quick = JSON.parse(readFileSync(resolve('scripts/fixtures/review-targets/quick-input.json'), 'utf8'));
            const targets = JSON.parse(readFileSync(resolve('scripts/fixtures/review-targets/targets.json'), 'utf8'));
            if (quick.dataset_class !== 'SIMULATED_ONLY' || targets.evidence_status !== 'SIMULATED_ONLY') throw new Error('Not a simulated demo');
            res.end(JSON.stringify({ quick, targets }));
          } catch { res.statusCode = 503; res.end('{}'); } return;
        }
        if (path === '/__ptti/health.json') {
          if (!review || !['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress || '')) { res.statusCode = 404; res.end(); return; }
          res.setHeader('Cache-Control', 'no-store'); res.setHeader('Content-Type', 'application/json; charset=utf-8');
          const head = (cwd: string) => { try { return execFileSync('git', ['rev-parse', 'HEAD'], { cwd, encoding: 'utf8', windowsHide: true }).trim(); } catch { return 'UNKNOWN'; } };
          res.end(JSON.stringify({ app: 'ptti-web-review-alpha', mode: 'internal-review', version: '0.4.0', workspace: resolve(process.cwd()), san_head: head(process.cwd()), playback_head: pinnedCore.coreCommit, playback_core_source_sha256: pinnedCore.sourceHash, playback_core_source: playbackCoreSource })); return;
        }
        if (path.toLowerCase().includes('.alpha-qa') || path.toLowerCase().includes('web-internal-review.json') || path.toLowerCase().includes('/scripts/fixtures/') || path === '/data/cinema.json') { res.statusCode = 404; res.end(); return; }
        if (path !== '/__ptti/bridge.json') return next();
        if (!review || !['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress || '')) { res.statusCode = 404; res.end(); return; }
        res.setHeader('Cache-Control','no-store'); res.setHeader('Content-Type','application/json; charset=utf-8');
        try { res.end(readFileSync(resolve('.alpha-qa/bridge/web-internal-review.json'))); } catch { res.statusCode = 503; res.end('{}'); }
      });
    }, configResolved(config) { if (review && config.server.host !== '127.0.0.1') throw new Error('Review must bind to loopback'); } }],
  };
});
