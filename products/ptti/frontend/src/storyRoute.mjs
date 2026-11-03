export function activeStoryMatch(story, page, revision) {
  if (!story || typeof story.matchId !== 'string' || !story.matchId) return null;
  if (story.page !== page || story.revision !== revision) return null;
  return story.matchId;
}
