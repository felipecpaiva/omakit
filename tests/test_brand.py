import os, tempfile, types, unittest

from omakit import brand
from .fakes import put


class BrandTest(unittest.TestCase):
    def test_contrast(self):
        self.assertAlmostEqual(brand.contrast("#000000", "#ffffff"), 21, places=6)
        self.assertAlmostEqual(brand.contrast("#5aa9ff", "#5aa9ff"), 1)
        self.assertAlmostEqual(brand.contrast("#5aa9ff", brand.PAPER), 2.21, places=2)
        for name, accent in brand.FAMILY:
            self.assertGreaterEqual(brand.contrast(accent, brand.BG), 3, name)

    def test_recolor_is_one_pass(self):
        swapped = brand.recolor('<a fill="#16181D"/><b fill="#8b7bff"/>', {"#16181d": "#8b7bff", "#8b7bff": "#000000"})
        self.assertEqual(swapped, '<a fill="#8b7bff"/><b fill="#000000"/>')

    def test_svg_bits(self):
        s = brand.svg(brand.rect(1, 2, 3, 4, 1, "#fff") + brand.path("M0 0L1 1", "#000", 2), 16, 16)
        self.assertIn('viewBox="0 0 16 16"', s); self.assertIn('rx="1"', s); self.assertIn('stroke-width="2"', s)

    def test_png_and_shot_commands(self):
        calls = []
        brand.png("a.svg", "a.png", 16, run=lambda a, **k: calls.append(a))
        self.assertEqual(calls[0], ["rsvg-convert", "-w", "16", "-o", "a.png", "a.svg"])
        brand.shot("<p>hi</p>", "out.png", 1200, 630, run=lambda a, **k: calls.append(a))
        self.assertIn("--window-size=1200,630", calls[1])

    def test_verify(self):
        d = tempfile.mkdtemp()
        put(os.path.join(d, "icon-16.png"), "w", ""); put(os.path.join(d, "notes.md"), "w", "fine, plain text\n")
        fake = lambda a, **k: types.SimpleNamespace(stdout="16x16")
        r = brand.verify(["icon-16.png", "notes.md"], d, sizes={"icon-16.png": "16x16"}, run=fake)
        self.assertEqual((r["status"], r["text_files_scanned"]), ("passed", 1))
        with self.assertRaises(AssertionError):
            brand.verify(["missing.svg"], d, run=fake)
        put(os.path.join(d, "bad.md"), "w", "a " + chr(0x2014) + " b")
        with self.assertRaises(AssertionError):
            brand.verify([], d, run=fake)

    @unittest.skipUnless(os.path.exists(brand.FALLBACK_FONT), "font not installed")
    def test_lettering_outlines(self):
        try:
            g = brand.lettering("ab", 0, 10, 12, "#fff")
        except ImportError:
            self.skipTest("fontTools not installed")
        self.assertEqual(g.count("<path"), 2); self.assertNotIn("<text", g)
