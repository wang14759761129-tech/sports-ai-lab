import type { FeedbackEntry } from './types';

interface FeedbackStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export const FEEDBACK_KEY: 'ptti-web-feedback-v0.1';
export function readFeedback(storage: FeedbackStorage): FeedbackEntry[];
export function appendFeedback(storage: FeedbackStorage, entry: FeedbackEntry): FeedbackEntry[];
