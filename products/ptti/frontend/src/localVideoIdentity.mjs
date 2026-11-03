const CHUNK_SIZE = 2 * 1024 * 1024;
const encoder = new TextEncoder();
const hex = bytes => Array.from(new Uint8Array(bytes), n => n.toString(16).padStart(2, '0')).join('');
const checkAbort = signal => { if (signal?.aborted) throw new DOMException('Video identity calculation cancelled', 'AbortError'); };

/** A domain-separated hash of SHA-256 chunk hashes. It is NOT the SHA-256 of the original file. */
export async function identifyLocalVideo(file, { signal, onProgress } = {}) {
 if (!file || !Number.isSafeInteger(file.size) || file.size <= 0 || typeof file.slice !== 'function') throw new Error('Choose a non-empty local video file');
 if (!globalThis.crypto?.subtle) throw new Error('Local video identification requires a secure context');
 const chunks = [];
 for (let offset = 0; offset < file.size; offset += CHUNK_SIZE) {
  checkAbort(signal);
  const bytes = await file.slice(offset, Math.min(offset + CHUNK_SIZE, file.size)).arrayBuffer();
  checkAbort(signal);
  chunks.push(hex(await crypto.subtle.digest('SHA-256', bytes)));
  onProgress?.(Math.min(offset + CHUNK_SIZE, file.size), file.size);
 }
 checkAbort(signal);
 const canonical = `ptti-local-video-chunks-v1\n${file.size}\n${CHUNK_SIZE}\n${chunks.join('\n')}\n`;
 const digest = hex(await crypto.subtle.digest('SHA-256', encoder.encode(canonical)));
 checkAbort(signal);
 return { algorithm: 'ptti-local-video-chunks-sha256-v1', digest, size: file.size, chunkSize: CHUNK_SIZE };
}

/** File stays in this browser. Caller owns the returned object URL and must release it. */
export async function openLocalVideo(file, options = {}) {
 const video = options.video;
 if (file?.type && (!file.type.startsWith('video/') || (video && !video.canPlayType(file.type)))) throw new Error('This browser does not support the selected video format');
 const identity = await identifyLocalVideo(file, options);
 checkAbort(options.signal);
 const url = URL.createObjectURL(file);
 let released = false;
 return { identity, url, release() { if (!released) { released = true; URL.revokeObjectURL(url); } } };
}
