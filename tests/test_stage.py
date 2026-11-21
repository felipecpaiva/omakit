import os, tempfile, unittest

from omakit.stage import Stage, forget_headless_blocks
from omakit.hypr import Hypr
from .fakes import FakeRun, no_subprocess, put, get


def trash(a):
    os.remove(a[2])


class StageTest(unittest.TestCase):
    def setUp(self):
        self.guard = no_subprocess(); self.guard.start()
        self.tmp = tempfile.mkdtemp()
        self.lines = []

    def tearDown(self):
        self.guard.stop()

    def stage(self, fake, **kw):
        h = Hypr(run=fake, sleep=lambda s: None)
        return Stage(hypr=h, state_home=self.tmp, out=lambda *a, **k: self.lines.append(" ".join(a)), **kw)

    def test_refuses_a_busy_spare_before_changing_anything(self):
        fake = FakeRun(clients=[{"address": "0x1", "workspace": {"id": 8}}])
        with self.assertRaises(SystemExit):
            with self.stage(fake, spare=8):
                pass
        self.assertEqual(fake.evals(), [])
        self.assertNotIn("setDnd", sum(fake.calls, []))

    def test_restores_everything(self):
        layout = os.path.join(self.tmp, "omarchy", "workspace-layouts", "8.lua")
        kept = os.path.join(self.tmp, "config.json"); put(kept, "wb", b"original")
        new = os.path.join(self.tmp, "new.json")
        fake = FakeRun(ws=3, mode="dwindle", dnd="off", cursor=(800, 500), on={"gio": trash})
        with self.stage(fake, spare=8, mode="floating", restore_files=[kept, new], countdown=5) as st:
            self.assertEqual((fake.ws, fake.applied, fake.dnd), (8, "floating", "on"))
            os.makedirs(os.path.dirname(layout)); put(layout, "w", "o.workspace_mode(...)")
            put(kept, "wb", b"changed"); put(new, "w", "x")
            fake.clients.append({"address": "0xd1", "workspace": {"id": 8}})
            fake.clients.append({"address": "0xaa", "workspace": {"id": 2}})
        self.assertEqual((fake.ws, fake.applied, fake.dnd), (3, "dwindle", "off"))
        self.assertEqual(get(kept, "rb"), b"original")
        self.assertFalse(os.path.exists(new)); self.assertFalse(os.path.exists(layout))
        self.assertEqual([c["address"] for c in fake.clients], ["0xaa"])
        self.assertIn('hl.dispatch(hl.dsp.cursor.move({ x = 800, y = 500 }))', fake.evals())
        report = self.lines[-1]
        self.assertTrue(report.startswith("restored: "))
        for part in ("1 closed", "workspace 3", "mode dwindle", "layout file trashed", "config.json exact", "new.json trashed", "dnd off", "cursor 800,500"):
            self.assertIn(part, report)
        self.assertNotIn("FAILED", report)
        self.assertIn("Starting in 5 s", self.lines[0])

    def test_keeps_an_existing_layout_file(self):
        layout = os.path.join(self.tmp, "omarchy", "workspace-layouts", "8.lua")
        os.makedirs(os.path.dirname(layout)); put(layout, "w", "floating")
        fake = FakeRun(mode="floating")
        with self.stage(fake, spare=8, mode="dwindle"):
            put(layout, "w", "dwindle")
        self.assertEqual(get(layout), "floating")
        self.assertEqual(fake.applied, "floating")

    def test_a_string_spare_still_guards(self):
        fake = FakeRun(clients=[{"address": "0x1", "workspace": {"id": 4}}])
        with self.assertRaises(SystemExit):
            with self.stage(fake, spare="4"):
                pass

    def test_mode_is_set_back_even_when_omarchy_reads_the_same(self):
        fake = FakeRun(mode="dwindle")  # eval does not change what Omarchy reads back
        with self.stage(fake, spare=8, mode="floating"):
            self.assertEqual(fake.applied, "floating")
        self.assertEqual(fake.applied, "dwindle")

    def test_restores_after_an_error_and_reports_a_failed_step(self):
        fake = FakeRun(dnd="on", on={"gio": lambda a: (_ for _ in ()).throw(OSError("no gio"))})
        new = os.path.join(self.tmp, "new.json")
        with self.assertRaises(RuntimeError):
            with self.stage(fake, spare=8, restore_files=[new]):
                put(new, "w", "x")
                raise RuntimeError("scene broke")
        self.assertEqual((fake.ws, fake.dnd), (3, "on"))
        self.assertIn("new.json FAILED (no gio)", self.lines[-1])
        self.assertIn("dnd on", self.lines[-1])


class HeadlessTest(unittest.TestCase):
    def test_forgets_only_headless_lines(self):
        with no_subprocess():
            d = tempfile.mkdtemp(); p = os.path.join(d, "monitor-workspaces")
            put(p, "w", "1\tAcme panel\teDP-1\n2\tx\tHEADLESS-2\n3\ty\tHEADLESS-3\n")
            fake = FakeRun()
            self.assertEqual(forget_headless_blocks(p, Hypr(run=fake), sleep=lambda s: None), 2)
            self.assertEqual(get(p), "1\tAcme panel\teDP-1\n")
            self.assertIn(["hyprctl", "reload"], fake.calls)
            self.assertEqual(forget_headless_blocks(p, Hypr(run=fake), sleep=lambda s: None), 0)
