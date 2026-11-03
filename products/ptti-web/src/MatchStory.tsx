import type { FanMatch, FanSource } from './fan-catalog.mjs';
import type { Locale } from './i18n';
import { message } from './i18n';

/** An editorial doorway over admitted facts, not an invented point-by-point narrative. */
export function MatchStory({ match, title, locale, sources, eligibleSourceIds, saved, onWatch, onCorner, onPersonal }: {
  match: FanMatch; title: string; locale: Locale; sources: FanSource[]; eligibleSourceIds: string[]; saved: boolean;
  onWatch?: (sourceId: string) => void; onCorner?: () => void; onPersonal?: () => void;
}) {
  const zh = locale === 'zh-CN';
  const linked = sources.filter(source => match.video_source_ids.includes(source.source_id) && source.canonical_match_id === match.match_id && ['HUMAN_VERIFIED', 'OFFICIAL_TITLE_ASSOCIATED_VISUAL_NOT_TESTED'].includes(source.match_link_status));
  const result = match.result_status === 'OFFICIAL_EVENT_RESULT_CROSSCHECKED' ? match.recorded_result : null;
  return <details className="match-story" data-match-story={match.match_id}>
    <summary><span>MATCH STORY</span><strong>{zh ? '比赛、来源与下一步' : 'The match. Its sources. Your next step.'}</strong></summary>
    <div className="match-story-body"><p className="eyebrow">{zh ? '公开赛事资料 · 不含个人记录' : 'Public match facts · no personal records'}</p><h3>{title}</h3>
      <dl><div><dt>{zh ? '赛事' : 'Event'}</dt><dd>{(zh ? match.event_zh : null) || match.event}</dd></div><div><dt>{zh ? '轮次' : 'Round'}</dt><dd>{match.round === 'UNKNOWN' ? message(locale,'fan.unknown') : (zh ? match.round_zh : null) || match.round}</dd></div><div><dt>{zh ? '已交叉核对的结果' : 'Cross-checked result'}</dt><dd>{result ? `${result.player_a_games}–${result.player_b_games}` : message(locale,'fan.unknown')}</dd></div></dl>
      {match.reference_url && <a className="fan-text-link" href={match.reference_url} target="_blank" rel="noopener noreferrer">{zh ? '查看赛事资料原站' : 'Open event reference'} ↗</a>}
      <section><h4>{zh ? '选择来源，继续观看' : 'Choose a source to continue'}</h4>{linked.length ? <ul>{linked.map(source => <li key={source.source_id} data-story-source-id={source.source_id}><div><strong>{source.publisher} · {source.platform}</strong><span>{message(locale, `fan.clipType.${source.content_type_claim}` as Parameters<typeof message>[1])}</span><small>{message(locale,'fan.playbackNotTested')} · {source.match_link_status === 'HUMAN_VERIFIED' ? message(locale,'fan.matchLinkScope') : source.match_link_status === 'OFFICIAL_TITLE_ASSOCIATED_VISUAL_NOT_TESTED' ? message(locale,'fan.matchLinkTitleOnly') : message(locale,'fan.sourceUnlinked')}</small></div>{eligibleSourceIds.includes(source.source_id) && source.external_viewing === 'ALLOWED' && source.url && onWatch ? <button type="button" className="button button-outline" onClick={() => onWatch(source.source_id)}>{zh ? '进入 Private Theater' : 'Open Private Theater'} →</button> : <span>{zh ? '暂无合格观看入口' : 'No eligible viewing entry'}</span>}</li>)}</ul> : <p role="status">{zh ? '尚无精确关联的观看来源。' : 'No precisely linked viewing source.'}</p>}</section>
      <p className="match-story-limit" role="note">{zh ? '暂无可信逐分数据，不能为这场公开赛事生成个人 Premiere、比分河流或技战术分析。官方来源入口不代表站内播放许可或视频已实测可播。' : 'No trusted point record is available for this public match. Personal Premiere, score river and technical analysis are unavailable here. An official entry is not in-app playback permission or verified playback.'}</p>
      <div className="personal-report-actions">{onCorner && <button type="button" onClick={onCorner}>{saved ? (zh ? '在收藏馆再发现' : 'Rediscover in your collection') : (zh ? '浏览我的收藏馆' : 'Browse Collector’s Lounge')}</button>}{onPersonal && <button type="button" onClick={onPersonal}>{zh ? '记录我自己的比赛 · 独立本机会话' : 'Review my own match · separate local session'}</button>}</div>
    </div>
  </details>;
}
