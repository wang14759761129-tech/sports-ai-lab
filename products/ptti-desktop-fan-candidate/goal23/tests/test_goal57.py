"""GOAL57 identity and isolation regressions; no GUI or compilation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_goal23 as builder


class Goal57Tests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((builder.HERE.parent / 'goal57/goal57-build.json').read_text(encoding='utf-8'))

    def test_new_and_frozen_profiles_validate_independently(self):
        builder.validate_config(self.config)
        for path in [builder.CONFIG_PATH, builder.HERE.parent / 'goal30/goal30-build.json']:
            builder.validate_config(json.loads(path.read_text(encoding='utf-8')))

    def test_wrong_sources_version_port_bridge_or_idle_fail_closed(self):
        for key, value in [('san_commit','0'*40), ('main_commit','1'*40),
                           ('playback_commit','2'*40), ('version','0.1.9-fan-03df597'),
                           ('qa_port',4209), ('minimum_available_gib',2.49),
                           ('minimum_idle_seconds',0), ('native_bridge_status','ENABLED')]:
            bad=copy.deepcopy(self.config); bad[key]=value
            with self.subTest(key=key), self.assertRaises(builder.BuildError):
                builder.validate_config(bad)

    def test_delta_and_playback_pins_are_mandatory(self):
        for key in ['public_package_hashes','public_package_contract_versions','playback_source_hashes']:
            bad=copy.deepcopy(self.config); bad[key].pop(next(iter(bad[key])))
            with self.subTest(key=key), self.assertRaises(builder.BuildError):
                builder.validate_config(bad)

    def test_playback_unavailable_stops_before_manifest_or_staging(self):
        with self.assertRaises(builder.BuildError):
            builder.verify_goal57_provenance(self.config, Path('.'), Path('.'), None)

    def test_low_ram_stops_before_build_tool_or_stage(self):
        with patch.object(builder, 'available_gib', return_value=2.49), patch.object(builder,'run_checked') as run:
            with self.assertRaises(builder.BuildBlocked):
                builder.build_candidate(None,self.config,{})
            run.assert_not_called()

    def test_old_and_new_profiles_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertNotEqual(builder.qa_profile_path(Path(temp),'0.1.9-goal30',4209),
                                builder.qa_profile_path(Path(temp),self.config['host_version'],4211))

    def test_main_manifest_tampering_fails(self):
        bad=copy.deepcopy(self.config); bad['main_content_manifest_sha256']='0'*64
        with self.assertRaises(builder.BuildError):
            builder.validate_config(bad)


if __name__=='__main__': unittest.main()
