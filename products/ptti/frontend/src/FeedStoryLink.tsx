import type {FeedVideo} from './feedCatalog';
import {feedMatchId} from './matchFavorites.mjs';

type MatchRef = {match_id: string};

export default function FeedStoryLink({video, matches, onOpen}: {
  video: FeedVideo;
  matches: MatchRef[];
  onOpen: (matchId: string) => void;
}) {
  const matchId = feedMatchId(video);
  if (!matchId || !matches.some(match => match.match_id === matchId)) return null;

  return <button className="feed-story-link" data-match-id={matchId} type="button" onClick={() => onOpen(matchId)}>
    比赛故事与来源
  </button>;
}
