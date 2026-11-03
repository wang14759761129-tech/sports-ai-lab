const TACTIC_COPY = Object.freeze({
  'active-flick': Object.freeze({
    id: 'active-flick',
    title: 'arena.choice.activeFlick',
    hint: 'arena.choice.activeFlickHint',
    intent: 'arena.detail.activeFlick.intent',
    advantage: 'arena.detail.activeFlick.advantage',
    risk: 'arena.detail.activeFlick.risk',
    when: 'arena.detail.activeFlick.when',
  }),
  'short-touch': Object.freeze({
    id: 'short-touch',
    title: 'arena.choice.shortTouch',
    hint: 'arena.choice.shortTouchHint',
    intent: 'arena.detail.shortTouch.intent',
    advantage: 'arena.detail.shortTouch.advantage',
    risk: 'arena.detail.shortTouch.risk',
    when: 'arena.detail.shortTouch.when',
  }),
  'long-push': Object.freeze({
    id: 'long-push',
    title: 'arena.choice.longPush',
    hint: 'arena.choice.longPushHint',
    intent: 'arena.detail.longPush.intent',
    advantage: 'arena.detail.longPush.advantage',
    risk: 'arena.detail.longPush.risk',
    when: 'arena.detail.longPush.when',
  }),
});
const CHOICES = new Set(Object.keys(TACTIC_COPY));

export const ARENA_TACTICS = Object.freeze(Object.values(TACTIC_COPY));

export function createArenaChallengeState() {
  return { selectedChoice: null, attempt: 1, takeawayGenerated: false };
}

export function reduceArenaChallenge(state, action) {
  if (!state || !Number.isSafeInteger(state.attempt) || state.attempt < 1 || !action || typeof action !== 'object') {
    return createArenaChallengeState();
  }
  if (action.type === 'choose') {
    return CHOICES.has(action.choice) ? { ...state, selectedChoice: action.choice } : state;
  }
  if (action.type === 'generate-takeaway') {
    return state.selectedChoice ? { ...state, takeawayGenerated: true } : state;
  }
  if (action.type === 'retry') return { selectedChoice: null, attempt: state.attempt + 1, takeawayGenerated: false };
  return state;
}

export function createArenaLearningTakeaway(choice) {
  const tactic = TACTIC_COPY[choice];
  if (!tactic) return null;
  return {
    simulated: 'arena.learning.simulated',
    scenario: 'arena.scenario',
    choice: tactic.title,
    purpose: tactic.intent,
    advantage: tactic.advantage,
    risk: tactic.risk,
    conditions: tactic.when,
    question: 'arena.learning.question',
  };
}

export function formatArenaLearningTakeaway(choice, translate) {
  const takeaway = createArenaLearningTakeaway(choice);
  if (!takeaway || typeof translate !== 'function') return null;
  const line = (label, key) => `${translate(label)}: ${translate(key)}`;
  return [
    translate(takeaway.simulated),
    `${translate('arena.scenarioDetail')} · ${translate(takeaway.scenario)}`,
    line('arena.learning.label.choice', takeaway.choice),
    line('arena.learning.label.purpose', takeaway.purpose),
    line('arena.learning.label.advantage', takeaway.advantage),
    line('arena.learning.label.risk', takeaway.risk),
    line('arena.learning.label.conditions', takeaway.conditions),
    `${line('arena.learning.label.question', takeaway.question)} ${translate(takeaway.conditions)}${translate('arena.learning.questionEnd')}`,
  ].join('\n');
}

/** Protects takeaway copy feedback from stale clipboard completions after a choice, retry, or unmount. */
export function createArenaTakeawayCopyGuard() {
  let revision = 0;
  return {
    invalidate() { revision++; },
    async copy(text, writeText) {
      const request = ++revision;
      let result = 'manual';
      try {
        if (typeof writeText !== 'function') throw new Error('clipboard-unavailable');
        await writeText(text);
        result = 'copied';
      } catch { /* The rendered read-only text field remains the manual fallback. */ }
      return request === revision ? result : null;
    },
  };
}
