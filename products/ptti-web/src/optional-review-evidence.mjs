/** Optional private evidence seam. Absence supplies no evidence and promotes no rights. */
export async function loadOptionalReviewEvidence(provider) {
  if (provider === undefined) return null;
  if (typeof provider !== 'function') throw new Error('invalid-optional-review-provider');
  const value = await provider();
  if (!value || typeof value.evidenceRaw !== 'string' || typeof value.reportsRaw !== 'string'
    || value.evidenceRaw.length > 1_000_000 || value.reportsRaw.length > 1_000_000) {
    throw new Error('invalid-optional-review-payload');
  }
  // The existing SHA and evidence validators remain mandatory at the consumer.
  return { evidenceRaw: value.evidenceRaw, reportsRaw: value.reportsRaw };
}
