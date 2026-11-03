export function validateProjection(p){
 if(!p||p.contract_version!=='ptti.cinema-match-projection/0.1'||p.audience!=='STRICT_PUBLIC_METADATA_EXTERNAL_LINK_ONLY'||!Array.isArray(p.matches)||!Array.isArray(p.video_sources)||!Array.isArray(p.evidence_sources))throw Error('Unsupported match projection');
 const ids=new Set(),sources=new Map();
 for(const m of p.matches){if(typeof m.match_id!=='string'||!m.match_id||ids.has(m.match_id)||m.media_sha256!==null||m.media_sha256_status!=='UNKNOWN'||!Array.isArray(m.source_ids)||!Array.isArray(m.participants)||!m.event||typeof m.event.name!=='string')throw Error('Invalid match');ids.add(m.match_id)}
 for(const s of p.video_sources){if(typeof s.source_id!=='string'||sources.has(s.source_id)||s.provider!=='YOUTUBE'||!/^[A-Za-z0-9_-]{11}$/.test(s.video_id)||s.official_url!==`https://www.youtube.com/watch?v=${s.video_id}`||s.media_sha256!==null||s.embedding!=='UNKNOWN'||s.download!=='NOT_GRANTED'||s.redistribution!=='NOT_GRANTED'||s.external_navigation!=='ALLOWED_AS_RECORDED'||s.page_status!=='NOT_TESTED'||s.playback_status!=='NOT_TESTED'||(s.match_id!==null&&!ids.has(s.match_id)))throw Error('Invalid source');sources.set(s.source_id,s)}
 for(const m of p.matches){if(new Set(m.source_ids).size!==m.source_ids.length||m.source_ids.some(id=>!sources.has(id)||sources.get(id).match_id!==m.match_id))throw Error('Invalid match source relation')}
 for(const s of sources.values())if(s.match_id!==null&&!p.matches.find(m=>m.match_id===s.match_id).source_ids.includes(s.source_id))throw Error('Unreciprocated source relation');
 return p;
}
