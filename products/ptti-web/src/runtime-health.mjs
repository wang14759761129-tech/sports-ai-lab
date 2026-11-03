import { createHash } from 'node:crypto';
import { consumeFanCatalog } from './fan-catalog.mjs';

function sha256(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function countCatalog(input, catalog) {
  return {
    matches: catalog.matches.length,
    sources: catalog.sources.length,
    stars: catalog.stars.length,
    human_verified_match_source_edges: catalog.sources.filter((source) => source.match_link_status === 'HUMAN_VERIFIED').length,
    full_match_claims: catalog.sources.filter((source) => source.content_type_claim === 'FULL_MATCH').length,
    event_highlight_claims: catalog.sources.filter((source) => source.content_type_claim === 'HIGHLIGHTS').length,
    clip_claims: catalog.sources.filter((source) => source.content_type_claim === 'CLIP').length,
    unknown_content_claims: catalog.sources.filter((source) => source.content_type_claim === 'UNKNOWN').length,
    playback_passes: catalog.sources.filter((source) => source.recorded_playback_status === 'PASS').length,
    source_manifest_entries: input.source_manifest.length,
  };
}

/**
 * Describe the identity loaded when this Vite service started separately from
 * the exact strict-public catalog bytes currently on disk and served by it.
 */
export function buildGoal15RuntimeHealth({ sanHead, sanHeadAtConfigLoad, playbackCoreHead, playbackCoreSourceSha256, watchRoutingSourceSha256, configLoadedAt, startupPin, catalogBytes }) {
  const startupPinIdentity = {
    main_source_commit: startupPin.main_source_commit,
    contract_version: startupPin.contract_version,
    view: startupPin.view,
    catalog_sha256: startupPin.artifact_sha256,
    schema_sha256: startupPin.schema_sha256,
  };
  let actualSha = null;
  let current = {
    consumer_validation: 'FAIL',
    validation_result: 'CATALOG_BYTES_UNAVAILABLE',
    sha256: null,
    contract_version: null,
    view: null,
    startup_pin_match: null,
    counts: null,
  };

  if (catalogBytes !== null && catalogBytes !== undefined) {
    actualSha = sha256(catalogBytes);
    current.sha256 = actualSha;
    current.startup_pin_match = actualSha === startupPin.artifact_sha256;
    try {
      const input = JSON.parse(Buffer.from(catalogBytes).toString('utf8'));
      current.contract_version = typeof input.contract_version === 'string' ? input.contract_version : null;
      current.view = typeof input.view === 'string' ? input.view : null;
      const catalog = consumeFanCatalog(input);
      if (!Array.isArray(input.source_manifest) || input.source_manifest.length !== 0) {
        throw new Error('public-source-manifest-must-be-empty');
      }
      current.consumer_validation = 'PASS';
      current.validation_result = 'CONSUMER_AND_PUBLIC_MANIFEST_VALID';
      current.counts = countCatalog(input, catalog);
    } catch {
      current.consumer_validation = 'FAIL';
      current.validation_result = 'CATALOG_INVALID_OR_PUBLIC_MANIFEST_NOT_EMPTY';
      current.counts = null;
    }
  }

  return {
    mode: 'INTERNAL_REVIEW_LOCAL_ONLY',
    san_git_head_current: sanHead,
    service_startup: {
      config_loaded_at_utc: configLoadedAt,
      san_git_head_observed_at_config_load: sanHeadAtConfigLoad,
      playback_core_git_head: playbackCoreHead,
      playback_core_source_sha256: playbackCoreSourceSha256,
      watch_routing_source_sha256: watchRoutingSourceSha256,
      goal15_pin: startupPinIdentity,
    },
    current_strict_public_catalog: current,
  };
}
