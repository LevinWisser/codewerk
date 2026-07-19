import unittest

from factory_game.design import ROOT, asset_manifest, design_tokens
from factory_game.fixed_renderer import fixed_layouts, point_in_polygon
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

    def test_fixed_view_layouts_cover_every_factory_size(self):
        from PIL import Image

        layouts = fixed_layouts()
        self.assertEqual(set(layouts), {"8", "10", "12"})
        for size_text, layout in layouts.items():
            size = int(size_text)
            self.assertEqual(len(layout["tiles"]), size * size)
            image_path = ROOT / layout["image"]
            self.assertTrue(image_path.is_file())
            with Image.open(image_path) as image:
                self.assertEqual(list(image.size), layout["render_size"])
                self.assertEqual(image.mode, "RGBA")

    def test_fixed_view_sprite_family_has_transparency(self):
        from PIL import Image

        root = ROOT / "assets" / "runtime" / "fixed"
        sprites = [path for path in root.rglob("*.png") if path.parent.name != "world"]
        self.assertEqual(len(sprites), 8)
        for path in sprites:
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA", path.name)
                self.assertEqual(image.getchannel("A").getextrema(), (0, 255), path.name)

    def test_fixed_view_coordinates_and_polygons_match_screen_direction(self):
        layout = fixed_layouts()["10"]
        origin = layout["tiles"]["0,0"]["center"]
        east = layout["tiles"]["1,0"]["center"]
        south = layout["tiles"]["0,1"]["center"]
        self.assertGreater(east[0], origin[0])
        self.assertGreater(south[1], origin[1])
        polygon = [tuple(point) for point in layout["tiles"]["0,0"]["polygon"]]
        self.assertTrue(point_in_polygon(tuple(origin), polygon))


if __name__ == "__main__":
    unittest.main()
