/** UI-only clipboard requests. A source change or unmount invalidates late results. */
export function createWatchCopyGuard() {
  let revision = 0;
  return {
    invalidate() { revision++; },
    async copy(url, writeText) {
      const request = ++revision;
      let result = 'manual';
      try {
        if (typeof writeText !== 'function') throw new Error('clipboard-unavailable');
        await writeText(url);
        result = 'copied';
      } catch { /* The existing manual-copy field remains the fallback. */ }
      return request === revision ? result : null;
    },
  };
}
