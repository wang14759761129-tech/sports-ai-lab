export async function openOfficialLink(event, url, bridge) {
  if (typeof bridge !== 'function') return 'BROWSER_DEFAULT';
  event.preventDefault();
  try {
    return await bridge(url) ? 'OPENED' : 'FAILED';
  } catch {
    return 'FAILED';
  }
}

export async function copyOfficialUrl(
  url,
  clipboardWrite = async value => {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable');
    await navigator.clipboard.writeText(value);
  },
  fallbackCopy = value => {
    const field = document.createElement('textarea');
    field.value = value;
    field.setAttribute('readonly', '');
    field.style.position = 'fixed';
    field.style.opacity = '0';
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand('copy');
    field.remove();
    return copied;
  },
) {
  try {
    await clipboardWrite(url);
    return true;
  } catch {
    try { return fallbackCopy(url); } catch { return false; }
  }
}
