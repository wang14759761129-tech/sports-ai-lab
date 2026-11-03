import test from "node:test";
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import {
  PACKAGE_DIR,
  PUBLIC_DIR,
  INTERNAL_DIR,
  validatePublicPhotoManifest,
  validateMatchVideoDelta,
  validateInternalReview,
  validateOnDisk,
} from "../scripts/build_goal17_1_real_content.mjs";

const photoSchema = JSON.parse(await readFile(path.resolve("products/ptti-integration/contracts/goal17-1-athlete-media-v0.1.schema.json"), "utf8"));
const matchSchema = JSON.parse(await readFile(path.resolve("products/ptti-integration/contracts/goal17-1-match-video-additions-v0.1.schema.json"), "utf8"));
const photoManifest = JSON.parse(await readFile(path.join(PUBLIC_DIR, "athlete-photo-additions.json"), "utf8"));
const matchDelta = JSON.parse(await readFile(path.join(PUBLIC_DIR, "official-match-video-additions.json"), "utf8"));
const internalReview = JSON.parse(await readFile(path.join(INTERNAL_DIR, "goal17-1-photo-rights-review.json"), "utf8"));
const goal15 = JSON.parse(await readFile(path.resolve("products/ptti-integration/generated/goal15-main-fan-universe-public-v0.2/match-library-strict-public.json"), "utf8"));

function assertSchema(value, schema, root = schema, location = "$", resolveRef = true) {
  if (resolveRef && schema.$ref) {
    const target = schema.$ref.split("/").slice(1).reduce((node, key) => node[key.replaceAll("~1", "/").replaceAll("~0", "~")], root);
    return assertSchema(value, target, root, location, false);
  }
  if (schema.const !== undefined) assert.equal(value, schema.const, `${location} const`);
  if (schema.enum) assert.ok(schema.enum.includes(value), `${location} enum`);
  if (schema.type === "object") {
    assert.ok(value && typeof value === "object" && !Array.isArray(value), `${location} object`);
    for (const key of schema.required || []) assert.ok(Object.hasOwn(value, key), `${location}.${key} required`);
    if (schema.additionalProperties === false) {
      for (const key of Object.keys(value)) assert.ok(Object.hasOwn(schema.properties || {}, key), `${location}.${key} additional property`);
    }
    for (const [key, childSchema] of Object.entries(schema.properties || {})) {
      if (Object.hasOwn(value, key)) assertSchema(value[key], childSchema, root, `${location}.${key}`);
    }
  } else if (schema.type === "array") {
    assert.ok(Array.isArray(value), `${location} array`);
    if (schema.minItems !== undefined) assert.ok(value.length >= schema.minItems, `${location} minItems`);
    if (schema.maxItems !== undefined) assert.ok(value.length <= schema.maxItems, `${location} maxItems`);
    value.forEach((item, index) => assertSchema(item, schema.items, root, `${location}[${index}]`));
  } else if (schema.type === "string") {
    assert.equal(typeof value, "string", `${location} string`);
    if (schema.minLength) assert.ok(value.length >= schema.minLength, `${location} minLength`);
    if (schema.pattern) assert.match(value, new RegExp(schema.pattern), `${location} pattern`);
    if (schema.format === "uri") assert.doesNotThrow(() => new URL(value), `${location} uri`);
    if (schema.format === "date-time") assert.ok(Number.isFinite(Date.parse(value)), `${location} date-time`);
    if (schema.format === "date") assert.match(value, /^\d{4}-\d{2}-\d{2}$/, `${location} date`);
  } else if (schema.type === "null") {
    assert.equal(value, null, `${location} null`);
  } else if (schema.type === "boolean") {
    assert.equal(typeof value, "boolean", `${location} boolean`);
  } else if (schema.type === "integer") {
    assert.ok(Number.isInteger(value), `${location} integer`);
    if (schema.minimum !== undefined) assert.ok(value >= schema.minimum, `${location} minimum`);
  } else if (Array.isArray(schema.type)) {
    assert.ok(schema.type.some((type) => type === "null" ? value === null : typeof value === type), `${location} union type`);
  }
}

test("public photo delta matches strict schema and only grants profile editorial scope", () => {
  assertSchema(photoManifest, photoSchema);
  assert.equal(validatePublicPhotoManifest(photoManifest), true);
  assert.equal(photoManifest.assets.length, 3);
  assert.deepEqual(photoManifest.assets.map((asset) => asset.subject_name), ["Wang Chuqin", "Sun Yingsha", "Félix Lebrun"]);
  assert.ok(photoManifest.assets.every((asset) => asset.match_id === null && asset.promotion_use === "NOT_CLEARED_NO_ENDORSEMENT_OR_ADVERTISING"));
  const sun = photoManifest.assets.find((asset) => asset.subject_name === "Sun Yingsha");
  assert.match(sun.changes_made, /CC BY 3\.0 source license/);
  assert.doesNotMatch(sun.changes_made, /CC0 source/);
});

