import {validateReviewV2} from './manualReviewV2.mjs';

export const MAX_REVIEW_BYTES = 2 * 1024 * 1024;
export const MAX_REVIEW_MARKS = 10000;
const algorithm = 'ptti-local-video-chunks-sha256-v1';
const validDigest = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);

/** Validate an export for preview only; caller must explicitly confirm before modifying state. */
export function prepareManualReviewImport(text, expected) {
 if (typeof text !== 'string' || new TextEncoder().encode(text).length > MAX_REVIEW_BYTES) throw Error('IMPORT_TOO_LARGE');
 let data;
 try { data = JSON.parse(text); } catch { throw Error('INVALID_JSON'); }
 if (!data || typeof data !== 'object' || Array.isArray(data)) throw Error('INVALID_REVIEW');
 if (!Array.isArray(data.marks) || data.marks.length > MAX_REVIEW_MARKS) throw Error('INVALID_MARKS');
 const review = validateReviewV2(data);
 // The local export's session identifier is not a durable media identifier.
 if (review.media.identity.kind !== 'SESSION') throw Error('UNSUPPORTED_IDENTITY');
 const fingerprint = data.local_content_fingerprint;
 if (!fingerprint || fingerprint.algorithm !== algorithm || !validDigest(fingerprint.digest)) throw Error('INVALID_FINGERPRINT');
 if (!expected || !validDigest(expected.digest) || !Number.isFinite(expected.duration_seconds) || expected.duration_seconds <= 0) throw Error('MEDIA_NOT_READY');
 if (fingerprint.digest !== expected.digest || review.media.duration_seconds !== expected.duration_seconds) throw Error('MEDIA_IDENTITY_MISMATCH');
 return {schema:review.schema, marks:review.marks, media_duration_seconds:review.media.duration_seconds, fingerprint:{algorithm,digest:fingerprint.digest}};
}
