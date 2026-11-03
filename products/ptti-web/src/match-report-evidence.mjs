export const MATCH_REPORT_SOURCE_COMMIT = '8036a37ff6af5ae5c7924b5c26d3290e640bf607';
export const MATCH_REPORT_EVIDENCE_SHA = '701213d2bfca2e120b31629ef9422f8fd9a21eef4f341a87614b65fd130effa8';
export const MATCH_REPORT_MATCH_LIBRARY_SHA = '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930';
export const MATCH_REPORT_FAN_INSPIRATION_SHA = '702bc12850676ae9eeda39b533ade9cc5f2da0fe8710aa8ebc82f0c2b803c5c9';

const fail = (code) => { throw new Error(code); };
const requireValue = (ok, code) => { if (!ok) fail(code); };
const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const MATCH_ID = 'pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final';
const VIDEO_ID = 'video-source:youtube:cDccQqVlMnc';
const ARTICLE_ID = 'goal15-wtt-singapore-smash-2026-ms-final';
const ARTICLE_URL = 'https://www.worldtabletennis.com/description?artId=5957';

/** Consume one Main match-report projection, joining only by exact admitted IDs. */
export function consumeMatchReportEvidence(input, catalog) {
  requireValue(isObject(input) && input.contract_version === 'ptti.main.match-report-evidence/0.1', 'unsupported-match-report-contract');
  requireValue(isObject(input.input_identity)
    && input.input_identity.match_library_sha256 === MATCH_REPORT_MATCH_LIBRARY_SHA
    && input.input_identity.fan_inspiration_sha256 === MATCH_REPORT_FAN_INSPIRATION_SHA, 'match-report-input-identity-mismatch');
  requireValue(Array.isArray(input.match_reports) && input.match_reports.length === 1, 'match-report-count-mismatch');
  const report = input.match_reports[0];
  requireValue(isObject(report) && report.report_id === 'match-report:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final'
    && report.match_id === MATCH_ID, 'match-report-identity-mismatch');
  const match = catalog?.matches?.find((item) => item.match_id === MATCH_ID);
  requireValue(Boolean(match), 'match-report-match-not-in-catalog');
  requireValue(report.event_name === 'Singapore Smash 2026' && report.event_year === 2026
    && report.event_name === match.event && report.round === match.round, 'match-report-event-mismatch');
  const expectedParticipants = [
    { athlete_id: 'athlete:121558', name_en: 'WANG Chuqin' },
    { athlete_id: 'athlete:121582', name_en: 'LIN Yun-Ju' },
  ];
  requireValue(Array.isArray(report.participants) && report.participants.length === expectedParticipants.length
    && report.participants.every((person, index) => isObject(person)
      && person.athlete_id === expectedParticipants[index].athlete_id
      && person.name_en === expectedParticipants[index].name_en), 'match-report-participants-mismatch');
  requireValue(match.participants.length === expectedParticipants.length
    && match.participants.every((person, index) => person.athlete_id === expectedParticipants[index].athlete_id
      && person.name_en === expectedParticipants[index].name_en), 'match-report-catalog-participants-mismatch');
  const result = report.recorded_result;
  requireValue(isObject(result) && result.winner_id === 'athlete:121558' && result.winner_name === 'WANG Chuqin'
    && result.player_a_games === 4 && result.player_b_games === 0
    && result.status === 'OFFICIAL_WTT_RESULT_CROSSCHECKED'
    && match.recorded_result?.player_a_games === 4 && match.recorded_result?.player_b_games === 0,
  'match-report-result-mismatch');
  requireValue(JSON.stringify(report.game_scores) === JSON.stringify([[11, 3], [11, 8], [11, 8], [11, 9]]), 'match-report-game-scores-mismatch');
  requireValue(typeof report.editorial_summary_zh === 'string' && report.editorial_summary_zh.length >= 20, 'match-report-summary-missing');

  const article = report.article;
  requireValue(isObject(article) && article.source_id === ARTICLE_ID && article.publisher === 'World Table Tennis'
    && article.title === 'Lion Heart: Wang Chuqin Takes Second Singapore Smash Title'
    && article.url === ARTICLE_URL && match.reference_url === ARTICLE_URL
    && match.evidence_source_ids.includes(ARTICLE_ID), 'match-report-article-identity-mismatch');
  requireValue(article.published_at === null
    && article.published_at_status === 'NOT_RECORDED_NO_DATE_IN_REVIEWED_SOURCE'
    && article.content_observation === 'OFFICIAL_DOMAIN_SEARCH_EXCERPT_SURFACED'
    && article.direct_page_status === 'COOKIE_CONSENT_SHELL_ONLY'
    && article.checked_on === '2026-10-21', 'match-report-article-evidence-overstated');

  const linkedVideo = report.linked_video;
  const existingSource = catalog.sources.find((source) => source.source_id === VIDEO_ID);
  requireValue(isObject(linkedVideo) && linkedVideo.source_id === VIDEO_ID
    && linkedVideo.url === 'https://www.youtube.com/watch?v=cDccQqVlMnc'
    && match.video_source_ids.includes(VIDEO_ID)
    && existingSource?.url === linkedVideo.url
    && existingSource?.canonical_match_id === MATCH_ID
    && existingSource?.match_link_status === 'HUMAN_VERIFIED'
    && linkedVideo.match_link === 'HUMAN_VERIFIED', 'match-report-video-join-mismatch');
  requireValue(linkedVideo.external_system_browser_open === 'NOT_TESTED'
    && linkedVideo.video_started === 'NOT_TESTED'
    && linkedVideo.complete_watch === 'UNVERIFIED', 'match-report-playback-evidence-overstated');
  requireValue(isObject(report.rights)
    && report.rights.article_republication === 'NOT_GRANTED'
    && report.rights.image_reuse === 'NOT_GRANTED'
    && report.rights.summary_and_outbound_link === 'FACTUAL_SUMMARY_AND_LINK_ONLY'
    && report.rights.video_embed === 'UNKNOWN_NOT_GRANTED', 'match-report-rights-overstated');
  return input.match_reports;
}

/** Return only report participants that already have an exact admitted Fan profile. */
export function getLinkedReportAthletes(report, catalog) {
  return report.participants
    .map((person) => catalog.stars.find((star) => star.athlete_id === person.athlete_id))
    .filter((star) => Boolean(star));
}