test("photo gate rejects unsafe match claims, broad promotion, duplicate ids and extra fields", () => {
  for (const mutation of [
    (value) => { value.assets[0].match_id = "match:guess"; },
    (value) => { value.assets[0].promotion_use = "ALLOWED"; },
    (value) => { value.assets[0].share_alike_required = false; },
    (value) => { value.assets[0].commercial_use_review = "ALLOWED"; },
    (value) => { value.assets[1].asset_id = value.assets[0].asset_id; },
  ]) {
    const invalid = structuredClone(photoManifest);
    mutation(invalid);
    assert.throws(() => validatePublicPhotoManifest(invalid));
  }
  const extraField = structuredClone(photoManifest);
  extraField.assets[0].unreviewed = true;
  assert.throws(() => assertSchema(extraField, photoSchema));
});

test("match/video delta matches schema and keeps viewing permission external-only and untested", () => {
  assertSchema(matchDelta, matchSchema);
  assert.equal(validateMatchVideoDelta(matchDelta, goal15), true);
  assert.equal(matchDelta.matches.length, 2);
  assert.ok(matchDelta.video_sources.every((source) => source.playback_status === "NOT_TESTED" && source.embed_permission === "UNKNOWN_NOT_GRANTED"));
  assert.ok(matchDelta.video_sources.every((source) => source.thumbnail_display_permission === "NOT_GRANTED_PENDING_WRITTEN_APPROVAL"));
});

test("match/video gate rejects mismatched ids, duplicate sources and playback escalation", () => {
  for (const mutation of [
    (value) => { value.video_sources[0].watch_url = "https://www.youtube.com/watch?v=aaaaaaaaaaa"; },
    (value) => { value.video_sources[0].playback_status = "PASS"; },
    (value) => { value.video_sources[1].source_id = value.video_sources[0].source_id; },
    (value) => { value.matches[0].video_source_ids[0] = "youtube:missing"; },
  ]) {
    const invalid = structuredClone(matchDelta);
    mutation(invalid);
    assert.throws(() => validateMatchVideoDelta(invalid, goal15));
  }
});

test("all nine GOAL16 candidates retain scoped decisions and honest hash coverage", () => {
  assert.equal(validateInternalReview(internalReview), true);
  const assets = internalReview.original_goal16_nine_candidate_recheck.assets;
  assert.equal(assets.length, 9);
  assert.equal(assets.filter((item) => item.actual_file_hash_status === "VERIFIED_LOCAL_ORIGINAL_MATCHES_RECORDED_SHA256").length, 4);
  assert.equal(assets.filter((item) => item.actual_file_hash_status === "NOT_MEASURED_ORIGINAL_NOT_STAGED").length, 5);
  for (const item of assets.filter((candidate) => candidate.actual_file_sha256 === null)) {
    assert.notEqual(item.clearance_status, "CLEARED_EDITORIAL_PROFILE_ONLY");
    assert.equal(item.actual_file_hash_status, "NOT_MEASURED_ORIGINAL_NOT_STAGED");
  }
  const rejected = internalReview.rejected_focus_photo_candidates[0];
  assert.equal(rejected.source_sha256, null);
  assert.equal(rejected.source_hash_status, "NOT_MEASURED_REJECTED_CANDIDATE_NOT_STAGED");
  assert.equal(rejected.disposition, "NOT_ADMITTED_AS_ATHLETE_PHOTO_OR_MATCH_PHOTO");
  assert.match(rejected.visual_review, /wide arena scene with multiple courts/);
});

test("public folder contains only described derivatives; build validates hashes and dimensions", async () => {
  const result = await validateOnDisk();
  assert.equal(result.status, "PASS");
  assert.equal(result.original_goal16_local_hashes_verified, 4);
  assert.equal(result.original_goal16_hashes_not_measured_for_noncleared_items, 5);
  assert.equal(result.new_scoped_photos, 3);
  const names = (await readdir(path.join(PUBLIC_DIR, "assets"))).sort();
  const expected = photoManifest.assets.flatMap((asset) => asset.derivatives.map((item) => path.basename(item.path))).sort();
  assert.deepEqual(names, expected);
  const publicEntries = (await readdir(PUBLIC_DIR)).sort();
  assert.deepEqual(publicEntries, ["assets", "athlete-photo-additions.json", "official-match-video-additions.json"]);
  const publicJson = `${JSON.stringify(photoManifest)}${JSON.stringify(matchDelta)}`;
  assert.doesNotMatch(publicJson, /(?:[A-Z]:\\|products\\ptti-integration\\generated|reviewed-originals|internal-review)/i);
  assert.equal(PACKAGE_DIR.endsWith("goal17-1-real-content-v0.1"), true);
});
