export function createShareText({ players, event, meta, route, status, officialUrl, pageUrl, scope, localHint }) {
  return ['PTTI · ' + players.join(' vs '), event + ' · ' + meta, route + ' · ' + status, scope, officialUrl || '', pageUrl, localHint].filter(Boolean).join('\n');
}

/** PNG for chat apps; drawn directly so CSP never needs remote/blob image permission. */
export async function createSharePng(copy) {
  const canvas = document.createElement('canvas'); canvas.width = 1200; canvas.height = 675;
  const ctx = canvas.getContext('2d'); if (!ctx) throw new Error('Canvas unavailable');
  ctx.fillStyle = '#0a0a0a'; ctx.fillRect(0, 0, 1200, 675);
  ctx.fillStyle = '#151619'; ctx.beginPath(); ctx.roundRect(36, 36, 1128, 603, 24); ctx.fill();
  ctx.strokeStyle = '#292b30'; ctx.stroke(); ctx.fillStyle = '#e53943'; ctx.fillRect(60,60,8,80);
  function text(value, x, y, size, color = '#f4f4f5') {
    ctx.fillStyle = color; ctx.font = `${size}px Arial,Microsoft YaHei,sans-serif`; ctx.fillText(String(value), x, y, 1080);
  }
  text('PTTI',88,103,36); text(copy.meta,88,138,20,'#a2a4aa'); text(copy.event,60,190,25,'#a2a4aa');
  text(copy.players[0] ?? '',60,275,52); text('VS',60,321,20,'#e53943'); text(copy.players.slice(1).join(' / '),60,390,52);
  text(copy.result || '',60,433,23,'#a2a4aa'); ctx.strokeStyle = '#292b30'; ctx.beginPath(); ctx.moveTo(60,466); ctx.lineTo(1140,466); ctx.stroke();
  text(copy.route,60,508,25); text(copy.status,60,549,23,copy.verified ? '#79d8a5' : '#f0be64');
  text(copy.checked,60,586,19,'#a2a4aa'); text(copy.footer,60,619,16,'#a2a4aa');
  return await new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('PNG export failed')), 'image/png'));
}
