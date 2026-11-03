import { readFileSync, realpathSync, lstatSync } from 'node:fs';
import { resolve, relative, dirname } from 'node:path';
import { createHash } from 'node:crypto';
export const TEXT_MANIFEST_SHA256 = '15337a5b64af8703cf6de69b583afb662b872f1671034af170c857d0873b2363';
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
export function verifyReviewedText(webRoot, logicalPath, legacyExpected) {
  const root = realpathSync(webRoot);
  const registryPath = resolve(root, '../../provenance/public-text-identities.json');
  if (lstatSync(registryPath).isSymbolicLink()) throw Error('text-registry-symlink');
  const registryBytes = readFileSync(registryPath);
  if (hash(registryBytes) !== TEXT_MANIFEST_SHA256) throw Error('text-registry-identity-mismatch');
  const pin = JSON.parse(registryBytes.toString('utf8')).files[logicalPath];
  if (!pin || pin.legacy_expected_sha256 !== legacyExpected) throw Error('unregistered-text-pin');
  const path = resolve(root, logicalPath);
  if (relative(root, path).startsWith('..')) throw Error('text-path-escape');
  for (let item = path; item !== root; item = dirname(item)) if (lstatSync(item).isSymbolicLink()) throw Error('text-symlink');
  const bytes = readFileSync(path);
  // Accept only the two explicitly enrolled byte identities, never arbitrary normalization.
  if (![pin.git_blob_sha256, pin.checkout_raw_sha256].includes(hash(bytes))) throw Error('reviewed-text-byte-mismatch');
  const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  if (hash(Buffer.from(text.replace(/\r\n/g, '\n'), 'utf8')) !== pin.canonical_lf_sha256) throw Error('reviewed-text-content-mismatch');
  return true;
}
