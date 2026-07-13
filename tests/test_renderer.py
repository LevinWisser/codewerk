import unittest

from factory_game.design import ROOT, asset_manifest, design_tokens
from factory_game.iso_renderer import project_iso, unproject_iso


class ProjectionTests(unittest.TestCase):
    def test_projection_round_trip(self):
        for x, y in ((0, 0), (1, 2), (8, 8), (11.75, 3.25)):
            screen = project_iso(x, y, 500, 90, 128, 64)
            restored = unproject_iso(*screen, 500, 90, 128, 64)
            self.assertAlmostEqual(restored[0], x)
            self.assertAlmostEqual(restored[1], y)

    def test_cardinal_directions_have_stable_isometric_axes(self):
        origin = project_iso(0, 0, 400, 60, 128, 64)
        east = project_iso(1, 0, 400, 60, 128, 64)
        south = project_iso(0, 1, 400, 60, 128, 64)
        self.assertGreater(east[0], origin[0])
        self.assertGreater(east[1], origin[1])
        self.assertLess(south[0], origin[0])
        self.assertGreater(south[1], origin[1])


class AssetTests(unittest.TestCase):
    def test_manifest_assets_exist_and_match_declared_sizes(self):
        from PIL import Image

        manifest = asset_manifest()
        self.assertGreaterEqual(len(manifest), 25)
        for name, entry in manifest.items():
            path = ROOT / entry["path"]
            self.assertTrue(path.is_file(), name)
            with Image.open(path) as image:
                self.assertEqual(list(image.size), entry["size"], name)
                self.assertEqual(image.mode, "RGBA", name)

    def test_design_tokens_use_two_to_one_tiles(self):
        geometry = design_tokens()["geometry"]
        self.assertEqual(geometry["tile_width"], geometry["tile_height"] * 2)
        self.assertEqual(geometry["asset_scale"], 2)


if __name__ == "__main__":
    unittest.main()
