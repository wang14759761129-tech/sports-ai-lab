import { verifyReviewedText } from './scripts/verify-reviewed-text.mjs';
import { verifyPlaybackSnapshot } from './scripts/verify-playback-snapshot.mjs';
import { defineConfig } from 'vite';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve, relative } from 'node:path';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { consumeReadonlyProjection } from './src/readonly-catalog.mjs';
import { consumeFanCatalog } from './src/fan-catalog.mjs';
import { buildGoal15RuntimeHealth } from './src/runtime-health.mjs';
import { canonicalJsonSha256Input, consumeGoal14FanDelivery, consumeGoal14StrictPublic } from './src/fan-content-delivery.mjs';
export default defineConfig(({ command, mode }) => {
  const review = mode === 'internal-review';
  const localRC = mode === 'local-rc';
  const goal14Candidate = mode === 'goal14-candidate';
  const goal14InternalReview = mode === 'goal14-internal-review';
  if (localRC && (command !== 'build' || !process.env.PTTI_RC_BUILD_OUT || !process.env.PTTI_PLAYBACK_CORE_SOURCE)) throw new Error('Use the recorded RC builder and isolated output/source snapshot.');
  if (command === 'build' && (review || goal14InternalReview)) throw new Error('Internal review cannot be built into a public artifact');
  const playbackIdentity = verifyPlaybackSnapshot(resolve(process.cwd(), '../..'));
  const playbackCoreSource = playbackIdentity.corePath;
  if (process.env.PTTI_PLAYBACK_CORE_SOURCE && resolve(process.env.PTTI_PLAYBACK_CORE_SOURCE) !== playbackCoreSource) throw new Error('Snapshot builds reject external Playback overrides');
  const playbackCoreDirectory = dirname(playbackCoreSource);
  const watchRoutingSource = playbackIdentity.routingPath;
  const playbackHead = 'SOURCE_SNAPSHOT:' + playbackIdentity.source_commit;
  const expectedCoreSha256 = playbackIdentity.files['products/ptti/playback-core/src/index.ts'];
  const expectedWatchRoutingSha256 = playbackIdentity.files['products/ptti/playback-core/adapters/watchRoutingContract.ts'];
  const watchRoutingDirectory = dirname(watchRoutingSource);
  const goal14PinPath = resolve('scripts/contracts/goal14-content-source-pin.json');
  const goal14SchemaIntelligence = resolve('scripts/contracts/fan-content-intelligence-v0.1.schema.json');
  const goal14SchemaDelivery = resolve('scripts/contracts/fan-content-delivery-v0.1.schema.json');
  const goal14MainAdmissionSchema = resolve('scripts/contracts/goal14-main-admission-match-library-index-v0.1.schema.json');
  const goal14MainAdmissionPath = resolve('scripts/fixtures/goal14-main-admission.json');
  const goal15PinPath = resolve('scripts/contracts/goal15-fan-universe-source-pin.json');
  const goal15Schema = resolve('scripts/contracts/goal15-main-fan-universe-match-library-index-v0.1.schema.json');
  const goal15PublicPath = resolve('public/data/match-library-strict-public.json');
  const goal14PublicPath = resolve('public/data/goal14-fan-content-strict-public.json');
  const goal14PrivateDirectory = resolve('.alpha-qa/goal14');
  const goal14PrivateDeliveryPath = resolve(goal14PrivateDirectory, 'fan-content-delivery-internal-review.json');
  const goal14PrivateBasePath = resolve(goal14PrivateDirectory, 'fan-content-internal-review.json');
  const goal14PrivateLocalizationPath = resolve(goal14PrivateDirectory, 'fan-localization-v0.1.json');
  const goal14Pin = JSON.parse(readFileSync(goal14PinPath, 'utf8'));
  const goal15Pin = JSON.parse(readFileSync(goal15PinPath, 'utf8'));
  const verifyPublicText = (path: string, expected: string) => verifyReviewedText(process.cwd(), relative(process.cwd(), path).split('\\').join('/'), expected);
  const configLoadedAt = new Date().toISOString();
  const gitHead = (cwd: string) => { try { return execFileSync('git', ['rev-parse', 'HEAD'], { cwd, encoding: 'utf8', windowsHide: true }).trim(); } catch { return 'UNKNOWN'; } };
  const serviceStartupSanHead = gitHead(process.cwd());
  const sha256Bytes = (bytes: Buffer | string) => createHash('sha256').update(bytes).digest('hex');
  for (const [path, expected, label] of [
    [goal14SchemaIntelligence, goal14Pin.sha256.intelligenceSchema, 'Goal14 intelligence schema'],
    [goal14SchemaDelivery, goal14Pin.sha256.deliverySchema, 'Goal14 delivery schema'],
    [goal14MainAdmissionSchema, goal14Pin.mainPublicAdmission.sha256.schemaBytes, 'Main public Match Library schema'],
    [goal15Schema, goal15Pin.schema_sha256, 'Goal15 Match Library schema'],
  ] as const) {
    if (!existsSync(path) || !verifyPublicText(path, expected)) throw new Error(`${label} does not match the pinned Main contract.`);
  }
  const goal14MainAdmissionBytes = readFileSync(goal14MainAdmissionPath);
  if (!verifyPublicText(goal14MainAdmissionPath, goal14Pin.mainPublicAdmission.sha256.artifactBytes)) throw new Error('Main strict-public admission bytes do not match the pinned GOAL14 artifact.');
  const goal14MainAdmission = consumeFanCatalog(JSON.parse(goal14MainAdmissionBytes.toString('utf8')));
  const mainAdmissionExpected = goal14Pin.mainPublicAdmission.expected;
  if (goal14MainAdmission.matches.length !== mainAdmissionExpected.counts.matches
    || goal14MainAdmission.sources.length !== mainAdmissionExpected.counts.sources
    || goal14MainAdmission.stars.length !== mainAdmissionExpected.counts.stars
    || goal14MainAdmission.matches[0]?.match_id !== mainAdmissionExpected.matchId
    || goal14MainAdmission.matches[0]?.video_source_ids.length !== 1
    || goal14MainAdmission.matches[0]?.video_source_ids[0] !== mainAdmissionExpected.sourceId
    || !mainAdmissionExpected.athleteIds.every((id: string) => goal14MainAdmission.stars.some((star) => star.athlete_id === id))) {
    throw new Error('Main strict-public admission identity or record counts do not match the reviewed pin.');
  }
  const goal15Bytes = readFileSync(goal15PublicPath);
  if (!verifyPublicText(goal15PublicPath, goal15Pin.artifact_sha256)) throw new Error('GOAL15 strict-public catalog bytes do not match the reviewed Main snapshot.');
  const goal15Input = JSON.parse(goal15Bytes.toString('utf8'));
  const goal15Catalog = consumeFanCatalog(goal15Input);
  const goal15Counts = {
    matches: goal15Catalog.matches.length,
    sources: goal15Catalog.sources.length,
    stars: goal15Catalog.stars.length,
    human_verified_match_source_edges: goal15Catalog.sources.filter((source) => source.match_link_status === 'HUMAN_VERIFIED').length,
    full_match_claims: goal15Catalog.sources.filter((source) => source.content_type_claim === 'FULL_MATCH').length,
    event_highlight_claims: goal15Catalog.sources.filter((source) => source.content_type_claim === 'HIGHLIGHTS').length,
    clip_claims: goal15Catalog.sources.filter((source) => source.content_type_claim === 'CLIP').length,
    unknown_content_claims: goal15Catalog.sources.filter((source) => source.content_type_claim === 'UNKNOWN').length,
    playback_passes: goal15Catalog.sources.filter((source) => source.recorded_playback_status === 'PASS').length,
  };
  if (goal15Input.contract_version !== goal15Pin.contract_version || goal15Input.view !== goal15Pin.view
    || Object.entries(goal15Pin.counts).some(([key, expected]) => goal15Counts[key as keyof typeof goal15Counts] !== expected)) {
    throw new Error('GOAL15 strict-public catalog protocol or content counts do not match the reviewed pin.');
  }
  const readGoal14InternalSnapshot = () => {
    const deliveryBytes = readFileSync(goal14PrivateDeliveryPath);
    const baseBytes = readFileSync(goal14PrivateBasePath);
    const localization = JSON.parse(readFileSync(goal14PrivateLocalizationPath, 'utf8'));
    const delivery = JSON.parse(deliveryBytes.toString('utf8'));
    if (sha256Bytes(deliveryBytes) !== goal14Pin.sha256.deliveryProjectionBytes) throw new Error('Internal delivery snapshot bytes do not match the pinned Main artifact.');
    if (sha256Bytes(baseBytes) !== goal14Pin.sha256.internalDatasetBytes || delivery.source_manifest?.base_dataset_sha256 !== sha256Bytes(baseBytes)) throw new Error('Internal delivery base dataset identity mismatch.');
    if (sha256Bytes(canonicalJsonSha256Input(localization)) !== goal14Pin.sha256.localizationCanonicalJson
      || delivery.source_manifest?.localization_sha256 !== goal14Pin.sha256.localizationCanonicalJson) throw new Error('Internal delivery localization identity mismatch.');
    consumeGoal14FanDelivery(delivery);
    return { bytes: deliveryBytes, delivery };
  };
  if (goal14InternalReview) readGoal14InternalSnapshot();
  const strictPath = resolve('public/data/web-strict-public.json');
  if (command === 'build') {
    const input = JSON.parse(readFileSync(strictPath, 'utf8'));
    const safe = consumeReadonlyProjection(input);
    consumeFanCatalog(JSON.parse(readFileSync(resolve('public/data/match-library-strict-public.json'), 'utf8')));
    if (safe.matches.length !== input.matches.length || safe.matches.reduce((n, m) => n + m.sources.length, 0) !== input.video_sources.length) throw new Error('Strict public file contains unauthorized records');
    const goal14Strict = JSON.parse(readFileSync(goal14PublicPath, 'utf8'));
    consumeGoal14StrictPublic(goal14Strict);
    if (!verifyPublicText(goal14PublicPath, goal14Pin.sha256.strictPublicBytes)) throw new Error('GOAL14 strict-public bytes do not match the pinned empty Main projection.');
  }
  return {
    define: { __PTTI_CATALOG_MODE__: JSON.stringify(review ? 'review' : 'public'), __PTTI_LOCAL_RC__: JSON.stringify(localRC), __PTTI_GOAL14_FAN_MODE__: JSON.stringify(goal14InternalReview ? 'internal-review' : 'public') },
    ...(localRC ? { build: { outDir: resolve(process.env.PTTI_RC_BUILD_OUT!), emptyOutDir: true } } : {}),
    resolve: { alias: [
      { find: '@ptti/playback-core', replacement: playbackCoreSource },
      { find: '@ptti/watch-routing', replacement: watchRoutingSource },
    ] },
    server: { host: '127.0.0.1', port: goal14InternalReview || goal14Candidate ? 4183 : review ? 4174 : 4175, strictPort: true, fs: { allow: [resolve(process.cwd()), playbackCoreDirectory, watchRoutingDirectory], deny: ['**/.env*','**/.git/**','**/.alpha-qa/**','**/scripts/fixtures/**'] } },
    preview: { host: '127.0.0.1', port: goal14InternalReview || goal14Candidate ? 4183 : 4175, strictPort: true },
    plugins: [{ name: 'loopback-alpha-bridge', configureServer(server) {
      server.middlewares.use((req, res, next) => {
        let path; try { path = decodeURIComponent((req.url || '').split('?')[0]); } catch { res.statusCode = 400; res.end(); return; }
        if (path === '/__ptti/goal14/fan-delivery.json') {
          const loopback = ['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress || '');
          if (!goal14InternalReview || req.headers['x-ptti-internal-review'] !== 'local-only' || req.headers.host !== '127.0.0.1:4183'
            || (req.headers.origin && req.headers.origin !== 'http://127.0.0.1:4183')
            || (req.headers['sec-fetch-site'] && req.headers['sec-fetch-site'] !== 'same-origin') || !loopback) { res.statusCode = 404; res.end(); return; }
          res.setHeader('Cache-Control', 'no-store'); res.setHeader('Content-Type', 'application/json; charset=utf-8'); res.setHeader('X-Content-Type-Options', 'nosniff');
          try { const snapshot = readGoal14InternalSnapshot(); res.end(snapshot.bytes); } catch { res.statusCode = 503; res.end('{}'); }
          return;
        }
        if (path === '/__ptti/goal14/health.json' || path === '/__ptti/goal14/candidate-identity.json') {
          if (!(goal14InternalReview || goal14Candidate) || req.headers.host !== '127.0.0.1:4183' || !['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress || '')) { res.statusCode = 404; res.end(); return; }
          res.setHeader('Cache-Control', 'no-store'); res.setHeader('Content-Type', 'application/json; charset=utf-8');
          res.setHeader('X-Content-Type-Options', 'nosniff');
          let currentCatalogBytes: Buffer | null = null;
          try { currentCatalogBytes = readFileSync(goal15PublicPath); } catch { /* reported as unavailable by the health contract */ }
          const goal15Runtime = buildGoal15RuntimeHealth({
            sanHead: gitHead(process.cwd()),
            sanHeadAtConfigLoad: serviceStartupSanHead,
            playbackCoreHead: playbackHead,
            playbackCoreSourceSha256: expectedCoreSha256,
            watchRoutingSourceSha256: expectedWatchRoutingSha256,
            configLoadedAt,
            startupPin: goal15Pin,
            catalogBytes: currentCatalogBytes,
          });
          const currentHead = gitHead(process.cwd());
          let worktreeClean = false;
          try { worktreeClean = execFileSync('git', ['status', '--porcelain', '--untracked-files=normal'], { cwd: process.cwd(), encoding: 'utf8', windowsHide: true }).trim() === ''; } catch { /* fail closed */ }
          res.end(JSON.stringify({
            ...goal15Runtime,
            mode: goal14InternalReview ? 'INTERNAL_REVIEW_LOCAL_ONLY' : 'FAN_CANDIDATE_LOCAL_ONLY',
            runtime_source_identity: {
              kind: 'VITE_DEV_SERVER_MUTABLE',
              service_config_commit: serviceStartupSanHead,
              current_git_commit: currentHead,
              current_worktree_clean: worktreeClean,
              config_and_current_commit_match: serviceStartupSanHead === currentHead,
              exact_served_bundle_verified: false,
            },
            service_startup: {
              ...goal15Runtime.service_startup,
              goal14: {
                main_artifact_source_commit: goal14Pin.main_artifact_source_head,
                public_admission_source_commit: goal14Pin.mainPublicAdmission.sourceCommit,
                public_admission_sha256: goal14Pin.mainPublicAdmission.sha256.artifactBytes,
                delivery_projection_sha256: goal14Pin.sha256.deliveryProjectionBytes,
              },
            },
            playback_core: playbackHead,
          }));
          return;
        }
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
          res.end(JSON.stringify({ app: 'ptti-web-review-alpha', mode: 'internal-review', version: '0.4.0', workspace: resolve(process.cwd()), san_head: head(process.cwd()), playback_head: head(playbackCoreDirectory), playback_core_source: playbackCoreSource })); return;
        }
        if (path.toLowerCase().includes('.alpha-qa') || path.toLowerCase().includes('web-internal-review.json') || path.toLowerCase().includes('/scripts/fixtures/') || path === '/data/cinema.json') { res.statusCode = 404; res.end(); return; }
        if (path !== '/__ptti/bridge.json') return next();
        if (!review || !['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress || '')) { res.statusCode = 404; res.end(); return; }
        res.setHeader('Cache-Control','no-store'); res.setHeader('Content-Type','application/json; charset=utf-8');
        try { res.end(readFileSync(resolve('.alpha-qa/bridge/web-internal-review.json'))); } catch { res.statusCode = 503; res.end('{}'); }
      });
    }, configResolved(config) { if ((review || goal14InternalReview) && config.server.host !== '127.0.0.1') throw new Error('Review must bind to loopback'); if (goal14InternalReview && config.server.port !== 4183) throw new Error('GOAL14 internal review must use isolated port 4183'); } }],
  };
});
