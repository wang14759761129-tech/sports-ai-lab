const family = value => value === 'YOUTUBE' || value === 'YOUTUBE_OFFICIAL' ? 'YOUTUBE' : value === 'BILIBILI' || value === 'BILIBILI_OFFICIAL' ? 'BILIBILI' : null;
export function resolveOfficialLink(source, registry, matchId = null) {
 if (!source || !Array.isArray(registry) || !family(source.provider) || typeof source.video_id !== 'string' || typeof source.source_url !== 'string') return {status:'UNAVAILABLE',url:null};
 const p=family(source.provider), id=source.video_id, nested=source.video_source;
 const matches=registry.filter(v=>v && family(v.provider)===p && v.video_id===id);
 if(matches.length!==1) return {status:'UNAVAILABLE',url:null};
 const recorded=matches[0];
 if(!source.source_key && !nested?.source_id) return {status:'UNAVAILABLE',url:null};
 if(!Number.isFinite(Date.parse(recorded.metadata_verified_at || recorded.source_verified_at || '')) || (!recorded.provenance?.metadata_method && !recorded.source_verified_at)) return {status:'UNAVAILABLE',url:null};
 if(recorded.source_url!==source.source_url || (source.source_key && recorded.source_key!==source.source_key) || (nested?.source_id && nested.source_id!==id) || (nested?.provider && family(nested.provider)!==p) || (recorded.video_source?.source_id && recorded.video_source.source_id!==id)) return {status:'UNAVAILABLE',url:null};
 if(matchId!==null && (typeof matchId!=='string' || source.match_id!==matchId || recorded.match_id!==matchId || (nested?.match_id && nested.match_id!==matchId))) return {status:'UNAVAILABLE',url:null};
 if(source.match_id && recorded.match_id!==source.match_id) return {status:'UNAVAILABLE',url:null};
 if(['UNAVAILABLE','RESTRICTED'].includes(source.playback_status) || ['DENIED','NOT_ALLOWED'].includes(source.external_viewing_permission) || ['DENIED','NOT_ALLOWED'].includes(recorded.external_viewing_permission)) return {status:'UNAVAILABLE',url:null};
 if(source.source_key && ![`${p}:${id}`,`${p}_OFFICIAL:${id}`].includes(source.source_key)) return {status:'UNAVAILABLE',url:null};
 try {const u=new URL(source.source_url);if(u.protocol!=='https:'||u.username||u.password||u.port||u.hash)return {status:'UNAVAILABLE',url:null};
 if(p==='YOUTUBE') {if(!/^[\w-]{11}$/.test(id)||!['youtube.com','www.youtube.com','m.youtube.com'].includes(u.hostname)||u.pathname!=='/watch'||u.searchParams.size!==1||u.searchParams.getAll('v').length!==1||u.searchParams.get('v')!==id)return {status:'UNAVAILABLE',url:null};}
 else if(!/^BV[A-Za-z0-9]{10}$/.test(id)||!['bilibili.com','www.bilibili.com'].includes(u.hostname)||![`/video/${id}`,`/video/${id}/`].includes(u.pathname)||u.search)return {status:'UNAVAILABLE',url:null};
 return {status:'REGISTERED',url:source.source_url};}catch{return {status:'UNAVAILABLE',url:null};}
}
