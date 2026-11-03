import { createHash } from 'node:crypto';
import { inflateRawSync } from 'node:zlib';
import { readFileSync } from 'node:fs';
import path from 'node:path';

export const PINNED_PLAYBACK_CORE_COMMIT = '304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe';
const PIN_CONTRACT = 'ptti.playback-core-source-archive/1';
const SOURCE_PATH = 'products/ptti/playback-core/src/index.ts';
const PIN_DIRECTORY = path.join('vendor', 'playback-core-304eb661');

const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const gitBlobSha1 = (bytes) => createHash('sha1').update(Buffer.concat([
  Buffer.from(`blob ${bytes.length}\0`, 'ascii'), bytes,
])).digest('hex');

function requireThat(condition, message) {
  if (!condition) throw new Error(`Playback Core pin rejected: ${message}`);
}

function extractZipMember(zipBytes, wantedName) {
  const endSignature = 0x06054b50;
  const centralSignature = 0x02014b50;
  const localSignature = 0x04034b50;
  let end = -1;
  const lowerBound = Math.max(0, zipBytes.length - 22 - 0xffff);
  for (let offset = zipBytes.length - 22; offset >= lowerBound; offset -= 1) {
    if (zipBytes.readUInt32LE(offset) === endSignature) {
      end = offset;
      break;
    }
  }
  requireThat(end >= 0, 'ZIP end-of-central-directory record is missing');
  const entryCount = zipBytes.readUInt16LE(end + 10);
  let cursor = zipBytes.readUInt32LE(end + 16);
  const matches = [];
  for (let index = 0; index < entryCount; index += 1) {
    requireThat(cursor + 46 <= zipBytes.length && zipBytes.readUInt32LE(cursor) === centralSignature,
      'ZIP central directory is malformed');
    const method = zipBytes.readUInt16LE(cursor + 10);
    const compressedSize = zipBytes.readUInt32LE(cursor + 20);
    const uncompressedSize = zipBytes.readUInt32LE(cursor + 24);
    const nameLength = zipBytes.readUInt16LE(cursor + 28);
    const extraLength = zipBytes.readUInt16LE(cursor + 30);
    const commentLength = zipBytes.readUInt16LE(cursor + 32);
    const localOffset = zipBytes.readUInt32LE(cursor + 42);
    const nameStart = cursor + 46;
    const name = zipBytes.subarray(nameStart, nameStart + nameLength).toString('utf8');
    if (name === wantedName) matches.push({ method, compressedSize, uncompressedSize, localOffset });
    cursor = nameStart + nameLength + extraLength + commentLength;
  }
  requireThat(matches.length === 1, `ZIP must contain exactly one ${wantedName}`);
  const entry = matches[0];
  requireThat(zipBytes.readUInt32LE(entry.localOffset) === localSignature, 'ZIP local file header is malformed');
  const localNameLength = zipBytes.readUInt16LE(entry.localOffset + 26);
  const localExtraLength = zipBytes.readUInt16LE(entry.localOffset + 28);
  const contentStart = entry.localOffset + 30 + localNameLength + localExtraLength;
  const compressed = zipBytes.subarray(contentStart, contentStart + entry.compressedSize);
  requireThat(compressed.length === entry.compressedSize, 'ZIP member is truncated');
  let result;
  if (entry.method === 0) result = Buffer.from(compressed);
  else if (entry.method === 8) result = inflateRawSync(compressed);
  else throw new Error(`Playback Core pin rejected: unsupported ZIP compression method ${entry.method}`);
  requireThat(result.length === entry.uncompressedSize, 'ZIP member size does not match its index');
  return result;
}

export function verifyPinnedPlaybackCoreBytes(pin, archiveBytes, sourceBytes, overrideBytes = sourceBytes) {
  requireThat(pin && pin.contract === PIN_CONTRACT, 'unsupported pin contract');
  requireThat(pin.core_commit === PINNED_PLAYBACK_CORE_COMMIT, 'unexpected Core commit');
  requireThat(pin.source_path === SOURCE_PATH, 'unexpected Core source path');
  requireThat(typeof pin.archive_file === 'string' && pin.archive_file === 'PTTI-Playback-Core-304eb661.zip', 'unexpected archive filename');
  requireThat(Number.isSafeInteger(pin.archive_bytes) && pin.archive_bytes === archiveBytes.length, 'archive byte count mismatch');
  requireThat(sha256(archiveBytes) === pin.archive_sha256, 'archive SHA-256 mismatch');
  const archivedSource = extractZipMember(archiveBytes, pin.source_path);
  requireThat(sha256(archivedSource) === pin.source_sha256, 'extracted source SHA-256 mismatch');
  requireThat(gitBlobSha1(archivedSource) === pin.git_blob_sha1, 'extracted source Git blob SHA-1 mismatch');
  requireThat(Buffer.compare(sourceBytes, archivedSource) === 0, 'vendored source does not match the verified archive');
  requireThat(Buffer.compare(overrideBytes, archivedSource) === 0, 'configured Vite source differs from the pinned source');
  return { coreCommit: pin.core_commit, sourcePath: pin.source_path, sourceHash: pin.source_sha256, sourceBytes: archivedSource };
}

export function verifyPinnedPlaybackCore(projectRoot, overridePath = null) {
  const pinDirectory = path.join(projectRoot, PIN_DIRECTORY);
  const pin = JSON.parse(readFileSync(path.join(pinDirectory, 'SOURCE_PIN.json'), 'utf8'));
  const archiveBytes = readFileSync(path.join(pinDirectory, pin.archive_file));
  const sourcePath = path.join(pinDirectory, 'src', 'index.ts');
  const sourceBytes = readFileSync(sourcePath);
  const overrideBytes = overridePath ? readFileSync(path.resolve(overridePath)) : sourceBytes;
  const verified = verifyPinnedPlaybackCoreBytes(pin, archiveBytes, sourceBytes, overrideBytes);
  return { ...verified, pin, sourcePath: overridePath ? path.resolve(overridePath) : sourcePath };
}
