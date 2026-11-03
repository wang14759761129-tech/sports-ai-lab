export const FAN_MEDIA_INDEX_VERSION = 'ptti.web-public-media-index/0.1';

const ROOT_KEYS = ['assets', 'contract_version'];
const ASSET_KEYS = [
  'asset_id', 'kind', 'subject_id', 'display_permission', 'source_page_url', 'photographer',
  'attribution', 'license', 'license_url', 'derivative_status', 'derivative_license', 'derivative_license_url',
  'derivative_notice', 'context_notice', 'actual_event', 'alt', 'sizes', 'object_position',
  'renditions', 'depicted_athlete_ids', 'match_evidence',
];
const RENDITION_KEYS = ['src', 'width', 'height', 'mime_type', 'sha256'];

function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function text(value) { return typeof value === 'string' && value.trim().length > 0; }
function sha256(value) { return typeof value === 'string' && /^[a-f0-9]{64}$/i.test(value); }
function https(value) { return typeof value === 'string' && /^https:\/\//i.test(value); }
function localMediaPath(value) {
  return typeof value === 'string' && /^\/media\/goal1[67]\//.test(value)
    && !value.includes('..') && !/[?#\\%]/.test(value) && !/^\/\//.test(value);
}
function exactKeys(value, expected) {
  if (!object(value)) return false;
  const actual = Object.keys(value).sort();
  const required = [...expected].sort();
  return actual.length === required.length && actual.every((key, index) => key === required[index]);
}

export function validatePublicMediaAsset(asset, catalog = null) {
  const issues = [];
  if (!object(asset)) return ['ASSET_NOT_OBJECT'];
  if (!exactKeys(asset, ASSET_KEYS)) issues.push('ASSET_FIELDS_NOT_ALLOWLISTED');
  if (!text(asset.asset_id)) issues.push('ASSET_ID_MISSING');
  if (!['ATHLETE_PORTRAIT', 'MATCH_PHOTOGRAPH'].includes(asset.kind)) issues.push('ASSET_KIND_INVALID');
  if (!text(asset.subject_id)) issues.push('SUBJECT_ID_MISSING');
  if (asset.display_permission !== 'ALLOWED') issues.push('DISPLAY_PERMISSION_NOT_CLEARED');
  if (!https(asset.source_page_url)) issues.push('SOURCE_PAGE_URL_INVALID');
  if (!text(asset.photographer) || !text(asset.attribution)) issues.push('MEDIA_ATTRIBUTION_MISSING');
  if (!text(asset.license) || !https(asset.license_url)) issues.push('MEDIA_LICENSE_MISSING');
  if (asset.derivative_status !== 'PERMITTED' || !text(asset.derivative_notice)
      || !text(asset.derivative_license) || !https(asset.derivative_license_url)) issues.push('MEDIA_DERIVATIVE_REVIEW_INCOMPLETE');
  if (!['CC BY-SA 2.0', 'CC BY-SA 4.0', 'CC BY 3.0', 'CC0 1.0', 'Test fixture only'].includes(asset.license)) issues.push('MEDIA_LICENSE_NOT_ALLOWLISTED');
  if (typeof asset.license === 'string' && /\bBY-SA\b/i.test(asset.license)
      && (asset.derivative_license !== asset.license || asset.derivative_license_url !== asset.license_url)) issues.push('SHARE_ALIKE_DERIVATIVE_LICENSE_MISMATCH');
  if (!text(asset.actual_event)) issues.push('MEDIA_EVENT_CONTEXT_MISSING');
  if (!text(asset.context_notice)) issues.push('MEDIA_CONTEXT_NOTICE_MISSING');
  if (!text(asset.alt) || !text(asset.sizes)) issues.push('MEDIA_ACCESSIBILITY_OR_SIZES_MISSING');
  if (typeof asset.object_position !== 'string' || !/^(?:\d{1,3}%\s+){1}\d{1,3}%$/.test(asset.object_position)
      || asset.object_position.split(/\s+/).some((part) => Number.parseInt(part, 10) > 100)) issues.push('MEDIA_CROP_POSITION_INVALID');
  if (!Array.isArray(asset.renditions) || asset.renditions.length === 0) issues.push('MEDIA_RENDITIONS_MISSING');
  else {
    if (!asset.renditions.some((rendition) => ['image/webp', 'image/jpeg', 'image/png'].includes(rendition?.mime_type))) issues.push('MEDIA_FALLBACK_RENDITION_MISSING');
    const seenPaths = new Set();
    for (const rendition of asset.renditions) {
      if (!exactKeys(rendition, RENDITION_KEYS) || !localMediaPath(rendition.src)
          || !Number.isInteger(rendition.width) || rendition.width < 1
          || !Number.isInteger(rendition.height) || rendition.height < 1
          || !['image/avif', 'image/webp', 'image/jpeg', 'image/png'].includes(rendition.mime_type)
          || !sha256(rendition.sha256)) issues.push('MEDIA_RENDITION_INVALID');
      if (seenPaths.has(rendition?.src)) issues.push('MEDIA_RENDITION_DUPLICATE_PATH');
      seenPaths.add(rendition?.src);
    }
  }
  if (!Array.isArray(asset.depicted_athlete_ids) || asset.depicted_athlete_ids.length === 0
      || asset.depicted_athlete_ids.some((id) => !text(id))) issues.push('DEPICTED_ATHLETE_IDS_INVALID');

  if (asset.kind === 'ATHLETE_PORTRAIT') {
    if (!asset.subject_id.startsWith('athlete:') || !asset.depicted_athlete_ids?.includes(asset.subject_id)) issues.push('ATHLETE_IDENTITY_NOT_EXACT');
    if (asset.match_evidence !== null) issues.push('PORTRAIT_MATCH_ASSOCIATION_NOT_ALLOWED');
    if (catalog && !catalog.stars?.some((star) => star.athlete_id === asset.subject_id)) issues.push('ATHLETE_ID_NOT_IN_STRICT_PUBLIC_CATALOG');
  }
  if (asset.kind === 'MATCH_PHOTOGRAPH') {
    if (!asset.subject_id.startsWith('pro:wtt:')) issues.push('MATCH_ID_INVALID');
    const evidence = asset.match_evidence;
    if (!object(evidence) || evidence.match_id !== asset.subject_id || !text(evidence.evidence_source_id)) issues.push('MATCH_ASSOCIATION_EVIDENCE_MISSING');
    if (catalog) {
      const match = catalog.matches?.find((row) => row.match_id === asset.subject_id);
      if (!match) issues.push('MATCH_ID_NOT_IN_STRICT_PUBLIC_CATALOG');
      else {
        if (asset.actual_event !== match.event && asset.actual_event !== match.event_id) issues.push('MATCH_EVENT_IDENTITY_MISMATCH');
        if (!match.evidence_source_ids?.includes(evidence?.evidence_source_id)) issues.push('MATCH_EVIDENCE_SOURCE_NOT_LINKED');
      }
      if (!matchEvidenceMapsToSubject(evidence, asset.subject_id)) issues.push('MATCH_EVIDENCE_SUBJECT_MISMATCH');
    }
  }
  return [...new Set(issues)];
}

function matchEvidenceMapsToSubject(evidence, matchId) {
  return object(evidence) && evidence.match_id === matchId && text(evidence.evidence_source_id);
}

export function createPublicMediaIndex(input, catalog = null) {
  if (!object(input) || input.contract_version !== FAN_MEDIA_INDEX_VERSION || !Array.isArray(input.assets)) {
    throw new Error('PUBLIC_MEDIA_INDEX_VERSION_OR_SHAPE_INVALID');
  }
  if (!exactKeys(input, ROOT_KEYS)) throw new Error('PUBLIC_MEDIA_INDEX_FIELDS_NOT_ALLOWLISTED');
  const assetIds = new Set();
  const subjects = new Set();
  const assets = [];
  for (const asset of input.assets) {
    const issues = validatePublicMediaAsset(asset, catalog);
    if (issues.length) throw new Error(`PUBLIC_MEDIA_ASSET_REJECTED:${asset?.asset_id ?? 'unknown'}:${issues.join(',')}`);
    if (assetIds.has(asset.asset_id)) throw new Error('PUBLIC_MEDIA_DUPLICATE_ASSET_ID');
    const subjectKey = `${asset.kind}:${asset.subject_id}`;
    if (subjects.has(subjectKey)) throw new Error('PUBLIC_MEDIA_DUPLICATE_SUBJECT');
    assetIds.add(asset.asset_id);
    subjects.add(subjectKey);
    assets.push(Object.freeze({
      ...asset,
      renditions: Object.freeze(asset.renditions.map((rendition) => Object.freeze({ ...rendition }))),
      depicted_athlete_ids: Object.freeze([...asset.depicted_athlete_ids]),
      match_evidence: asset.match_evidence ? Object.freeze({ ...asset.match_evidence }) : null,
    }));
  }
  return Object.freeze({
    assets: Object.freeze(assets),
    athletes: new Map(assets.filter((asset) => asset.kind === 'ATHLETE_PORTRAIT').map((asset) => [asset.subject_id, asset])),
    matches: new Map(assets.filter((asset) => asset.kind === 'MATCH_PHOTOGRAPH').map((asset) => [asset.subject_id, asset])),
  });
}

/** Evaluate Main's actual GOAL16 review record; NOT_CLEARED records always fail closed. */
export function evaluateGoal16Candidate(asset, { catalog, localAsset = null, intendedKind = 'ATHLETE_PORTRAIT' } = {}) {
  const reasons = [];
  if (!object(asset)) return { eligible: false, reasons: ['ASSET_NOT_OBJECT'] };
  if (asset.display_permission !== 'ALLOWED') reasons.push('DISPLAY_PERMISSION_NOT_CLEARED');
  if (!text(asset.photographer) || !text(asset.attribution) || !text(asset.license) || !https(asset.license_url)) reasons.push('ATTRIBUTION_OR_LICENSE_INCOMPLETE');
  if (!Array.isArray(asset.athlete_ids) || asset.athlete_ids.length === 0
      || asset.athlete_ids.some((id) => !text(id) || !catalog?.stars?.some((star) => star.athlete_id === id))) reasons.push('ATHLETE_IDENTITY_MISMATCH');
  if (!Array.isArray(asset.depicted_athletes) || asset.depicted_athletes.length === 0
      || !['VISUALLY_VERIFIED', 'HUMAN_VISUAL_IDENTITY_VERIFIED'].includes(asset.depiction_status)) reasons.push('DEPICTION_NOT_VISUALLY_VERIFIED');
  if (asset.crop_review !== 'APPROVED_FOR_DISPLAY') reasons.push('CROP_NOT_APPROVED');
  if (asset.media_sha256_status !== 'COMPUTED_FROM_REVIEWED_LOCAL_COPY' || !sha256(asset.media_sha256)) reasons.push('MEDIA_SHA256_NOT_VERIFIED');
  if (!localAsset || !sha256(localAsset.sha256) || localAsset.sha256.toLowerCase() !== asset.media_sha256?.toLowerCase()) reasons.push('LOCAL_MEDIA_SHA256_MISMATCH');
  if (intendedKind === 'MATCH_PHOTOGRAPH') {
    const match = catalog?.matches?.find((row) => row.match_id === asset.match_id);
    if (!match || asset.match_link_status !== 'HUMAN_VERIFIED') reasons.push('MATCH_IDENTITY_NOT_EXACT');
    if (match && asset.actual_event !== match.event && asset.actual_event !== match.event_id) reasons.push('MATCH_EVENT_MISMATCH');
  } else if (asset.match_id !== null) reasons.push('PORTRAIT_HAS_UNVERIFIED_MATCH_ASSOCIATION');
  return { eligible: reasons.length === 0, reasons: [...new Set(reasons)] };
}
