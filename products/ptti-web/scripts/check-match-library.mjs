import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { consumeMatchLibrary } from '../src/match-library.mjs';
const raw = await readFile(new URL('../.alpha-qa/match-library/internal-review.json', import.meta.url));
const internal = JSON.parse(raw);
const publicDoc = JSON.parse(await readFile(new URL('../public/data/match-library-strict-public.json', import.meta.url), 'utf8'));
const receipt = JSON.parse(await readFile(new URL('../.alpha-qa/match-library/import-receipt.json', import.meta.url), 'utf8'));
assert.equal(createHash('sha256').update(raw).digest('hex'), receipt.artifacts['internal-review'].sha256);
const projection = consumeMatchLibrary(internal, 'INTERNAL_REVIEW');
assert.equal(projection.source_count, 35); assert.equal(projection.registered_match_count, 6);
assert.equal(new Set(projection.sources.map(source => source.source_id)).size, 35);
assert(projection.sources.every(source => source.match_link_status === 'UNKNOWN' && source.current_session_eligibility === 'NOT_EVALUATED_CURRENT_SESSION'));
assert(projection.sources.every(source => !Object.hasOwn(source, 'thumbnail')));
assert.equal(consumeMatchLibrary(publicDoc, 'STRICT_PUBLIC').source_count, 0);
assert.throws(() => consumeMatchLibrary(internal, 'STRICT_PUBLIC'), /view-mismatch/);
assert.throws(() => consumeMatchLibrary(publicDoc, 'INTERNAL_REVIEW'), /view-mismatch/);
let negativeCases = 0;
for (const mutate of [
  d => { d.contract_version = 'ptti.match-library-index/9'; },
  d => { d.local_video_assets = [{}]; },
  d => { d.video_sources.push(structuredClone(d.video_sources[0])); },
  d => { d.video_sources[0].official_url = 'javascript:alert(1)'; },
  d => { d.video_sources[0].official_url = 'https://untrusted.example/video'; },
  d => { d.video_sources[0].thumbnail.url = 'https://example.com/unlicensed.jpg'; },
  d => { d.video_sources[0].canonical_match_id = d.matches[0].match_id; },
  d => { d.matches[0].video_source_ids = [d.video_sources[0].source_id]; },
  d => { d.video_sources[0].rights.public_listing = 'FAKE_ALLOWED'; },
  d => { d.video_sources[0].availability.current_session_eligibility = 'PASS'; },
  d => { d.analysis_compatibility.automatic_join_by_title_or_player_name = true; },
  d => { delete d.video_sources[0].source_identity_status; },
]) { const value = structuredClone(internal); mutate(value); assert.throws(() => consumeMatchLibrary(value, 'INTERNAL_REVIEW')); negativeCases++; }
const forgedPublic = structuredClone(internal); forgedPublic.view = 'STRICT_PUBLIC';
assert.throws(() => consumeMatchLibrary(forgedPublic, 'STRICT_PUBLIC'), /public-grant/);
console.log(`Main Library PASS: actual 35 distinct sources / 6 unlinked matches / public0; ${negativeCases + 3} rejection cases; exact import bytes retained; no media identity promotion.`);
