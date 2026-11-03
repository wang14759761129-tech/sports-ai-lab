/** Local page navigation only: never accepts an external redirect URL. */
export function readMatchId(href) {
  return new URL(href).searchParams.get('match') || '';
}
export function matchPageUrl(href, id) {
  const url = new URL(href);
  url.search = '';
  url.hash = '';
  if (id) url.searchParams.set('match', id);
  return url.href;
}
export function resolveSelectedMatch(matches, id) {
  return matches.find((match) => match.id === id) ?? null;
}
