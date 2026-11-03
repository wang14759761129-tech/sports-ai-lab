import io
import json
import urllib.parse
import urllib.error
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import unittest

from apps.youtube_data_api import YouTubeDataApiConfig, YouTubeDataApiError, fetch_videos_list_batch, fetch_videos_list, configuration_readiness


VIDEO_IDS = [
    "JTUWXpB-NVo", "H77vNFk3neg", "ekfCZiIEYi0", "DTPNEl3-2b0",
    "iQhVLkcGCFE", "0QgbtsBWZhk", "vYsJLPTEIaI", "aFs7HJ0NX18",
]


def config():
    return YouTubeDataApiConfig("TEST_ONLY_NO_REAL_KEY", "APPROVED", "YOUTUBE_DATA_API_V3", "SERVER_RESTRICTED")


class BatchTransportTests(unittest.TestCase):
    def test_exact_eight_ids_and_fields_are_sent_once(self):
        captured = []
        payload = {"items": [{"id": value} for value in VIDEO_IDS]}

        def opener(request, timeout):
            captured.append((request, timeout))
            return io.BytesIO(json.dumps(payload).encode())

        self.assertEqual(fetch_videos_list_batch(VIDEO_IDS, config(), opener=opener), payload)
        request, timeout = captured[0]
        parsed = urllib.parse.urlparse(request.full_url)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual((parsed.scheme, parsed.hostname, parsed.path), ("https", "www.googleapis.com", "/youtube/v3/videos"))
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(query["part"], ["snippet,contentDetails,status"])
        self.assertEqual(query["id"], [",".join(VIDEO_IDS)])
        self.assertEqual(query["maxResults"], ["8"])
        self.assertEqual(query["fields"], ["items(id,snippet(title,channelId,channelTitle,publishedAt,thumbnails),contentDetails(duration),status(privacyStatus,embeddable))"])
        self.assertEqual(timeout, 8)

    def test_invalid_batch_rejected_before_transport(self):
        for ids in ([], ["0QgbtsBWZhk"] * 2, ["short"], VIDEO_IDS * 7):
            calls = []

            def opener(request, timeout):
                calls.append(request)
                return io.BytesIO(b'{"items":[]}')

            with self.assertRaises(YouTubeDataApiError):
                fetch_videos_list_batch(ids, config(), opener=opener)
            self.assertEqual(calls, [])

    def test_unreviewed_client_fails_closed_without_transport(self):
        calls = []

        def opener(request, timeout):
            calls.append(request)
            return io.BytesIO(b'{"items":[]}')

        blocked = YouTubeDataApiConfig("TEST_ONLY_NO_REAL_KEY", "NOT_STARTED", "YOUTUBE_DATA_API_V3", "SERVER_RESTRICTED")
        with self.assertRaises(YouTubeDataApiError):
            fetch_videos_list_batch(VIDEO_IDS, blocked, opener=opener)
        self.assertEqual(calls, [])


    def test_single_profile_keeps_snippet_only_contract(self):
        captured=[]
        payload={"items":[{"id":VIDEO_IDS[0]}]}
        def opener(request,timeout):
            captured.append(request)
            return io.BytesIO(json.dumps(payload).encode())
        self.assertEqual(fetch_videos_list(VIDEO_IDS[0],config(),opener=opener),payload)
        query=urllib.parse.parse_qs(urllib.parse.urlparse(captured[0].full_url).query)
        self.assertEqual(query["part"],["snippet"])
        self.assertEqual(query["maxResults"],["1"])
        self.assertEqual(query["fields"],["items(id,snippet(title,channelId,channelTitle,publishedAt,thumbnails))"])

    def test_transport_errors_are_bounded_and_sanitized_for_both_profiles(self):
        for fetch in (lambda opener: fetch_videos_list(VIDEO_IDS[0], config(), opener=opener),
                      lambda opener: fetch_videos_list_batch(VIDEO_IDS, config(), opener=opener)):
            for body in (b"not-json", b"[]", b"{}", b'{"items":{}}', b'{"items":[null]}', b"x" * (2*1024*1024+1)):
                with self.subTest(body_kind=body[:20]):
                    with self.assertRaises(YouTubeDataApiError):
                        fetch(lambda request, timeout: io.BytesIO(body))
            for failure in (TimeoutError(), urllib.error.HTTPError("https://secret.invalid/?key=TEST_ONLY_NO_REAL_KEY",403,"failed",{},None)):
                def broken(request, timeout):
                    raise failure
                with self.assertRaises(YouTubeDataApiError) as caught:
                    fetch(broken)
                self.assertNotIn("TEST_ONLY_NO_REAL_KEY",str(caught.exception))
                self.assertNotIn("secret.invalid",str(caught.exception))

    def test_unexpected_and_duplicate_response_ids_are_rejected(self):
        for items in ([{"id":"OtherId1234"}], [{"id":VIDEO_IDS[0]},{"id":VIDEO_IDS[0]}]):
            with self.assertRaises(YouTubeDataApiError):
                fetch_videos_list_batch(VIDEO_IDS,config(),opener=lambda request,timeout:io.BytesIO(json.dumps({"items":items}).encode()))

    def test_readiness_does_not_expose_secret_or_claim_live_validation(self):
        ready=configuration_readiness(config())
        self.assertTrue(ready["configuration_ready"])
        self.assertFalse(ready["live_request_executed"])
        self.assertEqual(ready["credential_validity"],"NOT_TESTED")
        self.assertNotIn("TEST_ONLY_NO_REAL_KEY",json.dumps(ready))


class MetadataContractTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def setUp(self):
        self.payload=json.loads((self.root/'frontend/scripts/youtube-videos-list-8.mock.json').read_text(encoding='utf-8'))
        self.catalog=json.loads((self.root/'data/professional/official_video_sources.json').read_text(encoding='utf-8'))['videos']
        self.raw_schema=json.loads((self.root/'data/schemas/youtube-videos-list-response-0.1.schema.json').read_text(encoding='utf-8'))
        self.output_schema=json.loads((self.root/'data/schemas/youtube-video-metadata-poc-0.1.schema.json').read_text(encoding='utf-8'))

    def map_in_node(self,payload):
        script="""import {mapYoutubeVideosList} from './src/youtubeVideoMetadata.mjs';
let text='';for await(const chunk of process.stdin)text+=chunk;
const input=JSON.parse(text);
process.stdout.write(JSON.stringify(mapYoutubeVideosList(input.catalog,input.response,'2026-10-27T00:00:00Z',{dataOrigin:'MOCK'})));"""
        return subprocess.run(['node','--input-type=module','-e',script],input=json.dumps({'catalog':self.catalog,'response':payload}),text=True,capture_output=True,cwd=self.root/'frontend',check=False)

    def test_python_batch_to_node_to_real_json_schema_validation(self):
        # Actual Python transport code, in-memory MOCK opener only: no Google request.
        response=fetch_videos_list_batch(VIDEO_IDS,config(),opener=lambda request,timeout:io.BytesIO(json.dumps(self.payload).encode()))
        self.assertEqual(response,self.payload)
        Draft202012Validator(self.raw_schema,format_checker=FormatChecker()).validate(response)
        mapped=self.map_in_node(response)
        self.assertEqual(mapped.returncode,0,mapped.stderr)
        rows=json.loads(mapped.stdout)
        self.assertEqual(len(rows),8)
        validator=Draft202012Validator(self.output_schema,format_checker=FormatChecker())
        for row in rows:
            validator.validate(row)
            self.assertEqual(row['data_origin'],'MOCK')
            self.assertEqual(row['display_state'],'NO_IMAGE_FALLBACK')
            self.assertEqual(row['embedding_evidence_status'],'API_FIELD_ONLY_NOT_PERMISSION')

    def test_missing_api_id_is_unknown_without_invented_fields(self):
        self.payload['items']=[item for item in self.payload['items'] if item['id']!='0QgbtsBWZhk']
        mapped=self.map_in_node(self.payload)
        self.assertEqual(mapped.returncode,0,mapped.stderr)
        row=next(x for x in json.loads(mapped.stdout) if x['video_id']=='0QgbtsBWZhk')
        self.assertEqual(row['identity_status'],'NOT_RETURNED')
        self.assertIsNone(row['title'])
        self.assertIsNone(row['embeddable'])
        self.assertEqual(row['match_id'],'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun')

    def test_raw_schema_and_node_reject_wrong_boolean_duration_and_date(self):
        import copy
        for field,value in [('embeddable','true'),('duration',25),('publishedAt','invalid')]:
            payload=copy.deepcopy(self.payload)
            item=payload['items'][0]
            section='status' if field=='embeddable' else 'contentDetails' if field=='duration' else 'snippet'
            item[section][field]=value
            self.assertFalse(Draft202012Validator(self.raw_schema,format_checker=FormatChecker()).is_valid(payload))
            self.assertNotEqual(self.map_in_node(payload).returncode,0)

    def test_user_asset_and_visual_source_files_are_unchanged(self):
        # Source-integrity check, not a claim of live SQLite/Native persistence acceptance.
        paths=['frontend/src/VideoFeed.tsx','frontend/src/video-feed.css','frontend/src/LegacyMatchStory.tsx',
               'frontend/src/MomentCardsPage.tsx','frontend/src/ProLab.tsx','frontend/src/FanArena.tsx',
               'frontend/src/favoritePersistence.mjs','frontend/src/matchFavorites.mjs','frontend/src/momentCards.mjs',
               'frontend/src/proLabNotes.mjs','frontend/src/fanArenaEngine.mjs','backend/repository.py',
               'data/professional/official_video_sources.json','data/professional/cover_review/public-match-cover-manifest.v0.2.json']
        for path in paths:
            self.assertTrue((self.root/path).is_file(),path)
        result=subprocess.run(['git','diff','--exit-code','54d75007eb7dc63e33dd8ac419afc20cf7e2615c','--',*paths],cwd=self.root,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__ == "__main__":
    unittest.main()
