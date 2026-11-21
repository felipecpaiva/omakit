"""Record a screen region with grim in a loop and turn it into a captioned GIF and MP4 with gifkit.
    with Recorder((0, 36, 1280, 764)) as r:
        r.caption("Hold Alt"); ...
        r.finish("switch", out_dir="branding/demo", width=960)
The region is in logical (layout) pixels, which is what grim -g takes. scale sets the frame size: 1 gives frames at
the logical size, "native" uses the monitor scale for full resolution frames (needed when a gifkit compose crops in
physical pixels). look() switches region and scale mid recording, for a zoom onto one part."""
import os, shutil, tempfile, threading, time

from . import gifkit
from .hypr import Hypr


def region_arg(region):
    if isinstance(region, str):
        return region
    x, y, w, h = (round(v) for v in region)
    return f"{x},{y} {w}x{h}"


class Recorder:
    def __init__(self, region, scale=1, cursor=False, quality=88, hypr=None):
        self.h = hypr or Hypr()
        self.quality, self.cursor = quality, cursor
        self.look(region, scale)
        self.frames, self.marks, self.stop, self.th = [], [], threading.Event(), None
        self.dir = tempfile.mkdtemp(prefix="omakit-frames-")

    def look(self, region, scale=1):
        """Switch the captured region and scale, also mid recording. Region and scale change together (one tuple), so a
        frame is never taken with one new and one old. Keep the output size: w * scale and h * scale equal to the old
        ones (for example half the region at scale 2 for a zoom), or ffmpeg gets frames of two sizes."""
        self.view = (region_arg(region), self.h.monitor()["scale"] if scale == "native" else scale)

    region = property(lambda self: self.view[0])
    scale = property(lambda self: self.view[1])

    def argv(self, path):
        region, scale = self.view
        return ["grim", "-s", f"{scale:g}", *(["-c"] if self.cursor else []), "-g", region,
                "-t", "jpeg", "-q", str(self.quality), path]

    def __enter__(self):
        self.t0 = time.time()

        def grab():
            n = 0
            while not self.stop.is_set():
                p = os.path.join(self.dir, f"f{n:05d}.jpg")
                a = time.time() - self.t0
                self.h.run(self.argv(p))
                if os.path.exists(p):  # a failed capture leaves no file; skip it rather than build from a hole
                    self.frames.append((a, p)); n += 1
        self.th = threading.Thread(target=grab, daemon=True)
        self.th.start()
        return self

    def caption(self, text):
        """Show text from now until the next caption ('' clears it)."""
        self.marks.append((time.time() - self.t0, text))

    mark = caption

    def _stop(self):
        self.stop.set()
        if self.th:
            self.th.join()

    def finish(self, name, out_dir, **kw):
        """Stop, build out_dir/name.gif and .mp4 (kw go to gifkit.build), remove the frames, return the paths."""
        self.marks.append((time.time() - self.t0, ""))
        self._stop()
        total = time.time() - self.t0
        kw.setdefault("run", self.h.run)
        try:
            out = gifkit.build(self.frames, total, self.marks, out_dir, name, **kw)
        finally:
            shutil.rmtree(self.dir, ignore_errors=True)
        print(f"wrote {out[0]} ({len(self.frames)} frames in {total:.1f} s)", flush=True)
        return out

    def __exit__(self, *exc):
        self._stop()
        shutil.rmtree(self.dir, ignore_errors=True)
