export function resolveReferenceLink(source, registeredSources) {
 if (!source || typeof source.source_id !== 'string' || !source.source_id || typeof source.source_url !== 'string' || !Array.isArray(registeredSources)) return null;
 const rows=registeredSources.filter(row=>row && row.source_id===source.source_id);
 if(rows.length!==1 || rows[0].source_url!==source.source_url) return null;
 try {
  const url=new URL(source.source_url), host=url.hostname.toLowerCase();
  if(url.protocol!=='https:'||url.username||url.password||url.port||url.hash||!host.includes('.')||host==='localhost'||host.endsWith('.local')||/^[\d.]+$/.test(host))return null;
  if(['youtube.com','www.youtube.com','m.youtube.com','youtu.be','bilibili.com','www.bilibili.com'].includes(host))return null;
  return source.source_url;
 } catch {return null;}
}
