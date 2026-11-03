export type OfficialOpenResult = 'BROWSER_DEFAULT' | 'OPENED' | 'FAILED';

export function officialPlaybackMessages(source: any, playerStatus: string) {
  const limitation = typeof source?.playback_limitation === 'string'
    ? source.playback_limitation.trim()
    : '';
  return {
    status: playerStatus,
    limitation: limitation || null,
  };
}

export async function openOfficialLink(
  event: { preventDefault: () => void },
  url: string,
  bridge?: (url: string) => Promise<boolean> | boolean,
): Promise<OfficialOpenResult> {
  if (typeof bridge !== 'function') return 'BROWSER_DEFAULT';
  event.preventDefault();
  try {
    return await bridge(url) ? 'OPENED' : 'FAILED';
  } catch {
    return 'FAILED';
  }
}

export async function copyOfficialUrl(
  url: string,
  clipboardWrite: (value: string) => Promise<void> = async value => {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable');
    await navigator.clipboard.writeText(value);
  },
  fallbackCopy: (value: string) => boolean = value => {
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
): Promise<boolean> {
  try {
    await clipboardWrite(url);
    return true;
  } catch {
    try { return fallbackCopy(url); } catch { return false; }
  }
}
