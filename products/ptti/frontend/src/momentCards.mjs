// Cinema Moment Cards — pure logic, no React, no network, no video download.
// Storage is isolated: browser localStorage key below, never the production
// matches.db. A caller may inject a memory storage object for tests.
// A "match" here is a registered FeedVideo (official:<video_id> / local:<video_id>).
// It is NOT a professional match record: we never auto-confirm a match by title.

export const MOMENT_STORAGE_KEY = 'ptti-moment-cards-v1';

export function parseTimestamp(input) {
  if (typeof input === 'number' && Number.isFinite(input)) {
    return input >= 0 && input < 24 * 3600 ? Math.floor(input) : null;
  }
  if (typeof input !== 'string') return null;
  const text = input.trim();
  if (!text) return null;
  if (/^\d+$/.test(text)) {
    const seconds = Number(text);
    return seconds < 24 * 3600 ? seconds : null;
  }
  const parts = text.split(':').map((p) => p.trim());
  if (parts.length !== 2 && parts.length !== 3) return null;
  if (!parts.every((p) => /^\d+$/.test(p))) return null;
  const nums = parts.map(Number);
  let seconds;
  if (parts.length === 2) {
    const [m, s] = nums;
    if (s > 59) return null;
    seconds = m * 60 + s;
  } else {
    const [h, m, s] = nums;
    if (m > 59 || s > 59) return null;
    seconds = h * 3600 + m * 60 + s;
  }
  return seconds < 24 * 3600 ? seconds : null;
}

export function formatTimestamp(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '';
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rest = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
  return `${m}:${String(rest).padStart(2, '0')}`;
}

