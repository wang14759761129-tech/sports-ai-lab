// Read-only adapter for the pinned strict-public projection; never opens media.
export const MATCH_CONTRACT_VERSION = 'ptti.match/1.0';
export const PUBLIC_PROJECTION_SHA256 = '5a94b6c9f2196b31ba9c151188b31900d4fbd50c2c5ecda6e95efcdde639c329';
function reject(reason) { throw new TypeError(`MATCH_CONTRACT:${reason}`); }
// Preferred San boundary: verify exact reviewed bytes before parsing any data.
export async function parsePinnedMatchContract(bytes, matchId) {
  if (!(bytes instanceof Uint8Array) || !globalThis.crypto?.subtle) reject('BYTES_OR_CRYPTO');
  const hash=await globalThis.crypto.subtle.digest('SHA-256',bytes);
  const actual=Array.from(new Uint8Array(hash),x=>x.toString(16).padStart(2,'0')).join('');
  if(actual!==PUBLIC_PROJECTION_SHA256) reject('PROJECTION_SHA_MISMATCH');
  let parsed; try { parsed=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes)); } catch { reject('PROJECTION_JSON'); }
  return createMatchContract(parsed,matchId);
}
function safeWatch(source) {
  if (source?.provider !== 'YOUTUBE' || !/^[A-Za-z0-9_-]{11}$/.test(source?.video_id || '') || source.external_navigation !== 'ALLOWED_AS_RECORDED') reject('SOURCE_NOT_ADMITTED');
  let u; try { u=new URL(source.official_url); } catch { reject('INVALID_URL'); }
  if (u.protocol !== 'https:' || u.hostname !== 'www.youtube.com' || u.port || u.username || u.password || u.pathname !== '/watch' || u.hash || [...u.searchParams.keys()].length !== 1 || u.searchParams.get('v') !== source.video_id) reject('URL_IDENTITY');
  return source.official_url;
}
export function createMatchContract(projection, matchId) {
  if (projection?.contract_version !== 'ptti.cinema-match-projection/0.1' || projection?.audience !== 'STRICT_PUBLIC_METADATA_EXTERNAL_LINK_ONLY' || !Array.isArray(projection.matches) || !Array.isArray(projection.video_sources) || !Array.isArray(projection.evidence_sources)) reject('PROJECTION');
  if (typeof matchId !== 'string' || !matchId) reject('MATCH_ID');
  const matches=projection.matches.filter(m => m.match_id === matchId);
  if (matches.length !== 1) reject('MATCH_NOT_UNIQUE');
  const match=matches[0];
  if (!match.event || typeof match.event.name !== 'string' || !Array.isArray(match.participants) || !Array.isArray(match.source_ids) || new Set(match.source_ids).size !== match.source_ids.length) reject('MATCH_INVALID');
  const sources=match.source_ids.map(sourceId => {
    const rows=projection.video_sources.filter(s=>s.source_id===sourceId);
    if(rows.length!==1 || rows[0].match_id!==matchId) reject('SOURCE_LINK');
    const source=rows[0], url=safeWatch(source);
    if(source.media_sha256!==null || source.media_sha256_status!=='UNKNOWN' || source.embedding!=='UNKNOWN' || source.download!=='NOT_GRANTED' || source.redistribution!=='NOT_GRANTED' || source.evidence_url!==url || !Array.isArray(source.evidence_source_ids)) reject('RIGHTS_OR_SHA');
    return {source_id:sourceId,provider:source.provider,video_id:source.video_id,official_url:url,publisher:source.publisher??null,source_identity_status:source.identity_status??'UNKNOWN',evidence_url:source.evidence_url??null,evidence_source_ids:source.evidence_source_ids??[],media_sha256:null,media_sha256_status:'UNKNOWN',authorization:{external_navigation:'ALLOWED_AS_RECORDED',embedding:'UNKNOWN',download:'NOT_GRANTED',redistribution:'NOT_GRANTED'},availability:{page:'NOT_TESTED',playback:'NOT_TESTED',current_session:'NOT_EVALUATED_CURRENT_SESSION'}};
  });
  const evidenceIds=Array.isArray(match.evidence_source_ids)?match.evidence_source_ids:[];
  return {contract_version:MATCH_CONTRACT_VERSION,data_origin:'SOURCE_BACKED',match_id:matchId,event:match.event,participants:match.participants,match_type:match.match_type??'UNKNOWN',round:match.round??'UNKNOWN',match_identity_status:match.identity_status??'UNKNOWN',media_sha256:null,media_sha256_status:'UNKNOWN',sources,evidence_sources:projection.evidence_sources.filter(e=>evidenceIds.includes(e.source_id))};
}
