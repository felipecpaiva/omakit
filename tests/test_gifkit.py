import os, tempfile, types, unittest

from omakit import gifkit
from .fakes import no_subprocess


class GifkitTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.dir = tempfile.mkdtemp()
        self.frames = []
        for i in range(3):
            p = os.path.join(self.dir, f"f{i}.jpg"); open(p, "w").close(); self.frames.append((i * 0.5, p))

    def run_(self, argv, **kw):
        self.calls.append(argv)
        if argv[0] == "ffmpeg":  # the frame sequence must exist while ffmpeg runs
            seq = os.path.dirname(argv[argv.index("-i") + 1])
            self.seq = seq; self.ticks = len(os.listdir(seq))
        return types.SimpleNamespace(stdout="", returncode=0)

    def test_builds_gif_and_mp4(self):
        with no_subprocess():
            out = gifkit.build(self.frames, 1.5, [(0, "Hold Alt: 50% faster"), (1.0, "")], self.dir, "demo", font="/f.ttf",
                               compose="crop=10:10:0:0", color="#ffffff", run=self.run_)
        self.assertEqual(out, [os.path.join(self.dir, "demo.gif"), os.path.join(self.dir, "demo.mp4")])
        gif, mp4 = self.calls
        graph = gif[gif.index("-filter_complex") + 1]
        self.assertTrue(graph.startswith("crop=10:10:0:0,drawtext=fontfile=/f.ttf:text='Hold Alt\\: 50\\% faster'"))
        self.assertIn("fontcolor=#ffffff", graph)
        self.assertIn("between(t,0.00,1.00)", graph)
        self.assertIn("libx264", mp4)
        self.assertEqual(self.ticks, 18)  # 1.5 s at 12 fps
        self.assertFalse(os.path.exists(self.seq))  # the symlink folder is removed

    def test_no_caption_no_drawtext(self):
        gifkit.build(self.frames, 1, [(0, "")], self.dir, "d", font="/f.ttf", mp4=False, run=self.run_)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("drawtext", self.calls[0][self.calls[0].index("-filter_complex") + 1])

    def test_default_font_falls_back(self):
        self.assertEqual(gifkit.default_font(lambda a, **k: types.SimpleNamespace(stdout="")), gifkit.FALLBACK_FONT)
        f = self.frames[0][1]
        self.assertEqual(gifkit.default_font(lambda a, **k: types.SimpleNamespace(stdout=f)), f)

    def test_no_frames(self):
        with self.assertRaises(ValueError):
            gifkit.build([], 1, [], self.dir, "d", font="/f", run=self.run_)
