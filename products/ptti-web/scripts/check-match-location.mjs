import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { matchPageUrl, readMatchId, resolveSelectedMatch } from '../src/match-location.mjs';
const matches = JSON.parse(await readFile(new URL('./fixtures/cinema-legacy.json', import.meta.url)));
for (const match of matches) {
  const url = matchPageUrl('http://127.0.0.1:4174/?private=discard#old', match.id);
  assert.equal(readMatchId(url), match.id);
  assert.equal(resolveSelectedMatch(matches, readMatchId(url)), match);
  assert.equal(new URL(url).origin, 'http://127.0.0.1:4174');
  assert.equal(new URL(url).searchParams.size, 1);
  assert.equal(new URL(url).hash, '');
}
assert.equal(resolveSelectedMatch(matches, 'unknown'), null);
assert.equal(resolveSelectedMatch(matches, 'https://evil.example'), null);
assert.equal(readMatchId(matchPageUrl('http://127.0.0.1:4174/?match=old', '')), '');
assert.equal(readMatchId(matchPageUrl('http://127.0.0.1:4174/', 'a&b#c')), 'a&b#c');
console.log('Match location PASS: four records round-trip, unknown IDs rejected, same-origin links, no unrelated parameters.');
