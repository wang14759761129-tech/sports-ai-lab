import assert from 'node:assert/strict';
import { FEEDBACK_KEY, appendFeedback, readFeedback } from '../src/feedback-storage.mjs';

class MemoryStorage {
  values = new Map();
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, value); }
}

const storage = new MemoryStorage();
const first = { id: 'qa-1', issueCategory: 'official-link', friction: 'Example QA record' };
const second = { id: 'qa-2', issueCategory: 'mobile-display', friction: '' };
assert.deepEqual(readFeedback(storage), []);
assert.deepEqual(appendFeedback(storage, first), [first]);
assert.deepEqual(appendFeedback(storage, second), [first, second]);
assert.deepEqual(readFeedback(storage), [first, second]);
assert.equal(storage.getItem(FEEDBACK_KEY), JSON.stringify([first, second]));

storage.setItem(FEEDBACK_KEY, '{not json');
assert.deepEqual(readFeedback(storage), []);
console.log('Feedback storage checks passed: append, restore, issue categories, and malformed-data recovery.');
