// Cinema viewing helpers — pure, testable, no React, no network.
// Session-only restoration: sessionStorage, not localStorage, not production DB.
// This module is independent of Moment Cards: it does not import momentCards.mjs,
// so PATCH-05 applies even if PATCH-04 has not been applied yet.

export const FEED_VIEW_KEY = 'ptti-r4-feed-view-v1';

export function saveFeedView(storage, view) {
  try {
    if (typeof storage?.setItem !== 'function') return false;
    const current = loadFeedView(storage) || { athlete: '', event: '', query: '' };
    const saved = Object.fromEntries(['athlete','event','query'].map(key => [key,
      Object.hasOwn(view || {}, key) && typeof view[key] === 'string' ? view[key] : current[key]]));
    storage?.setItem(FEED_VIEW_KEY, JSON.stringify(saved));
    return true;
  } catch {
    return false;
  }
}

export function loadFeedView(storage) {
  try {
    const raw = storage?.getItem(FEED_VIEW_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return {
      athlete: typeof parsed.athlete === 'string' ? parsed.athlete : '',
      event: typeof parsed.event === 'string' ? parsed.event : '',
      query: typeof parsed.query === 'string' ? parsed.query : '',
    };
  } catch {
    return null;
  }
}

// Merge a saved view into the current view, but never overwrite a value the
// user has already chosen in this session. Empty current values are restored.
export function mergeFeedView(saved, current) {
  if (!saved) return current;
  const merged={...current};
  for (const key of ['athlete','event','query']) {
    if (typeof current?.[key] !== 'string' && typeof saved[key]==='string') merged[key]=saved[key];
  }
  return merged;
}

// Describe an official-watch failure without opening anything new.
// watchUrl null = never verified, so there is nothing safe to open or copy.
// failedUrl set = desktop open failed, copy is the safe recovery.
export function describeWatchFailure({ watchUrl, failedWatchUrl }) {
  if (!watchUrl) {
    return {
      kind: 'UNAVAILABLE',
      message: '官方观看链接待核实，未打开任何外部页面，目录数据未变。',
      canCopy: false,
      canRetry: true,
    };
  }
  if (failedWatchUrl && failedWatchUrl === watchUrl) {
    return {
      kind: 'OPEN_FAILED',
      message: '系统浏览器未能打开官方页面，可复制链接后手动打开。',
      canCopy: true,
      canRetry: true,
    };
  }
  return { kind: 'OK', message: '', canCopy: Boolean(watchUrl), canRetry: false };
}

// Personal shelves show the complete saved/history set; discovery filters remain intact for return.
export function personalShelfFilters(page, filters) {
  if (page !== 'feedFavorites' && page !== 'feedHistory') return filters;
  return {...filters, query:'',category:'全部',athlete:'',event:'',year:'',platform:'',content:''};
}
