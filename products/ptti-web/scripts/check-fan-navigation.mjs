import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createFanStarDestination, createFanWatchReturn, getKnownMatchAthleteIds, restoreFanWatchReturn } from '../src/fan-navigation.mjs';

assert.deepEqual(createFanStarDestination('athlete:verified-1'), { page: 'stars', matchId: null, starId: 'athlete:verified-1' });
assert.throws(() => createFanStarDestination('  '), /athlete-id-required/);
assert.deepEqual(createFanWatchReturn('cinema', { matchId: 'match:verified-1', starId: null }), { page: 'cinema', matchId: 'match:verified-1', starId: null });
assert.deepEqual(createFanWatchReturn('rivalries', { matchId: 'match:verified-1' }), { page: 'rivalries', matchId: 'match:verified-1', starId: null });
assert.deepEqual(createFanWatchReturn('corner', { starId: 'athlete:verified-1' }), { page: 'corner', matchId: null, starId: 'athlete:verified-1' });
assert.deepEqual(createFanWatchReturn('highlights', { matchId: null }), { page: 'highlights', matchId: null, starId: null });
assert.deepEqual(restoreFanWatchReturn({ page: 'stars', matchId: 'match:verified-1', starId: 'athlete:verified-1' }), { page: 'stars', matchId: 'match:verified-1', starId: 'athlete:verified-1' });
assert.deepEqual(restoreFanWatchReturn({ page: 'internal-review', matchId: '../private', starId: null }), { page: 'cinema', matchId: '../private', starId: null });
assert.deepEqual(restoreFanWatchReturn(null), { page: 'cinema', matchId: null, starId: null });
assert.deepEqual(getKnownMatchAthleteIds({ participants: [{ athlete_id: 'athlete:known' }, { athlete_id: 'athlete:unknown' }, { athlete_id: 'athlete:known' }, { side: 'B' }] }, ['athlete:known']), ['athlete:known'], 'saved-match links include only known, unique participant identities');
assert.deepEqual(getKnownMatchAthleteIds(null, ['athlete:known']), []);

