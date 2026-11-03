import copy
import json
from pathlib import Path
import unittest

import build_goal23 as builder


class Goal65IdentityTests(unittest.TestCase):
    def test_pinned_candidate_and_reject_changed_identities(self):
        path = Path(builder.__file__).parent.parent / 'goal65/goal65-build.json'
        config = json.loads(path.read_text(encoding='utf-8'))
        builder.validate_config(config)
        for field, value in [('san_commit', '0' * 40), ('qa_port', 4211),
                             ('version', '0.1.10-cinema-b8017ac'),
                             ('minimum_idle_seconds', 0),
                             ('main_content_manifest_sha256', '0' * 64)]:
            with self.subTest(field=field):
                changed = copy.deepcopy(config)
                changed[field] = value
                with self.assertRaises(builder.BuildError):
                    builder.validate_config(changed)


if __name__ == '__main__':
    unittest.main()
