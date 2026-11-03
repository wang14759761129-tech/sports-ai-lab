import { readFile } from 'node:fs/promises';
import { consumeMatchMedia, resolveWebIds } from '../runtime/match-media-consumer.mjs';

const payload = JSON.parse(await readFile(new URL('../generated/alpha-rc/web-internal-review.json', import.meta.url), 'utf8'));
const mapping = JSON.parse(await readFile(new URL('../runtime/web-id-map.json', import.meta.url), 'utf8'));
if (mapping.mapping_version !== 'ptti.web-id-map/0.1') throw new Error('Unsupported ID mapping version');
const internal = consumeMatchMedia(payload, { view: 'internal-review' });
const publicCatalog = consumeMatchMedia(payload, { view: 'strict-public' });
console.log(JSON.stringify({ contract_version: internal.contract_version, internal_matches: internal.matches.length,
  strict_public_sources: publicCatalog.video_sources.length,
  rows: mapping.items.map(item => {
    const ids = resolveWebIds(item.web_record_id, mapping.items, internal);
    const match = internal.matches.find(row => row.match_id === ids.match_id);
    const source = internal.video_sources.find(row => row.source_id === ids.source_id);
    return { ...ids, event: match.event, match_identity: match.identity_status,
      players_unassigned: match.participant_names_unassigned || [], player_ids: match.participants.flatMap(side => side.members.map(member => member.player_id)),
      match_link_status: source.match_link_status, resource_kind: source.resource_kind, canonical_url: source.canonical_url,
      rights: source.rights, territory: source.territory.status,
      external_visual: source.evidence.external_video_page.status,
      embedded: source.evidence.embed_playback.status, desktop_native: source.evidence.desktop_native_playback.status };
  }) }, null, 2));