const [catalogComponent, searchOverlay, browserQa, stylesheet, htmlShell, favicon, appSource, universeSource, i18nSource, publicCatalogText, artworkComponent, catalogProvider, theaterFrameSource] = await Promise.all([
  readFile(new URL('../src/FanCatalogPage.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/FanSearchOverlay.tsx', import.meta.url), 'utf8'),
  readFile(new URL('./check-goal14-first-fan-journey-browser.mjs', import.meta.url), 'utf8'),
  readFile(new URL('../src/style.css', import.meta.url), 'utf8'),
  readFile(new URL('../index.html', import.meta.url), 'utf8'),
  readFile(new URL('../public/favicon.svg', import.meta.url), 'utf8'),
  readFile(new URL('../src/App.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/FanUniversePages.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/i18n.ts', import.meta.url), 'utf8'),
  readFile(new URL('../public/data/match-library-strict-public.json', import.meta.url), 'utf8'),
  readFile(new URL('../src/FanArtwork.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/PublicFanCatalog.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/PrivateTheaterFrame.tsx', import.meta.url), 'utf8'),
]);
const publicCatalog = JSON.parse(publicCatalogText);
const admittedMatch = publicCatalog.matches.find((match) => match.match_id === 'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun');
const linkedStarId = admittedMatch?.participants.find((participant) => participant.athlete_id === 'athlete:121558')?.athlete_id;
assert.ok(admittedMatch && linkedStarId, 'return-context regression uses the actual admitted Main match and athlete IDs');
assert.deepEqual(getKnownMatchAthleteIds(admittedMatch, publicCatalog.stars.map((star) => star.athlete_id)), admittedMatch.participants.map((participant) => participant.athlete_id).filter(Boolean), 'real Main match participant IDs remain linked through My Corner');
const watchSnapshot = createFanWatchReturn('stars', { matchId: admittedMatch.match_id, starId: linkedStarId });
assert.deepEqual(restoreFanWatchReturn(watchSnapshot), { page: 'stars', matchId: admittedMatch.match_id, starId: linkedStarId }, 'Watch return retains the selected Stars profile and match detail');
assert.match(theaterFrameSource, /data-fan-watch-detail/);
assert.match(catalogComponent, /data-linked-match-id=\{sourceMatch\.match_id\}/);
assert.match(searchOverlay, /results\.matches\.map\(\(match\) =>[\s\S]*onOpenMatch\(match\.match_id\)/, 'Cinema search result opens its exact public match detail');
assert.match(appSource, /onOpenMatch=\{\(id\) => \{ setFanSearchOpen\(false\); openFanMatch\(id\); \}\}/, 'search closes cleanly before selecting the exact match');
assert.match(catalogComponent, /mode === 'highlights'[\s\S]*visibleHighlights\.map\(sourceCard\)/, 'the dedicated highlights route renders only the strict highlight projection');
assert.match(catalogComponent, /onGoHighlights && <button[\s\S]*onClick=\{onGoHighlights\}/, 'Cinema provides a real action into the full event-highlights list');
assert.match(catalogComponent, /\(mode === 'cinema' \|\| mode === 'stars'\) && selectedMatchView\(\)/, 'a match selected from a Stars profile renders its match detail instead of a blank view');
assert.match(catalogComponent, /t\(selectedStar \? 'fan\.backToStars' : 'fan\.backToCinema'\)/, 'match detail returns to the originating player profile when applicable');
assert.match(catalogComponent, /onOpenWatch\(source\.source_id, \{ matchId: source\.match_link_status === 'HUMAN_VERIFIED' \? source\.canonical_match_id : null, starId: selectedStar\?\.athlete_id \?\? null \}\)/, 'Watch receives only the source exact-ID match association, never surrounding UI context');
assert.match(catalogComponent, /onOpenMatch\(admittedFullMatch\.match_id\)/, 'Clips empty-state action opens the exact admitted match');
assert.match(catalogComponent, /data-fan-open-match-id=\{admittedFullMatch\.match_id\}/);
assert.match(catalogComponent, /data-cinema-cover-wall/);
assert.match(catalogComponent, /data-fan-search/);
const cinemaSource = catalogComponent.slice(catalogComponent.indexOf("{mode === 'cinema' && !selectedMatch && !selectedStar && <>"), catalogComponent.indexOf("{mode !== 'cinema' && mode !== 'watch'"));
assert.equal((cinemaSource.match(/<input data-fan-search/g) || []).length, 1, 'typing must not switch between separate home and result inputs');
assert.match(cinemaSource, /<div className="fan-cinema-discovery"><label/, 'the input has a stable, unconditional parent while query changes');
assert.match(catalogProvider, /fetchPinnedJson\('\/data\/match-library-strict-public\.json', hashes\.base\)/, 'Fan UI reads pinned strict-public catalog through its shared provider');
assert.match(catalogProvider, /fetchPinnedJson\('\/data\/goal17-official-match-video-additions\.json', hashes\.delta\)/, 'Fan UI reads pinned strict-public delta through its shared provider');
assert.match(catalogComponent, /featuredRouteEligible/);
assert.match(catalogComponent, /featuredSource\.source_id/);
assert.match(catalogComponent, /OriginalFanArtwork/);
assert.match(artworkComponent, /fan\.artworkCredit/);
assert.doesNotMatch(catalogComponent, /<iframe\b|<video\b/i, 'Fan cards never embed or pretend to host match footage');
assert.match(catalogComponent, /target="_blank" rel="noopener noreferrer"/, 'external platform links open safely after a user click');
assert.match(catalogComponent, /onClick=\{\(\) => setOfficialOpenAttempted\(true\)\}/, 'official-link feedback is tied to the deliberate click');
assert.match(catalogComponent, /officialOpenAttempted && <p[^>]+role="status"/, 'Watch provides an accessible fallback hint without claiming playback');
assert.match(catalogComponent, /setOfficialOpenAttempted\(false\); setWatchUrlCopyState\('idle'\)/, 'new source clears prior link feedback');
assert.match(catalogComponent, /fan-detail-save[^>]+aria-pressed=\{savedMatchIds\.includes\(selectedMatch\.match_id\)\}/, 'match detail can save the exact viewed match');
assert.match(catalogComponent, /fan-watch-save[^>]+aria-pressed=\{savedMatchIds\.includes\(sourceMatch\.match_id\)\}/, 'Watch can save only an exactly linked match');
assert.match(i18nSource, /'fan\.officialOpenAttempted': '已尝试在新标签打开官方页面。/, 'Chinese guidance distinguishes opening from playback');
assert.match(i18nSource, /'fan\.officialOpenAttempted': 'We tried to open the official page/, 'English guidance distinguishes opening from playback');
assert.match(catalogComponent, /const clipFiltersActive = Boolean\(query\.trim\(\)\) \|\| clipAthleteId !== 'all' \|\| clipType !== 'all'/);
assert.match(catalogComponent, /function clearClipFilters\(\)[\s\S]*setQuery\(''\)[\s\S]*setClipAthleteId\('all'\)[\s\S]*setClipType\('all'\)/);
assert.match(appSource, /function openFanWatch\(sourceId: string, context\?[\s\S]*setWatchReturn\(createFanWatchReturn\(page === 'watch' \? watchReturn.page : page, context\)\)/);
assert.match(appSource, /function returnFromWatch\(\)[\s\S]*setFanMatchId\(destination\.matchId\)[\s\S]*setFanStarId\(destination\.starId\)[\s\S]*changePage\(destination\.page\)/);
assert.match(appSource, /function openFanMatch\(matchId: string\)[\s\S]*setFanMatchId\(matchId\)[\s\S]*changePage\('cinema'\)/);
assert.match(catalogComponent, /data-fan-match-detail[\s\S]*fan-detail-save[^>]+aria-pressed=\{savedMatchIds\.includes\(selectedMatch\.match_id\)\}/, 'match details expose persistent save state after returning from Watch');
assert.match(appSource, /<MyCornerPage[\s\S]*onGoClips=\{\(\) => changePage\('clips'\)\}[\s\S]*onGoGear=\{\(\) => changePage\('gear'\)\}[\s\S]*onOpenStar=\{openFanStar\}/, 'My Corner has direct routes to exact participant profiles, Clips, and Gear');
assert.match(universeSource, /getKnownMatchAthleteIds\(match, catalog\?\.stars\.map\(\(star\) => star\.athlete_id\) \?\? \[\]\)/, 'saved match athlete links are restricted to catalog identities');
assert.match(universeSource, /data-related-athlete-id=\{athleteId\}[\s\S]*onOpenStar\(athleteId\)/, 'My Corner exposes only exact-ID related profile actions');
assert.match(universeSource, /onGoClips && <button[\s\S]*onClick=\{onGoClips\}[\s\S]*onGoGear && <button[\s\S]*onClick=\{onGoGear\}/, 'My Corner exposes Clips and Gear shortcuts');
assert.match(appSource, /function openFanRivalry\(rivalryId: string\)[\s\S]*setFanRivalryId\(rivalryId\)[\s\S]*changePage\('rivalries'\)/);
assert.match(appSource, /page === 'corner' && <Suspense[\s\S]*><MyCornerPage/, 'My Corner is lazy-loaded when selected');
assert.match(appSource, /mode="rivalries"/);
assert.match(catalogComponent, /onOpenRivalry/);
assert.match(catalogComponent, /onGoCorner/);
assert.match(i18nSource, /'fan\.emptyClipsDetail': '当前短片数量为 0。赛事级高光会在首页单独列出，完整比赛保留在赛事卡片中，不会混成短片。'/);
assert.match(i18nSource, /'fan\.emptyClipsDetail': 'There are currently 0 short clips\. Event-level highlights have their own shelf on Cinema, and full matches stay on match cards\.'/);
assert.match(i18nSource, /'fan\.openAvailableMatch': '查看已准入比赛'/);
assert.match(i18nSource, /'fan\.openAvailableMatch': 'View admitted match'/);
assert.match(i18nSource, /'fan\.clearClipFilters': '清除搜索和筛选'/);
assert.match(i18nSource, /'fan\.clearClipFilters': 'Clear search and filters'/);
assert.match(browserQa, /\[data-fan-watch-detail\] \[data-linked-match-id=/);
assert.doesNotMatch(browserQa, /\[data-fan-watch-detail\]\[data-linked-match-id=/);
assert.match(browserQa, /official_link_open/);
assert.match(browserQa, /official_page_domcontentloaded/);
assert.match(browserQa, /official_page_load_result = 'TIMEOUT'/);
assert.match(browserQa, /finally \{\s*if \(external && !external\.isClosed\(\)\)/);
assert.match(browserQa, /test_popup_cleanup = 'PASS'/);
assert.match(browserQa, /after third-party popup cleanup, PTTI Watch context remains intact/);
assert.match(browserQa, /app_status: appStatus/);
assert.match(browserQa, /third_party_page_load_status/);
assert.match(browserQa, /popup\.on\('pageerror'/);
assert.match(browserQa, /English Clips empty-state demo action/);
assert.match(browserQa, /async function assertNoHorizontalOverflow/);
assert.match(browserQa, /async function assertActionable/);
assert.match(browserQa, /cinema-zh-390x844\.png/);
assert.match(browserQa, /stars-zh-390x844\.png/);
assert.match(browserQa, /watch-zh-390x844\.png/);
assert.match(browserQa, /verify the real English Clips empty state/);
assert.match(browserQa, /Clips empty state opens the exact admitted match and returns to Clips/);
assert.match(browserQa, /English Clips action opens the exact admitted match and returns to Clips/);
assert.match(browserQa, /clips-en-390x844\.png/);
assert.match(browserQa, /official_page_load_result/);
assert.doesNotMatch(browserQa, /if \(officialWatchEvidence\.official_page_domcontentloaded === 'PASS'\)/);
assert.match(browserQa, /video_playback: 'NOT_TESTED'/);
assert.match(browserQa, /http_failures/);
assert.match(stylesheet, /\.primary-nav \{[^}]*flex: 1 1 auto;[^}]*overflow-x: auto;/);
assert.match(stylesheet, /\.nav-link \{[^}]*white-space: nowrap;/);
assert.match(stylesheet, /\.site-header > \.wordmark, \.site-header > \.header-actions \{ flex: 0 0 auto; \}/);
assert.match(stylesheet, /\.primary-nav \{ flex: 0 0 100%; width: 100%; min-height: 44px; order: 3; justify-content: flex-start;/);
assert.match(stylesheet, /\.fan-content-body \.button \{ width: 100%; min-height: 46px;/);
assert.match(stylesheet, /\.fan-empty-actions \{ display: flex; flex-wrap: wrap;/);
assert.match(stylesheet, /\.fan-cinema-hero \{ position: relative; display: grid; grid-template-columns: minmax\(0, \.85fr\) minmax\(0, 1\.15fr\)/, 'Cinema has a responsive visual-first hero');
assert.match(stylesheet, /\.fan-star-grid \.fan-star-tile \.fan-artwork \{ aspect-ratio: 3 \/ 4;/, 'Stars use consistent portrait artwork cards');
assert.match(stylesheet, /\.fan-clips-empty \{ display: grid;/, 'Clips has a designed empty state');
assert.match(stylesheet, /\.fan-art-poster-copy \{ position: absolute;/, 'athlete and event cards use original typographic artwork rather than unlicensed photos');
assert.match(stylesheet, /@media \(max-width: 680px\)[\s\S]*\.fan-cinema-hero \{ grid-template-columns: minmax\(0, 1fr\)/, 'Cinema stacks on phone screens');
assert.match(stylesheet, /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.fan-tool-card, \.fan-star-tile \.fan-artwork, \.nav-link \{ transition: none;/, 'fan motion respects reduced-motion preferences');
assert.match(appSource, /data-page=\{page\}/);
assert.match(appSource, /<nav className="primary-nav"[\s\S]*nav\.cinema[\s\S]*nav\.stars[\s\S]*nav\.clips/);
assert.match(appSource, /className="pro-nav"/);
assert.match(appSource, /page === 'highlights' && <FanCatalogPage[\s\S]*mode="highlights"/, 'Highlights is reachable as a dedicated page');
assert.match(htmlShell, /<link rel="icon" type="image\/svg\+xml" href="\/favicon\.svg" \/>/);
assert.match(favicon, /<svg[\s\S]*<\/svg>/);
console.log('PASS: Watch return preserves exact Main Stars + match context in the navigation flow.');
console.log('PASS: My Corner exposes Clips/Gear and only catalog-known participant links for saved matches.');
console.log('PASS: Clips empty state links only to the exact-ID admitted full match; FULL_MATCH remains excluded from clips.');
console.log('PASS: Search/filter no-results can be cleared; Chinese/English empty-state copy and responsive action layout are wired.');
console.log('PASS: GOAL14 browser QA selectors and layout invariants verified.');
assert.doesNotMatch(catalogComponent, /className="fan-cinema-hero grand-lobby"/);assert.match(catalogComponent, /data-cinema-cover-wall/);assert.match(catalogComponent, /onOpenWatch\(playableRoute.source.source_id/);