export function parseTags(input) {
  if (Array.isArray(input)) {
    return [...new Set(input.map((t) => String(t).trim().replace(/^#+/, '')).filter(Boolean))].slice(0, 10);
  }
  if (typeof input !== 'string') return [];
  return [...new Set(input.split(/[,，、\s]+/).map((t) => t.trim().replace(/^#+/, '')).filter(Boolean))].slice(0, 10);
}

export function validateMoment(input) {
  const errors = [];
  const videoKey = typeof input?.videoKey === 'string' ? input.videoKey.trim() : '';
  if (!videoKey) errors.push('请先选择一场比赛');
  const title = typeof input?.title === 'string' ? input.title.trim() : '';
  if (!title) errors.push('请填写时刻名称');
  if (title.length > 60) errors.push('时刻名称不能超过 60 字');
  const seconds = parseTimestamp(input?.timestamp);
  if (seconds === null) errors.push('时间戳格式不对，例如 12:34 或 1:02:03');
  const note = typeof input?.note === 'string' ? input.note.trim() : '';
  if (note.length > 500) errors.push('备注不能超过 500 字');
  const tags = parseTags(input?.tags ?? '');
  if (tags.some(tag => tag.length > 60)) errors.push('单个标签不能超过 60 字');
  if (errors.length) return { errors, cleaned: null };
  return { errors: [], cleaned: { videoKey, title, seconds, note, tags } };
}

export function createMoment(list, input, now = Date.now()) {
  const { errors, cleaned } = validateMoment(input);
  if (errors.length) return { errors, moments: list };
  const moment = {
    id: `moment-${now}-${Math.random().toString(36).slice(2, 8)}`,
    ...cleaned,
    createdAt: new Date(now).toISOString(),
    updatedAt: new Date(now).toISOString(),
  };
  return { errors: [], moments: sortMoments([...list, moment]), moment };
}

export function updateMoment(list, id, input, now = Date.now()) {
  const { errors, cleaned } = validateMoment(input);
  if (errors.length) return { errors, moments: list };
  const found = list.some((m) => m.id === id);
  if (!found) return { errors: ['找不到这张时刻卡片'], moments: list };
  const moments = list.map((m) => (m.id === id ? { ...m, ...cleaned, updatedAt: new Date(now).toISOString() } : m));
  return { errors: [], moments: sortMoments(moments) };
}

export function deleteMoment(list, id) {
  return list.filter((m) => m.id !== id);
}

export function sortMoments(list) {
  return [...list].sort((a, b) => (a.seconds - b.seconds) || (a.createdAt < b.createdAt ? -1 : 1));
}

export function filterMomentsByTag(list, tag) {
  if (!tag) return list;
  return list.filter((m) => (m.tags || []).includes(tag));
}

// Precise jump is enabled ONLY for YouTube, whose watch URL supports &t=<seconds>.
// Every other provider returns precise:false and only the plain official page URL.
// A local video has no official watch URL at all.
export function buildOfficialJump(video, seconds) {
  const blocked = reason => ({precise:false,url:null,reason});
  if (!video?.watchUrl || video.kind === 'LOCAL') return blocked('没有官方观看链接');
  if (!Number.isInteger(seconds) || seconds < 0 || seconds >= 86400) return blocked('时间戳无效');
  const source = video.source;
  const id = source?.video_id;
  const provider = source?.provider;
  if (source?.source_url && source.source_url !== video.watchUrl) return blocked('观看地址与已登记来源不一致');
  if (source?.video_source?.source_id && source.video_source.source_id !== id) return blocked('来源视频 ID 不一致');
  const family = value => ['YOUTUBE','YOUTUBE_OFFICIAL'].includes(value) ? 'YOUTUBE' : value;
  if (source?.video_source?.provider && family(source.video_source.provider) !== family(provider)) return blocked('来源平台不一致');
  try {
    const url = new URL(video.watchUrl);
    if (url.protocol !== 'https:' || url.username || url.password || url.hash || url.port) return blocked('官方 HTTPS 地址未通过核对');
    if (family(provider) === 'YOUTUBE') {
      if (typeof id !== 'string' || !/^[A-Za-z0-9_-]{11}$/.test(id) ||
          !['www.youtube.com','youtube.com','m.youtube.com'].includes(url.hostname) ||
          url.pathname !== '/watch' || url.searchParams.getAll('v').length !== 1 || url.searchParams.get('v') !== id) {
        return blocked('视频 ID 与官方 YouTube 页面不匹配，已阻止打开');
      }
      url.searchParams.set('t', String(seconds));
      return {precise:true,url:url.toString(),reason:''};
    }
    if (provider === 'BILIBILI' && typeof id === 'string' && /^BV[A-Za-z0-9]{10}$/.test(id) &&
        ['www.bilibili.com','bilibili.com'].includes(url.hostname) && !url.search &&
        [`/video/${id}`,`/video/${id}/`].includes(url.pathname)) {
      return {precise:false,url:video.watchUrl,reason:'仅打开已登记官方页面；请在平台内手动定位时间。'};
    }
  } catch {}
  return blocked('来源未通过官方链接核对');
}

function validStoredMoment(m) {
  return m && typeof m.id === 'string' && m.id.length > 0 && m.id.length <= 128 &&
    typeof m.videoKey === 'string' && m.videoKey.length > 0 && m.videoKey.length <= 256 &&
    typeof m.title === 'string' && m.title.trim().length > 0 && m.title.length <= 60 &&
    Number.isInteger(m.seconds) && m.seconds >= 0 && m.seconds < 86400 &&
    typeof m.note === 'string' && m.note.length <= 500 && Array.isArray(m.tags) && m.tags.length <= 10 &&
    m.tags.every(t => typeof t === 'string' && t.length <= 60) &&
    typeof m.createdAt === 'string' && Number.isFinite(Date.parse(m.createdAt)) &&
    typeof m.updatedAt === 'string' && Number.isFinite(Date.parse(m.updatedAt));
}

export function loadMomentState(storage, key = MOMENT_STORAGE_KEY) {
  const failed = error => ({moments:[],writable:false,error});
  try {
    if (typeof storage?.getItem !== 'function' || typeof storage?.setItem !== 'function') return failed('此浏览器存储不可用，暂不能保存时刻。');
    const raw = storage.getItem(key);
    if (raw === null) return {moments:[],writable:true,error:''};
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || !parsed.every(validStoredMoment) || new Set(parsed.map(m=>m.id)).size !== parsed.length) {
      return failed('已有时刻数据格式异常；已保留原始记录，暂不覆盖。');
    }
    return {moments:sortMoments(parsed),writable:true,error:''};
  } catch { return failed('无法读取本机时刻数据；已保留原始记录，暂不覆盖。'); }
}

export function loadMoments(storage, key = MOMENT_STORAGE_KEY) {
  return loadMomentState(storage,key).moments;
}

export function writeMoments(storage, moments, key = MOMENT_STORAGE_KEY) {
  try {
    if (typeof storage?.setItem !== 'function') return {ok:false,error:'此浏览器存储不可用，时刻未保存。'};
    if (!Array.isArray(moments) || !moments.every(validStoredMoment) || new Set(moments.map(moment=>moment.id)).size !== moments.length) return {ok:false,error:'时刻数据校验失败，未保存。'};
    storage.setItem(key,JSON.stringify(moments));
    return {ok:true,error:''};
  } catch (error) {
    return {ok:false,error:error?.name === 'QuotaExceededError' ? '本机存储空间不足，时刻未保存；请保留当前输入。' : '本机存储写入失败，时刻未保存；请保留当前输入。'};
  }
}

export function saveMoments(storage, moments, key = MOMENT_STORAGE_KEY) {
  return writeMoments(storage,moments,key).ok;
}

export function exportMoments(moments,now=Date.now()) {
  if(!Array.isArray(moments)||!moments.every(validStoredMoment))throw Error('Invalid moment records');
  return {schema:'ptti.moment-cards-backup/0.1',exportedAt:new Date(now).toISOString(),momentCount:moments.length,
    moments:sortMoments(moments).map(({id,videoKey,title,seconds,note,tags,createdAt,updatedAt})=>({id,videoKey,title,seconds,note,tags:[...tags],createdAt,updatedAt}))};
}
