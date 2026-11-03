import type {MouseEvent} from 'react';
import {findOfficialFeedVideo, officialAction, officialWatchState} from './feedCatalog.js';

type Match = {
  match_id: string;
  event_name?: string | null;
  event_date?: string | null;
  round?: string | null;
  players?: {player_a?: any; player_b?: any};
  online_sources?: any[];
};

export default function LegacyMatchStory({match, data, saved, saving=false, error, onBack, onToggleSaved, onPlay, onOpenEmbedded, onOpenOfficial}: {
  match: Match; data: any; saved: boolean; saving?: boolean; error?: string; onBack: () => void; onToggleSaved: () => void;
  onPlay: (videoId: string) => void; onOpenEmbedded: (source: any) => void;
  onOpenOfficial: (event: MouseEvent<HTMLAnchorElement>, url: string) => void;
}) {
  const linkedSources = (match.online_sources || []).filter(source =>
    source.match_id === match.match_id && typeof source.source_url === 'string' && source.source_url.startsWith('https://'));
  const localVideos = (data.videos || []).filter((video: any) => video.match_id === match.match_id);
  const playerName = (player: any) => player?.canonical_name_zh || player?.canonical_name_en || '选手资料未核实';

  return <article className="legacy-match-story" data-match-story={match.match_id} aria-labelledby="legacy-match-story-title">
    <button className="legacy-story-back" type="button" onClick={onBack}>← 返回赛事封面墙</button>
    <header>
      <p className="legacy-story-eyebrow">MATCH STORY · 已收录赛事资料</p>
      <h1 id="legacy-match-story-title">{match.event_name || '赛事名称未核实'}</h1>
      <p>{playerName(match.players?.player_a)} <span aria-hidden="true">vs</span> {playerName(match.players?.player_b)}</p>
    </header>
    <dl className="legacy-story-facts">
      <div><dt>赛事日期</dt><dd>{match.event_date || '未记录'}</dd></div>
      <div><dt>轮次</dt><dd>{!match.round || match.round === 'UNKNOWN' ? '未记录' : match.round}</dd></div>
      <div><dt>比赛 ID</dt><dd><code>{match.match_id}</code></dd></div>
    </dl>
    <button className="legacy-story-save" type="button" aria-pressed={saved} disabled={saving} onClick={onToggleSaved}>
      {saved ? '★ 已收藏比赛 · 取消收藏' : '☆ 收藏这场比赛'}
    </button>
    {error && <p className="legacy-story-error" role="alert">{error}</p>}

    <section aria-labelledby="legacy-story-sources">
      <h2 id="legacy-story-sources">观看来源</h2>
      {linkedSources.length ? <ul className="legacy-story-source-list">{linkedSources.map((source: any) => {
        const feedVideo = findOfficialFeedVideo(data, match.match_id, source);
        const state = officialWatchState(feedVideo?.source || source);
        const action = feedVideo ? officialAction(feedVideo) : 'SOURCE_LINK';
        return <li key={source.source_key || `${source.provider}:${source.video_source?.source_id || source.video_id}`}>
          <div><strong>{source.title || source.display_title || '官方来源'}</strong><span>{source.source_publisher || source.channel || source.provider || '发布者未记录'}</span><small>{state.label} · 实际播放未在此处验收</small></div>
          {action === 'EMBED'
            ? <button type="button" onClick={() => onOpenEmbedded(feedVideo!.source)}>在 PTTI 内打开已准入来源 ↗</button>
            : feedVideo?.watchUrl ? <a href={feedVideo.watchUrl} target="_blank" rel="noopener noreferrer" onClick={event => onOpenOfficial(event, feedVideo.watchUrl!)}>前往官方来源 ↗</a> : <span role="status">来源身份或链接待核实，暂不可打开</span>}
        </li>;
      })}</ul> : <p role="status">暂时没有精确关联到这场比赛的官方观看来源。</p>}
    </section>

    <section aria-labelledby="legacy-story-local">
      <h2 id="legacy-story-local">本机录像</h2>
      {localVideos.length ? <ul className="legacy-story-source-list">{localVideos.map((video: any) => <li key={video.video_id}>
        <div><strong>{video.title || '本机录像'}</strong><small>{video.availability_status === 'AVAILABLE' ? '本机可用 · 播放和分析权限按登记状态处理' : '本机文件当前不可用'}</small></div>
        <button type="button" disabled={video.availability_status !== 'AVAILABLE'} onClick={() => onPlay(video.video_id)}>打开本机录像</button>
      </li>)}</ul> : <p>没有已精确关联的本机录像。</p>}
    </section>
    <p className="legacy-story-limit" role="note">本页只展示目录中已有的赛事事实与来源，不生成逐分叙事或比分；官方链接不代表站内播放许可，也不代表视频已经实测可播。</p>
  </article>;
}
