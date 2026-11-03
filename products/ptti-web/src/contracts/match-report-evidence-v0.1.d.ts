export interface MainMatchReportV01 {
  report_id: 'match-report:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final';
  match_id: 'pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final';
  event_name: 'Singapore Smash 2026';
  event_year: 2026;
  round: "Men's Singles Final";
  participants: Array<{ athlete_id: string; name_en: string }>;
  recorded_result: {
    winner_id: 'athlete:121558'; winner_name: 'WANG Chuqin'; player_a_games: 4; player_b_games: 0;
    status: 'OFFICIAL_WTT_RESULT_CROSSCHECKED';
  };
  game_scores: [[11, 3], [11, 8], [11, 8], [11, 9]];
  editorial_summary_zh: string;
  article: {
    source_id: 'goal15-wtt-singapore-smash-2026-ms-final'; publisher: 'World Table Tennis';
    title: 'Lion Heart: Wang Chuqin Takes Second Singapore Smash Title';
    url: 'https://www.worldtabletennis.com/description?artId=5957'; published_at: null;
    published_at_status: 'NOT_RECORDED_NO_DATE_IN_REVIEWED_SOURCE';
    content_observation: 'OFFICIAL_DOMAIN_SEARCH_EXCERPT_SURFACED';
    direct_page_status: 'COOKIE_CONSENT_SHELL_ONLY'; checked_on: '2026-10-21';
  };
  linked_video: {
    source_id: 'video-source:youtube:cDccQqVlMnc'; url: 'https://www.youtube.com/watch?v=cDccQqVlMnc';
    match_link: 'HUMAN_VERIFIED'; external_system_browser_open: 'NOT_TESTED';
    video_started: 'NOT_TESTED'; complete_watch: 'UNVERIFIED';
  };
  rights: {
    article_republication: 'NOT_GRANTED'; image_reuse: 'NOT_GRANTED';
    summary_and_outbound_link: 'FACTUAL_SUMMARY_AND_LINK_ONLY'; video_embed: 'UNKNOWN_NOT_GRANTED';
  };
}

export interface MainMatchReportEvidenceV01 {
  contract_version: 'ptti.main.match-report-evidence/0.1';
  generated_at: string;
  input_identity: { match_library_sha256: string; fan_inspiration_sha256: string };
  match_reports: [MainMatchReportV01];
  notice: string;
}
