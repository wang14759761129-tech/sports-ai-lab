# Sprint 09 — Match Contract v1 for San

This is an adapter over the existing Sprint 08 strict-public projection, not a new match database. Source bundle: `generated/sprint08-cinema-projection-v0.1.json`; exact LF-byte SHA-256 `5a94b6c9f2196b31ba9c151188b31900d4fbd50c2c5ecda6e95efcdde639c329`. Version: `ptti.match/1.0`.

San can vendor `runtime/match-contract-v1.mjs` and its `.d.mts`, together with that exact JSON, within its own authorized integration. Preferred async call:

```js
import {parsePinnedMatchContract} from './match-contract-v1.mjs';
const response = await fetch('/data/sprint08-cinema-projection-v0.1.json');
if (!response.ok) throw new Error('Match data unavailable');
const bytes = new Uint8Array(await response.arrayBuffer());
const match = await parsePinnedMatchContract(bytes, 'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun');
```

This verifies the exact reviewed bytes with WebCrypto before parsing, rejects unknown match IDs, and returns the match's recorded event, players, source identities, evidence and separately scoped rights and availability. WebCrypto requires a secure browser context (localhost qualifies); no network request is made by this module. `createMatchContract` is a lower-level function for already authenticated in-memory data; it is not a substitute for byte verification. Validate results using `contracts/match-contract-v1.schema.json`. Existing `consumeFanCatalog` expects its original schema; this record is a separate read-only adapter result and must not be passed to it as an existing catalog.

All eight returned matches and their source metadata are sourced from existing admitted snapshots; there are no synthetic match records in the public bundle. Tests use labeled synthetic malformed inputs solely as rejection cases. The ten event-level/unlinked sources remain in the original projection and are not presented as single-match videos. Publisher identity and match identity statuses retain their respective recorded scope. Page, playback and current-session eligibility are NOT_TESTED / NOT_EVALUATED_CURRENT_SESSION. Official-page navigation is scoped to the recorded link; embedded playback, video download and redistribution are not granted by this contract.

Media SHA-256 is null/UNKNOWN for every returned source because no video bytes or trustworthy file digest are present. The public JSON SHA identifies data, not media. No DEMO, USER_OWNED or LICENSED media is asserted. Future media types require their own reviewed scope and a new contract revision; this version refuses to infer them.

Run `node --test products/ptti-integration/tests/match-contract-v1.test.mjs` and `python -m unittest discover -s products/ptti-integration/tests -p test_match_contract_v1.py -v`. These checks are code/schema evidence only; they do not establish San integration, browser playback, rights beyond the recorded scope, or GUI acceptance.
