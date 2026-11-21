import os, tempfile, time, types, unittest

from omakit.hypr import Hypr
from omakit.record import Recorder, region_arg
from .fakes import FakeRun, no_subprocess


class RecordTest(unittest.TestCase):
    def test_region_and_native_scale(self):
        with no_subprocess():
            r = Recorder((0, 36, 1280, 764.4), scale="native", cursor=True, hypr=Hypr(run=FakeRun(scale=1.6)))
            self.assertEqual(r.argv("/x.jpg")[:6], ["grim", "-s", "1.6", "-c", "-g", "0,36 1280x764"])
            self.assertEqual(region_arg("1,2 3x4"), "1,2 3x4")

    def test_look_switches_region_and_scale_together(self):
        with no_subprocess():
            r = Recorder("0,25 1600x974", hypr=Hypr(run=FakeRun(scale=1.6)))
            self.assertEqual(r.argv("/x.jpg")[1:5], ["-s", "1", "-g", "0,25 1600x974"])
            r.look((800, 25, 800, 487), 2)
            self.assertEqual(r.argv("/x.jpg")[1:5], ["-s", "2", "-g", "800,25 800x487"])
            self.assertEqual((r.region, r.scale), ("800,25 800x487", 2))
            r.look("0,25 1600x974")
            self.assertEqual(r.argv("/x.jpg")[1:5], ["-s", "1", "-g", "0,25 1600x974"])

    def test_records_and_builds(self):
        def grim(a):
            open(a[-1], "w").close(); time.sleep(0.01)
        fake = FakeRun(on={"grim": grim, "fc-match": lambda a: "", "ffmpeg": lambda a: ""})
        out = tempfile.mkdtemp()
        with no_subprocess():
            with Recorder((0, 0, 100, 100), hypr=Hypr(run=fake)) as r:
                r.caption("one"); time.sleep(0.1); r.mark("two"); time.sleep(0.1)
                paths = r.finish("scene", out_dir=out, fontsize=30)
        self.assertEqual([os.path.basename(p) for p in paths], ["scene.gif", "scene.mp4"])
        self.assertEqual([m[1] for m in r.marks], ["one", "two", ""])
        self.assertGreater(len(r.frames), 2)
        self.assertFalse(os.path.exists(r.dir))
        ff = [c for c in fake.calls if c[0] == "ffmpeg"]
        self.assertEqual(len(ff), 2)
        self.assertIn("fontsize=30", ff[0][ff[0].index("-filter_complex") + 1])
