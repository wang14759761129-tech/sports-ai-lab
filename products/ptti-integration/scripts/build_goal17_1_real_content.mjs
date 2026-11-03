import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { access, mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.resolve(scriptDir, "../../..");
export const PACKAGE_DIR = path.join(REPO_ROOT, "products/ptti-integration/generated/goal17-1-real-content-v0.1");
export const INTERNAL_DIR = path.join(PACKAGE_DIR, "internal");
export const PUBLIC_DIR = path.join(PACKAGE_DIR, "public");
export const ASSET_DIR = path.join(PUBLIC_DIR, "assets");
export const BASE_GOAL16_PATH = path.join(REPO_ROOT, "products/ptti-integration/generated/goal16-public-media-v0.2/public-media-manifest.json");
export const BASE_GOAL16_REVIEW_PATH = path.join(REPO_ROOT, "products/ptti-integration/generated/goal16-media-clearance-v0.2/rights-review.json");
export const BASE_GOAL15_PATH = path.join(REPO_ROOT, "products/ptti-integration/generated/goal15-main-fan-universe-public-v0.2/match-library-strict-public.json");

const EXPECTED_GOAL16_SHA = "c05491a64f59ac922d2d85d081eccf3b2853f717ece82c8bcfa3d05608f2c004";
const EXPECTED_GOAL15_SHA = "1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930";
const FFMPEG = process.env.PTTI_FFMPEG_PATH || "ffmpeg";
const FFPROBE = process.env.PTTI_FFPROBE_PATH || "ffprobe";

const PHOTO_SPECS = [
  {
    asset_id: "commons:acttc-2016:wang-chuqin-1",
    athlete_id: "athlete:121558",
    subject_name: "Wang Chuqin",
    presentation: "PROFILE_CONTEXT_PHOTO",
    source_page_url: "https://commons.wikimedia.org/wiki/File:Wang_Chuqin_ACTTC2016_1.jpeg",
    source_file_url: "https://upload.wikimedia.org/wikipedia/commons/5/5d/Wang_Chuqin_ACTTC2016_1.jpeg",
    source_title: "Wang Chuqin ACTTC2016 1.jpeg",
    photographer: "XIAOYU TANG (original Flickr account: Crew of China Sports)",
    license: "CC BY-SA 2.0",
    license_url: "https://creativecommons.org/licenses/by-sa/2.0/",
    original_relpath: "reviewed-originals/commons-wang-chuqin-acttc2016-1.jpeg",
    expected_sha256: "099f115434756b081e98d29003b8fca7196e8905e2463ace08141022a7604649",
    expected_dimensions: { width: 3061, height: 2041 },
    captured_at: "2016-09-20",
    actual_event: "2016 All China Table Tennis Championships; exact match/opponent not established",
    depicted_athletes: ["Wang Chuqin"],
    identity_evidence: "Commons file caption and structured data name Wang Chuqin; inspected pixels are visually consistent. No match-level association is established.",
    age_at_capture_status: "MINOR_AT_CAPTURE_APPROX_16",
    rights_scope_review: "Commons page states CC BY-SA 2.0 and FlickreviewR confirmed the license. No explicit personality-rights warning was present on the reviewed file page. Scoped approval is limited to a factual athlete-profile context with attribution; no endorsement, advertising, homepage campaign, merchandise, match claim or video-cover use. Minor-at-capture is recorded; this review is not a jurisdiction-specific legal opinion.",
    attribution: "Wang Chuqin ACTTC2016 1.jpeg — Photo by XIAOYU TANG (original Flickr source Crew of China Sports), licensed CC BY-SA 2.0. Source and license links are provided. This factual profile use does not imply endorsement.",
    quality_limit: "High-resolution original (3061x2041). Responsive derivatives use a 4:5 center crop; inspect as a player-profile context image, never as a current match photograph.",
    derivatives: [
      { name: "wang-chuqin-acttc2016-1-800x1000.webp", width: 800, height: 1000, mode: "CROP_4_5" },
      { name: "wang-chuqin-acttc2016-1-400x500.webp", width: 400, height: 500, mode: "CROP_4_5" },
    ],
  },
  {
    asset_id: "commons:cnsvideo:2024-sun-yingsha-interview-still",
    athlete_id: "athlete:131163",
    subject_name: "Sun Yingsha",
    presentation: "PROFILE_INTERVIEW_STILL",
    source_page_url: "https://commons.wikimedia.org/wiki/File:Sun_Yingsha.png",
    source_file_url: "https://upload.wikimedia.org/wikipedia/commons/1/16/Sun_Yingsha.png",
    source_title: "Sun Yingsha.png",
    photographer: "China News Service (CNS); still captured from the CNS interview video",
    license: "CC BY 3.0",
    license_url: "https://creativecommons.org/licenses/by/3.0/",
    original_relpath: "reviewed-originals/commons-sun-yingsha-2024.png",
    expected_sha256: "35cb98f2d947783c031dd8f4816380008a833171fda1099f02a1b6086f02015e",
    expected_dimensions: { width: 498, height: 648 },
    captured_at: "2024-08-11",
    actual_event: "Paris 2024 period CNS interview; not a match photograph",
    depicted_athletes: ["Sun Yingsha"],
    identity_evidence: "Commons file page names Sun Yingsha and CNS; visible interview setting and CNS microphone agree with the caption. The file page links the source interview.",
    age_at_capture_status: "ADULT_AT_CAPTURE",
    rights_scope_review: "Commons records the still as released under YouTube's CC BY 3.0 option, attributes China News Service and links the source interview. No explicit personality-rights warning was shown on the file page. Scoped approval is limited to a factual profile interview still with visible credit; no endorsement, advertising, homepage campaign, merchandise, match claim or video-cover use. This review is not a jurisdiction-specific legal opinion.",
    attribution: "Sun Yingsha.png — China News Service interview still, 11 August 2024; CC BY 3.0. Source interview and license are linked. Resized for profile use; no endorsement is implied.",
    quality_limit: "498x648 source is low resolution relative to a hero image. Do not upscale; maximum suggested CSS width is 249px at DPR 2, and use only in a compact profile context.",
    derivatives: [
      { name: "sun-yingsha-interview-400x520.webp", width: 400, height: 520, mode: "PROPORTIONAL_DOWNSCALE" },
      { name: "sun-yingsha-interview-249x324.webp", width: 249, height: 324, mode: "PROPORTIONAL_DOWNSCALE" },
    ],
  },
  {
    asset_id: "commons:french-championships-2024:felix-lebrun-doubles-context",
    athlete_id: "athlete:135977",
    subject_name: "Félix Lebrun",
    presentation: "MULTI_PLAYER_EVENT_CONTEXT",
    source_page_url: "https://commons.wikimedia.org/wiki/File:Flavien_Coton_et_Alexandre_Cassin_contre_F%C3%A9lix_Lebrun_et_Alexis_Lebrun.jpg",
    source_file_url: "https://upload.wikimedia.org/wikipedia/commons/5/53/Flavien_Coton_et_Alexandre_Cassin_contre_F%C3%A9lix_Lebrun_et_Alexis_Lebrun.jpg",
    source_title: "Flavien Coton et Alexandre Cassin contre Félix Lebrun et Alexis Lebrun.jpg",
    photographer: "Eltito13",
    license: "CC0 1.0",
    license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
    original_relpath: "reviewed-originals/commons-felix-lebrun-french-championships-2024.jpg",
    expected_sha256: "eb034fd9d291323345d70a92b7992b8379f888a82ce13e4df1cf1034612c46d8",
    expected_dimensions: { width: 2585, height: 2192 },
    captured_at: "2024-03-23",
    actual_event: "2024 French Table Tennis Championships doubles scene; exact match/video record is not linked",
    depicted_athletes: ["Flavien Coton", "Alexandre Cassin", "Alexis Lebrun", "Félix Lebrun"],
    identity_evidence: "Commons title, French/English captions and inspected four-player frame identify both Lebrun brothers in the doubles scene. Félix is one of four visible athletes; the whole-frame caption must be retained.",
    age_at_capture_status: "MINOR_AT_CAPTURE_APPROX_17",
    rights_scope_review: "The file page identifies Eltito13 as author and CC0 1.0. CC0 dedicates copyright but does not grant publicity/privacy rights. No explicit personality-rights warning was shown on this file page. Scoped approval is limited to a factual, captioned athlete-profile context image retaining all four players; no isolated face crop, endorsement, advertising, homepage campaign, merchandise, match-ID claim or video-cover use. Minor-at-capture is recorded; this review is not a jurisdiction-specific legal opinion.",
    attribution: "Flavien Coton et Alexandre Cassin contre Félix Lebrun et Alexis Lebrun — photo by Eltito13, dedicated under CC0 1.0. Voluntary credit and source link are retained. The full four-player context is preserved; no endorsement is implied.",
    quality_limit: "High-resolution 2585x2192 full-frame doubles scene. Keep the full context and caption; do not crop or present as a solo portrait or as a match from the PTTI library.",
    derivatives: [
      { name: "felix-lebrun-french-championships-2024-960x814.webp", width: 960, height: 814, mode: "FULL_FRAME_DOWNSCALE" },
      { name: "felix-lebrun-french-championships-2024-480x407.webp", width: 480, height: 407, mode: "FULL_FRAME_DOWNSCALE" },
    ],
  },
];

const VIDEO_SPECS = [
  {
    video_id: "ywX9mUJ8NtI",
    title: "FULL MATCH | Lin Shidong vs Benedikt Duda | MS R16 | WTT Champions Doha 2026",
    published_at: "2026-01-09",
    match_id: "match:ptti:wtt-doha-2026:ms-r16:lin-shidong-benedikt-duda",
    round: "R16",
    other_player: "Benedikt Duda",
  },
  {
    video_id: "Kbhf47vb3eE",
    title: "FULL MATCH | Lin Shidong vs Jang Woojin | MS SF | WTT Champions Doha 2026",
    published_at: "2026-01-12",
    match_id: "match:ptti:wtt-doha-2026:ms-sf:lin-shidong-jang-woojin",
    round: "SF",
    other_player: "Jang Woojin",
  },
];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

export async function sha256File(filePath) {
  const bytes = await readFile(filePath);
  return createHash("sha256").update(bytes).digest("hex");
}

function toolPath(name, configured) {
  return configured || name;
}

function runTool(command, args) {
  const result = spawnSync(command, args, { encoding: "utf8", windowsHide: true, maxBuffer: 8 * 1024 * 1024 });
  if (result.error) throw new Error(`${command} could not run: ${result.error.message}`);
  if (result.status !== 0) throw new Error(`${command} failed (${result.status}): ${(result.stderr || result.stdout).trim()}`);
  return result.stdout.trim();
}

export function validatePublicPhotoManifest(data) {
  assert(data.contract_version === "ptti.goal17.1-athlete-media/0.1", "unknown public photo contract version");
  assert(data.view === "STRICT_PUBLIC_MEDIA_DELTA", "photo package must be a strict additive public view");
  assert(data.assets?.length === 3, "public photo package must contain exactly the three reviewed new assets");
  const ids = new Set();
  for (const asset of data.assets) {
    assert(!ids.has(asset.asset_id), `duplicate asset_id: ${asset.asset_id}`);
    ids.add(asset.asset_id);
    assert(asset.display_permission === "ALLOWED_SCOPED", `asset is not scoped-cleared: ${asset.asset_id}`);
    assert(asset.use_scope === "ATHLETE_PROFILE_EDITORIAL_ONLY", `unexpected use scope: ${asset.asset_id}`);
    assert(asset.match_id === null, `profile photo cannot be match-linked without direct evidence: ${asset.asset_id}`);
    assert(asset.match_link_status === "NOT_LINKED_NO_DIRECT_MATCH_PHOTO_EVIDENCE", `unsafe match link status: ${asset.asset_id}`);
    assert(asset.promotion_use === "NOT_CLEARED_NO_ENDORSEMENT_OR_ADVERTISING", `promotion use was widened: ${asset.asset_id}`);
    assert(asset.commercial_use_review === "NOT_CLEARED_ENDORSEMENT_ADVERTISING_OR_PROMOTION", `commercial use was widened: ${asset.asset_id}`);
    assert(asset.share_alike_required === asset.license.startsWith("CC BY-SA"), `license obligations do not match: ${asset.asset_id}`);
    assert(asset.depicted_athletes?.length > 0 && asset.actual_event, `depiction/event context missing: ${asset.asset_id}`);
    assert(asset.derivatives?.length >= 1, `missing derivatives: ${asset.asset_id}`);
    assert(/^[0-9a-f]{64}$/.test(asset.source_sha256), `invalid source hash: ${asset.asset_id}`);
    for (const derivative of asset.derivatives) {
      assert(/^[0-9a-f]{64}$/.test(derivative.sha256), `invalid derivative hash: ${asset.asset_id}`);
      assert(derivative.format === "WEBP", `unexpected derivative format: ${asset.asset_id}`);
      assert(derivative.metadata_stripped === true, `metadata not stripped: ${asset.asset_id}`);
    }
  }
  return true;
}

export function validateMatchVideoDelta(data, baseLibrary) {
  assert(data.contract_version === "ptti.goal17.1-match-video-additions/0.1", "unknown match/video delta version");
  assert(data.view === "STRICT_PUBLIC_EXTERNAL_LINK_DELTA", "match/video package is not a strict external-link delta");
  assert(data.matches?.length === 2 && data.video_sources?.length === 2, "expected two precisely paired match/video additions");
  const baseIds = new Set(baseLibrary.matches.map((match) => match.match_id));
  const matchIds = new Set();
  const sources = new Map();
  for (const source of data.video_sources) {
    assert(!sources.has(source.source_id), `duplicate source_id: ${source.source_id}`);
    sources.set(source.source_id, source);
    assert(source.source_id === `youtube:${source.provider_video_id}`, `source id does not match provider video id: ${source.source_id}`);
    assert(source.watch_url === `https://www.youtube.com/watch?v=${source.provider_video_id}`, `watch URL and video id disagree: ${source.source_id}`);
    assert(source.watch_route === "OFFICIAL_EXTERNAL_LINK_ONLY", `unexpected watch route: ${source.source_id}`);
    assert(source.playback_status === "NOT_TESTED", `external link cannot become playback PASS: ${source.source_id}`);
    assert(source.embed_permission === "UNKNOWN_NOT_GRANTED", `embed permission was promoted: ${source.source_id}`);
    assert(source.thumbnail_display_permission === "NOT_GRANTED_PENDING_WRITTEN_APPROVAL", `thumbnail permission was promoted: ${source.source_id}`);
    assert(source.download_permission === "NOT_GRANTED", `download permission was promoted: ${source.source_id}`);
    assert(source.local_analysis_permission === "NOT_GRANTED", `analysis permission was promoted: ${source.source_id}`);
    assert(source.redistribution_permission === "NOT_GRANTED", `redistribution permission was promoted: ${source.source_id}`);
    assert(source.territory_status === "UNKNOWN" && source.login_status === "UNKNOWN", `unknown access state was broadened: ${source.source_id}`);
  }
  for (const match of data.matches) {
    assert(!matchIds.has(match.match_id), `duplicate match_id: ${match.match_id}`);
    assert(!baseIds.has(match.match_id), `match id already exists in base package: ${match.match_id}`);
    matchIds.add(match.match_id);
    assert(match.provider_match_id === null && match.match_date === null, `unverified provider match id/date must remain null: ${match.match_id}`);
    assert(match.identity_status === "OFFICIAL_VIDEO_TITLE_MATCH_ASSOCIATION; VISUAL_MATCH_NOT_TESTED", `match identity evidence was overstated: ${match.match_id}`);
    assert(match.video_source_ids.length === 1, `match must bind exactly one video source: ${match.match_id}`);
    const source = sources.get(match.video_source_ids[0]);
    assert(source && source.match_id === match.match_id, `invalid match/source reference: ${match.match_id}`);
    assert(source.title.includes(match.participants[0].display_name) && source.title.includes(match.participants[1].display_name), `source title does not support both participants: ${match.match_id}`);
  }
  assert([...sources.values()].every((source) => matchIds.has(source.match_id)), "orphan video source found");
  return true;
}

async function baselineDigests() {
  const goal16Sha = await sha256File(BASE_GOAL16_PATH);
  const goal15Sha = await sha256File(BASE_GOAL15_PATH);
  assert(goal16Sha === EXPECTED_GOAL16_SHA, "GOAL16 baseline changed; stop and re-review before generating delta");
  assert(goal15Sha === EXPECTED_GOAL15_SHA, "GOAL15 strict-public baseline changed; stop and re-review before generating delta");
  return { goal16Sha, goal15Sha };
}

async function probeDimensions(filePath) {
  const output = runTool(toolPath("ffprobe", FFPROBE), [
    "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", filePath,
  ]);
  const parsed = JSON.parse(output);
  const stream = parsed.streams?.[0];
  assert(stream?.width > 0 && stream?.height > 0, `image dimensions unavailable: ${filePath}`);
  return { width: stream.width, height: stream.height };
}

async function assertNoEmbeddedMetadata(filePath) {
  const output = runTool(toolPath("ffprobe", FFPROBE), [
    "-v", "error", "-show_entries", "format_tags:stream_tags", "-of", "json", filePath,
  ]);
  const parsed = JSON.parse(output);
  const hasFormatTags = Object.keys(parsed.format?.tags || {}).length > 0;
  const hasStreamTags = (parsed.streams || []).some((stream) => Object.keys(stream.tags || {}).length > 0);
  assert(!hasFormatTags && !hasStreamTags, `metadata remains in derivative: ${filePath}`);
  return true;
}

async function createDerivative(spec, derivative) {
  const sourcePath = path.join(PACKAGE_DIR, spec.original_relpath);
  const targetPath = path.join(ASSET_DIR, derivative.name);
  await mkdir(ASSET_DIR, { recursive: true });
  const temporaryPath = `${targetPath}.tmp-${process.pid}`;
  const vf = derivative.mode === "CROP_4_5"
    ? `scale=${derivative.width}:${derivative.height}:force_original_aspect_ratio=increase:flags=lanczos,crop=${derivative.width}:${derivative.height}`
    : `scale=${derivative.width}:${derivative.height}:force_original_aspect_ratio=decrease:flags=lanczos`;
  try {
    runTool(toolPath("ffmpeg", FFMPEG), [
      "-hide_banner", "-loglevel", "error", "-i", sourcePath,
      "-frames:v", "1", "-vf", vf, "-c:v", "libwebp", "-quality", "88", "-compression_level", "6",
      "-map_metadata", "-1", "-f", "webp", "-y", temporaryPath,
    ]);
    const tempSha = await sha256File(temporaryPath);
    try {
      await access(targetPath);
      const existingSha = await sha256File(targetPath);
      assert(existingSha === tempSha, `refusing to overwrite an existing non-matching derivative: ${targetPath}`);
      await rm(temporaryPath);
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
      await rename(temporaryPath, targetPath);
    }
  } finally {
    try { await rm(temporaryPath); } catch { /* no temporary file remains */ }
  }
  const dimensions = await probeDimensions(targetPath);
  assert(dimensions.width === derivative.width && dimensions.height === derivative.height, `unexpected derivative dimensions: ${derivative.name}`);
  await assertNoEmbeddedMetadata(targetPath);
  return {
    path: `assets/${derivative.name}`,
    sha256: await sha256File(targetPath),
    width: dimensions.width,
    height: dimensions.height,
    format: "WEBP",
    license: spec.license,
    changes_made: derivative.mode === "CROP_4_5"
      ? "4:5 center crop, downscaled to responsive WebP, metadata stripped; derivative remains under source license"
      : "Full-frame or proportional downscale to responsive WebP, metadata stripped; derivative remains under source license",
    metadata_stripped: true,
  };
}

function makeContentDelta(baseGoal15Sha) {
  const sources = VIDEO_SPECS.map((spec) => ({
    source_id: `youtube:${spec.video_id}`,
    match_id: spec.match_id,
    provider: "YOUTUBE",
    provider_video_id: spec.video_id,
    title: spec.title,
    publisher: "World Table Tennis",
    publisher_status: "OFFICIAL_VERIFIED_CHANNEL",
    source_published_at: spec.published_at,
    watch_url: `https://www.youtube.com/watch?v=${spec.video_id}`,
    watch_route: "OFFICIAL_EXTERNAL_LINK_ONLY",
    source_page_status: "OFFICIAL_TITLE_METADATA_FOUND; PLAYER_PAGE_NOT_OPENED",
    playback_status: "NOT_TESTED",
    completeness_status: "TITLE_ASSERTS_FULL_MATCH; VISUAL_COMPLETENESS_NOT_VERIFIED",
    embed_permission: "UNKNOWN_NOT_GRANTED",
    thumbnail_display_permission: "NOT_GRANTED_PENDING_WRITTEN_APPROVAL",
    download_permission: "NOT_GRANTED",
    local_analysis_permission: "NOT_GRANTED",
    redistribution_permission: "NOT_GRANTED",
    territory_status: "UNKNOWN",
    login_status: "UNKNOWN",
    copyright_notice: "© WTT; WTT states its content is copyrighted and images may not be reproduced without prior approval.",
    match_identity_evidence: "Official verified WTT channel video title names both players, category, round and event; no in-player visual verification performed.",
  }));
  const matches = VIDEO_SPECS.map((spec) => {
    const source = sources.find((item) => item.match_id === spec.match_id);
    return {
      match_id: spec.match_id,
      provider_match_id: null,
      event_id: "wtt-event:3231",
      event_name: "WTT Champions Doha 2026",
      event_page_url: "https://www.worldtabletennis.com/eventInfo?eventId=3231",
      event_year: 2026,
      category: "MS",
      round: spec.round,
      match_date: null,
      title: `${spec.title.includes("vs ") ? spec.title.split("FULL MATCH | ")[1].split(" | MS")[0] : spec.title}`,
      participants: [
        { athlete_id: "athlete:137237", display_name: "Lin Shidong", identity_status: "CANONICAL_BASE_PACKAGE_ID", identity_evidence_url: source.watch_url },
        { athlete_id: null, display_name: spec.other_player, identity_status: "OFFICIAL_VIDEO_TITLE_NAMED_UNMAPPED", identity_evidence_url: source.watch_url },
      ],
      identity_status: "OFFICIAL_VIDEO_TITLE_MATCH_ASSOCIATION; VISUAL_MATCH_NOT_TESTED",
      identity_evidence_source_id: source.source_id,
      video_source_ids: [source.source_id],
    };
  });
  return {
    contract_version: "ptti.goal17.1-match-video-additions/0.1",
    generated_at: new Date().toISOString(),
    view: "STRICT_PUBLIC_EXTERNAL_LINK_DELTA",
    base_goal15_library_sha256: baseGoal15Sha,
    license_notice: "Additive metadata only. These are official external links; playback, territory, login, embed, thumbnail, download, local analysis and redistribution permissions remain as stated per source. Do not replace the base strict-public package.",
    matches,
    video_sources: sources,
  };
}

async function buildGoal16NineRecheck(goal16Sha) {
  const review = JSON.parse(await readFile(BASE_GOAL16_REVIEW_PATH, "utf8"));
  const sourceManifestPath = path.join(REPO_ROOT, review.source_manifest.path);
  const sourceManifest = JSON.parse(await readFile(sourceManifestPath, "utf8"));
  assert(review.assets.length === 9 && sourceManifest.assets.length === 9, "expected the original nine GOAL16 candidates");
  assert(await sha256File(sourceManifestPath) === review.source_manifest.sha256, "GOAL16 source candidate manifest SHA does not match its review record");
  const manifestAssets = new Map(sourceManifest.assets.map((item) => [item.asset_id, item]));
  const assets = [];
  for (const item of review.assets) {
    const manifestItem = manifestAssets.get(item.asset_id);
    assert(manifestItem, `GOAL16 review asset missing from source manifest: ${item.asset_id}`);
    assert(manifestItem.source_page_url === item.source_page_url, `GOAL16 source page mismatch: ${item.asset_id}`);
    assert(item.photographer.startsWith(manifestItem.photographer) && manifestItem.license === item.license, `GOAL16 author/license mismatch: ${item.asset_id}`);
    assert(JSON.stringify(manifestItem.image_dimensions) === JSON.stringify(item.source_dimensions), `GOAL16 dimensions mismatch: ${item.asset_id}`);
    let actualSha = null;
    let hashStatus = "NOT_MEASURED_ORIGINAL_NOT_STAGED";
    if (item.reviewed_original_relpath) {
      const originalPath = path.join(REPO_ROOT, ...item.reviewed_original_relpath.split("/"));
      actualSha = await sha256File(originalPath);
      assert(actualSha === item.source_sha256, `Goal16 stored original SHA mismatch: ${item.asset_id}`);
      hashStatus = "VERIFIED_LOCAL_ORIGINAL_MATCHES_RECORDED_SHA256";
    }
    const cleared = item.clearance_status === "CLEARED_EDITORIAL_PROFILE_ONLY";
    assets.push({
      asset_id: item.asset_id,
      subject_name: item.subject_name,
      athlete_id: item.athlete_id,
      source_page_url: item.source_page_url,
      source_file_url: item.source_file_url,
      photographer: item.photographer,
      license: item.license,
      source_dimensions: item.source_dimensions,
      identity_review: item.identity_review,
      visual_review: item.visual_review,
      event_review: item.event_review,
      clearance_status: item.clearance_status,
      actual_file_sha256: actualSha,
      actual_file_hash_status: hashStatus,
      use_scenarios: {
        athlete_profile_editorial: cleared ? "CLEARED_SCOPED_RETAIN_EXISTING_GOAL16_PACKAGE" : item.clearance_status,
        homepage_promotion_or_advertising: "NOT_CLEARED",
        exact_match_photograph: "NOT_CLEARED_NO_DIRECT_MATCH_PHOTO_EVIDENCE",
        video_cover_or_thumbnail: "NOT_CLEARED_SEPARATE_PERMISSION_NOT_REVIEWED",
        download_or_redistribution_beyond_license: "NOT_CLEARED",
      },
      blockers: item.blockers,
    });
  }
  return {
    contract_version: "ptti.goal17.1-goal16-photo-recheck/0.1",
    generated_at: new Date().toISOString(),
    baseline_public_manifest_sha256: goal16Sha,
    baseline_rights_review_sha256: await sha256File(BASE_GOAL16_REVIEW_PATH),
    source_candidate_count: assets.length,
    assets,
  };
}

export async function build() {
  const { goal16Sha, goal15Sha } = await baselineDigests();
  const goal15 = JSON.parse(await readFile(BASE_GOAL15_PATH, "utf8"));
  const internalRecheck = await buildGoal16NineRecheck(goal16Sha);

  const publicAssets = [];
  const newPhotoReviews = [];
  for (const spec of PHOTO_SPECS) {
    const sourcePath = path.join(PACKAGE_DIR, spec.original_relpath);
    const actualSha = await sha256File(sourcePath);
    assert(actualSha === spec.expected_sha256, `source image SHA-256 mismatch: ${spec.asset_id}`);
    const dimensions = await probeDimensions(sourcePath);
    assert(dimensions.width === spec.expected_dimensions.width && dimensions.height === spec.expected_dimensions.height, `source dimensions do not match reviewed file page: ${spec.asset_id}`);
    const derivatives = [];
    for (const derivative of spec.derivatives) derivatives.push(await createDerivative(spec, derivative));
    const shareAlike = spec.license.startsWith("CC BY-SA");
    const licenseName = decodeURIComponent(spec.source_page_url.split("File:")[1]).replaceAll("_", " ");
    publicAssets.push({
      asset_id: spec.asset_id,
      athlete_id: spec.athlete_id,
      subject_name: spec.subject_name,
      match_id: null,
      match_link_status: "NOT_LINKED_NO_DIRECT_MATCH_PHOTO_EVIDENCE",
      use_scope: "ATHLETE_PROFILE_EDITORIAL_ONLY",
      display_permission: "ALLOWED_SCOPED",
      promotion_use: "NOT_CLEARED_NO_ENDORSEMENT_OR_ADVERTISING",
      photo_presentation: spec.presentation,
      depicted_athletes: spec.depicted_athletes,
      actual_event: spec.actual_event,
      source_page_url: spec.source_page_url,
      source_file_url: spec.source_file_url,
      source_title: licenseName,
      photographer: spec.photographer,
      license: spec.license,
      license_url: spec.license_url,
      attribution: spec.attribution,
      changes_made: `Source converted/resized to WebP responsive derivatives with metadata removed. ${shareAlike ? "Derivatives remain under the source ShareAlike license." : `The ${spec.license} source license continues to govern the derivatives; voluntary attribution is retained.`}`,
      share_alike_required: shareAlike,
      commercial_use_review: "NOT_CLEARED_ENDORSEMENT_ADVERTISING_OR_PROMOTION",
      source_sha256: actualSha,
      source_dimensions: dimensions,
      derivatives,
      quality_limit: spec.quality_limit,
    });
    newPhotoReviews.push({
      asset_id: spec.asset_id,
      subject_name: spec.subject_name,
      athlete_id: spec.athlete_id,
      source_page_url: spec.source_page_url,
      source_file_url: spec.source_file_url,
      photographer: spec.photographer,
      license: spec.license,
      license_url: spec.license_url,
      source_sha256: actualSha,
      source_dimensions: dimensions,
      captured_at: spec.captured_at,
      age_at_capture_status: spec.age_at_capture_status,
      actual_event: spec.actual_event,
      depicted_athletes: spec.depicted_athletes,
      identity_evidence: spec.identity_evidence,
      visual_review: spec.identity_evidence,
      rights_scope_review: spec.rights_scope_review,
      decision: "CLEARED_SCOPED_ATHLETE_PROFILE_EDITORIAL_ONLY",
      display_permission: "ALLOWED_SCOPED_PROFILE_EDITORIAL_ONLY",
      commercial_use_review: "NOT_CLEARED_ENDORSEMENT_ADVERTISING_OR_PROMOTION",
      homepage_promotion_or_advertising: "NOT_CLEARED",
      match_id: null,
      match_photo_use: "NOT_CLEARED_NO_DIRECT_MATCH_RECORD",
      video_cover_use: "NOT_CLEARED_SEPARATE_PERMISSION_NOT_REVIEWED",
      local_video_or_ai_training_use: "NOT_GRANTED_BY_THIS_IMAGE_REVIEW",
      derivatives: derivatives.map((item) => ({ path: item.path, sha256: item.sha256, width: item.width, height: item.height, license: item.license })),
    });
  }

  const photoManifest = {
    contract_version: "ptti.goal17.1-athlete-media/0.1",
    generated_at: new Date().toISOString(),
    view: "STRICT_PUBLIC_MEDIA_DELTA",
    base_goal16_manifest_sha256: goal16Sha,
    base_goal15_library_sha256: goal15Sha,
    license_notice: "This additive package contains three images cleared only for factual athlete-profile editorial context with visible credit/source/license and preserved context. No image is linked to a GOAL15 match. Homepage promotion, advertising, endorsement, match-photo, video-cover, download beyond license, AI training and other uses require separate review.",
    assets: publicAssets,
  };
  const contentDelta = makeContentDelta(goal15Sha);
  validatePublicPhotoManifest(photoManifest);
  validateMatchVideoDelta(contentDelta, goal15);

  const newCandidateIds = new Set(newPhotoReviews.map((item) => item.asset_id));
  assert(newCandidateIds.size === 3, "new photo candidate IDs are not unique");
  const internalReview = {
    contract_version: "ptti.goal17.1-media-internal-review/0.1",
    generated_at: new Date().toISOString(),
    preserved_baselines: {
      goal16_public_manifest_sha256: goal16Sha,
      goal15_strict_public_library_sha256: goal15Sha,
      goal16_original_review_sha256: internalRecheck.baseline_rights_review_sha256,
    },
    original_goal16_nine_candidate_recheck: internalRecheck,
    new_photo_candidates: newPhotoReviews,
    rejected_focus_photo_candidates: [
      {
        candidate_id: "commons:2026-wtttc:venue-20260503-135123",
        intended_athletes: ["Lin Shidong", "Kuai Man"],
        source_page_url: "https://commons.wikimedia.org/wiki/File:2026_World_Team_Table_Tennis_Championships_20260503_135123.jpg",
        source_file_url: "https://upload.wikimedia.org/wikipedia/commons/9/93/2026_World_Team_Table_Tennis_Championships_20260503_135123.jpg",
        photographer: "Bearas",
        license: "CC BY-SA 4.0",
        license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
        source_dimensions: { width: 4000, height: 3000 },
        source_sha256: null,
        source_hash_status: "NOT_MEASURED_REJECTED_CANDIDATE_NOT_STAGED",
        page_identity_evidence: "The file caption only names the 2026 World Team Table Tennis Championships; Lin Shidong and Kuai Man appear as Commons categories, with no structured depicts statements on the reviewed page.",
        visual_review: "Inspected the actual 4000x3000 original shown in the existing browser tab. It is a wide arena scene with multiple courts and tiny players; neither intended athlete can be identified or presented prominently at profile-card scale.",
        disposition: "NOT_ADMITTED_AS_ATHLETE_PHOTO_OR_MATCH_PHOTO",
        reusable_alternative: "The CC BY-SA license supports attributed use of this venue scene under its terms, but this package has no event-venue image slot; do not use it as a Lin Shidong or Kuai Man portrait or match image.",
      },
    ],
    focus_player_gaps: [
      { subject_name: "Lin Shidong", status: "NO_SUITABLE_CLEARED_PORTRAIT_FOUND", evidence: "The reviewed 2026 Worlds Commons image is a wide venue frame; the athletes are not individually identifiable/prominent at profile-card scale. No image is admitted." },
      { subject_name: "Kuai Man", status: "NO_SUITABLE_CLEARED_PORTRAIT_FOUND", evidence: "The reviewed 2026 Worlds Commons image is a wide venue frame; the player is not individually identifiable/prominent at profile-card scale. No image is admitted." },
      { subject_name: "Félix Lebrun", status: "ONE_SCOPED_CONTEXT_IMAGE_ADMITTED", evidence: "The 2024 French Championships image is a four-player doubles scene; full context/caption retained, no specific PTTI match link." },
    ],
    video_evidence_limitations: "Official WTT title metadata establishes candidate match identity and external links only. No official player page or video player was opened in this session; actual playback, completeness, territory, login and embed remain unverified.",
  };
  validateInternalReview(internalReview);

  await mkdir(INTERNAL_DIR, { recursive: true });
  await mkdir(PUBLIC_DIR, { recursive: true });
  await writeJson(path.join(INTERNAL_DIR, "goal16-nine-photo-recheck.json"), internalRecheck);
  await writeJson(path.join(INTERNAL_DIR, "goal17-1-photo-rights-review.json"), internalReview);
  await writeJson(path.join(PUBLIC_DIR, "athlete-photo-additions.json"), photoManifest);
  await writeJson(path.join(PUBLIC_DIR, "official-match-video-additions.json"), contentDelta);
  return { internalReview, photoManifest, contentDelta };
}

function validateInternalReview(review) {
  assert(review.contract_version === "ptti.goal17.1-media-internal-review/0.1", "unknown internal review version");
  assert(review.original_goal16_nine_candidate_recheck.source_candidate_count === 9, "original GOAL16 nine-candidate review missing");
  const baselineAssets = review.original_goal16_nine_candidate_recheck.assets;
  assert(baselineAssets.length === 9, "must retain exactly nine original GOAL16 candidates");
  for (const item of baselineAssets) {
    if (item.actual_file_hash_status === "NOT_MEASURED_ORIGINAL_NOT_STAGED") {
      assert(item.actual_file_sha256 === null, `unmeasured original has a fabricated hash: ${item.asset_id}`);
      assert(item.clearance_status !== "CLEARED_EDITORIAL_PROFILE_ONLY", `cleared candidate has no local source hash: ${item.asset_id}`);
    }
  }
  assert(review.new_photo_candidates.length === 3, "must retain three new scoped photo reviews");
  assert(review.new_photo_candidates.every((item) => item.decision === "CLEARED_SCOPED_ATHLETE_PROFILE_EDITORIAL_ONLY"), "new photo review contains an unapproved public candidate");
  assert(review.rejected_focus_photo_candidates?.length === 1, "the reviewed Lin Shidong/Kuai Man venue candidate must remain documented");
  const rejectedVenue = review.rejected_focus_photo_candidates[0];
  assert(rejectedVenue.source_sha256 === null && rejectedVenue.source_hash_status === "NOT_MEASURED_REJECTED_CANDIDATE_NOT_STAGED", "rejected venue candidate cannot claim a measured original hash");
  assert(rejectedVenue.disposition === "NOT_ADMITTED_AS_ATHLETE_PHOTO_OR_MATCH_PHOTO", "venue image cannot be mislabeled as a player or match photo");
  return true;
}

async function validateOnDisk() {
  const goal15 = JSON.parse(await readFile(BASE_GOAL15_PATH, "utf8"));
  const photoManifest = JSON.parse(await readFile(path.join(PUBLIC_DIR, "athlete-photo-additions.json"), "utf8"));
  const contentDelta = JSON.parse(await readFile(path.join(PUBLIC_DIR, "official-match-video-additions.json"), "utf8"));
  const internalReview = JSON.parse(await readFile(path.join(INTERNAL_DIR, "goal17-1-photo-rights-review.json"), "utf8"));
  validatePublicPhotoManifest(photoManifest);
  validateMatchVideoDelta(contentDelta, goal15);
  validateInternalReview(internalReview);
  for (const candidate of PHOTO_SPECS) {
    const reviewed = photoManifest.assets.find((item) => item.asset_id === candidate.asset_id);
    assert(reviewed, `public candidate missing: ${candidate.asset_id}`);
    const sourcePath = path.join(PACKAGE_DIR, candidate.original_relpath);
    assert((await sha256File(sourcePath)) === reviewed.source_sha256, `source hash mismatch: ${candidate.asset_id}`);
    for (const derivative of reviewed.derivatives) {
      const assetPath = path.join(PUBLIC_DIR, derivative.path);
      assert((await sha256File(assetPath)) === derivative.sha256, `derivative hash mismatch: ${candidate.asset_id}`);
      const dimensions = await probeDimensions(assetPath);
      assert(dimensions.width === derivative.width && dimensions.height === derivative.height, `derivative dimension mismatch: ${candidate.asset_id}`);
      await assertNoEmbeddedMetadata(assetPath);
    }
  }
  return {
    status: "PASS",
    original_goal16_candidates: internalReview.original_goal16_nine_candidate_recheck.source_candidate_count,
    original_goal16_local_hashes_verified: internalReview.original_goal16_nine_candidate_recheck.assets.filter((item) => item.actual_file_hash_status === "VERIFIED_LOCAL_ORIGINAL_MATCHES_RECORDED_SHA256").length,
    original_goal16_hashes_not_measured_for_noncleared_items: internalReview.original_goal16_nine_candidate_recheck.assets.filter((item) => item.actual_file_hash_status === "NOT_MEASURED_ORIGINAL_NOT_STAGED").length,
    new_scoped_photos: photoManifest.assets.length,
    derivative_count: photoManifest.assets.reduce((sum, item) => sum + item.derivatives.length, 0),
    new_match_records: contentDelta.matches.length,
    new_official_video_sources: contentDelta.video_sources.length,
    photo_manifest_sha256: await sha256File(path.join(PUBLIC_DIR, "athlete-photo-additions.json")),
    video_delta_sha256: await sha256File(path.join(PUBLIC_DIR, "official-match-video-additions.json")),
  };
}

async function writeJson(filePath, value) {
  await writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const mode = process.argv[2];
    if (mode === "--build") {
      await build();
      console.log(JSON.stringify(await validateOnDisk(), null, 2));
    } else if (mode === "--validate") {
      console.log(JSON.stringify(await validateOnDisk(), null, 2));
    } else {
      throw new Error("Use --build or --validate");
    }
  } catch (error) {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  }
}

export { PHOTO_SPECS, VIDEO_SPECS, validateInternalReview, validateOnDisk };
