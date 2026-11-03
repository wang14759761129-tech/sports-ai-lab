export const FEEDBACK_KEY = 'ptti-web-feedback-v0.1';

export function readFeedback(storage) {
  try {
    const value = storage.getItem(FEEDBACK_KEY);
    if (!value) return [];
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function appendFeedback(storage, entry) {
  const entries = [...readFeedback(storage), entry];
  storage.setItem(FEEDBACK_KEY, JSON.stringify(entries));
  return entries;
}
