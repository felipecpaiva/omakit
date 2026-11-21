import json, types, unittest

from omakit.hypr import Hypr
from .fakes import FakeRun, no_subprocess


class HyprTest(unittest.TestCase):
    def test_monitor_is_logical(self):
        with no_subprocess():
            h = Hypr(run=FakeRun(scale=1.6))
            m = h.monitor()
            self.assertEqual((m["width"], m["height"], m["scale"], m["pwidth"]), (1600, 1000, 1.6, 2560))
            self.assertEqual(h.physical(100), 160)

    def test_rotated_monitor_swaps_sides(self):
        mon = [{"name": "DP-1", "x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1, "transform": 1, "focused": True}]
        h = Hypr(run=lambda a, **k: types.SimpleNamespace(stdout=json.dumps(mon)))
        self.assertEqual((h.monitor()["width"], h.monitor()["height"]), (1080, 1920))

    def test_queries(self):
        h = Hypr(run=FakeRun(ws=5, cursor=(10, 20)))
        self.assertEqual((h.active_ws(), h.cursor(), h.layout_mode(8)), (5, (10, 20), "dwindle"))
