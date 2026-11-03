import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cinema_match_adapter',ROOT/'cinema_match_adapter.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)

class CinemaProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.inputs=adapter.load_inputs()
    def test_actual_snapshots_and_relations(self):
        result=adapter.project(self.inputs)
        schema=json.loads((ROOT/'contracts/cinema-match-projection-v0.1.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator(schema,format_checker=FormatChecker()).validate(result)
        self.assertEqual((len(result['matches']),len(result['video_sources'])),(8,18))
        self.assertEqual(sum(s['match_id'] is not None for s in result['video_sources']),8)
        self.assertEqual(len({s['official_url'] for s in result['video_sources']}),18)
        target=next(m for m in result['matches'] if m['match_id']=='pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun')
        self.assertEqual(target['source_ids'],['video-source:youtube:0QgbtsBWZhk'])
        self.assertEqual(sum(s['match_id'] is None for s in result['video_sources']),10)
        self.assertTrue(all(s['media_sha256'] is None and s['playback_status']=='NOT_TESTED' and s['embedding']=='UNKNOWN' for s in result['video_sources']))
    def test_cli_exact_match(self):
        result=subprocess.run([sys.executable,str(ROOT/'cinema_match_adapter.py'),'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun'],capture_output=True,check=True)
        obj=json.loads(result.stdout);self.assertEqual(obj['video_sources'][0]['video_id'],'0QgbtsBWZhk')
        self.assertTrue(obj['evidence_sources'])
    def test_sample_is_reproducible_and_has_no_private_paths(self):
        data=subprocess.check_output([sys.executable,str(ROOT/'cinema_match_adapter.py')])
        self.assertEqual(data,(ROOT/'generated/sprint08-cinema-projection-v0.1.json').read_bytes())
        self.assertNotIn(b'C:\\\\Users',data)
        self.assertNotIn(b'reviewed-originals',data)
        self.assertNotIn(b'INTERNAL_REVIEW_ONLY',data)
    def test_no_guessed_association(self):
        bad=copy.deepcopy(self.inputs);bad[0]['video_sources'][3]['canonical_match_id']=bad[0]['matches'][0]['match_id']
        with self.assertRaisesRegex(ValueError,'SOURCE_MATCH_MISMATCH'): adapter.project(bad)
    def test_duplicate_and_unapproved_rejected(self):
        bad=copy.deepcopy(self.inputs);bad[0]['video_sources'].append(copy.deepcopy(bad[0]['video_sources'][0]))
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SOURCE'):adapter.project(bad)
        for new in ('javascript:alert(1)','https://www.youtube.com.evil.invalid/watch?v=0QgbtsBWZhk','https://www.youtube.com/watch?v=H77vNFk3neg'):
            bad=copy.deepcopy(self.inputs);bad[0]['video_sources'][0]['official_url']=new
            with self.assertRaisesRegex(ValueError,'SOURCE_NOT_ELIGIBLE'):adapter.project(bad)
        bad=copy.deepcopy(self.inputs);bad[0]['video_sources'][0]['rights']['external_viewing']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'SOURCE_NOT_ELIGIBLE'):adapter.project(bad)
    def test_delta_identity_or_visibility_cannot_be_promoted(self):
        for field,value in [('view','INTERNAL_ONLY'),('base_goal15_library_sha256','0'*64)]:
            bad=copy.deepcopy(self.inputs);bad[1][field]=value
            with self.assertRaises(ValueError):adapter.project(bad)

if __name__=='__main__':unittest.main()
