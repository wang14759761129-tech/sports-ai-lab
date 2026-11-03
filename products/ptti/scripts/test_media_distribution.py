"""Lightweight packaging-staging tests; no backend imports or databases."""
import tempfile
import unittest
from pathlib import Path
from media_distribution import stage_professional_catalog, ACTIVE_MANIFEST


class MediaDistributionTests(unittest.TestCase):
    def test_staging_keeps_registry_and_active_manifest_without_history(self):
        with tempfile.TemporaryDirectory(prefix="ptti-media-stage-") as folder:
            root = Path(folder) / "source"
            data = root / "data/professional"
            reviews = data / "cover_review"
            reviews.mkdir(parents=True)
            (data / "registry.json").write_text('{"matches": []}')
            (reviews / ACTIVE_MANIFEST).write_text('{"assets": []}')
            (reviews / "public-match-cover-manifest.v0.1.json").write_text('{"historical": true}')
            target = Path(folder) / "build"
            result = stage_professional_catalog(root, target)
            self.assertEqual((result / "registry.json").read_bytes(), (data / "registry.json").read_bytes())
            self.assertEqual([p.name for p in (result / "cover_review").iterdir()], [ACTIVE_MANIFEST])
            self.assertTrue((reviews / "public-match-cover-manifest.v0.1.json").exists())


if __name__ == "__main__":
    unittest.main()
