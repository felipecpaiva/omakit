"""A safe stage for live demos and tests: a spare, empty workspace, Do Not Disturb, and everything put back after.
    with Stage(spare=8, mode="floating", restore_files=[cfg]) as st:
        ... open demo windows on the spare workspace, record ...
On exit (also after an error) it closes every window left on the spare workspace (it was empty, so they are all
ours), focuses the workspace you came from, puts back the spare's layout mode and Omarchy's saved layout file for it,
Do Not Disturb, the listed files (their bytes, or gio trash when they did not exist) and the pointer, then prints a
"restored:" line. Each step runs on its own, so one failure does not skip the rest; failures show in the report."""
import os, time

from .hypr import Hypr


def _state_home():
    return os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


class Stage:
    def __init__(self, spare=8, dnd=True, restore_files=(), cursor=True, countdown=0, mode=None, hypr=None,
                 state_home=None, out=print):
        self.h = hypr or Hypr()
        self.spare, self.dnd, self.cursor, self.countdown, self.mode, self.out = spare, dnd, cursor, countdown, mode, out
        self.layout_file = os.path.join(state_home or _state_home(), "omarchy", "workspace-layouts", f"{spare}.lua")
        self.files = [os.path.abspath(os.path.expanduser(p)) for p in restore_files]
        self.report = []

    def __enter__(self):
        h = self.h
        if any(c["workspace"]["id"] == self.spare for c in h.clients()):
            raise SystemExit(f"spare workspace {self.spare} is not empty; not touching it")
        self.origin = h.active_ws()
        self.mode0 = h.layout_mode(self.spare)
        self.saved = {p: _read(p) for p in [self.layout_file, *self.files]}
        self.dnd0 = h.sh("omarchy-shell", "notifications", "isDnd") if self.dnd else None
        self.cursor0 = h.cursor() if self.cursor else None
        if self.countdown:
            self.out(f"Starting in {self.countdown} s. Hands off the keyboard, mouse and screen.", flush=True)
            h.sleep(self.countdown)
        try:
            if self.dnd:
                h.sh("omarchy-shell", "notifications", "setDnd", "on")
            h.focus_ws(self.spare); h.sleep(0.8)
            if self.mode:
                h.set_layout_mode(self.spare, self.mode); h.sleep(0.8)
        except BaseException:
            self.restore()
            raise
        return self

    def __exit__(self, *exc):
        self.restore()

    def _step(self, label, fn):
        try:
            r = fn()
            if r:
                self.report.append(f"{label} {r}" if label else r)
        except Exception as e:  # keep going: the other steps still have to run
            self.report.append(f"{label or 'step'} FAILED ({e})")

    def _close_spare(self):
        mine = [c for c in self.h.clients() if c["workspace"]["id"] == self.spare]
        for c in mine:
            self.h.close(c["address"])
        if mine:
            self.h.sleep(1.5)
        return f"{len(mine)} closed"

    def _origin(self):
        if self.origin is not None:
            self.h.focus_ws(self.origin); self.h.sleep(0.5)
        return self.origin

    def _mode(self):
        if self.h.layout_mode(self.spare) != self.mode0:
            self.h.set_layout_mode(self.spare, self.mode0); self.h.sleep(0.5)
        return self.mode0

    def _file(self, path):
        before, now = self.saved[path], _read(path)
        if before is None:
            if now is None:
                return None
            self.h.run(["gio", "trash", path])
            return "trashed" if not os.path.exists(path) else "NOT TRASHED"
        if now != before:
            tmp = path + ".omakit-restore"
            with open(tmp, "wb") as f:
                f.write(before)
            os.replace(tmp, path)
        return "exact" if _read(path) == before else "DIFFERENT"

    def _dnd(self):
        want = self.dnd0 if self.dnd0 in ("on", "off") else "off"
        self.h.sh("omarchy-shell", "notifications", "setDnd", want)
        return self.h.sh("omarchy-shell", "notifications", "isDnd")

    def _cursor(self):
        if self.cursor0:
            self.h.move_cursor(*self.cursor0)
            return "%g,%g" % self.cursor0

    def restore(self):
        self.report = []
        self._step(f"spare {self.spare} windows", self._close_spare)
        self._step("workspace", self._origin)
        self._step(f"spare {self.spare} mode", self._mode)
        self._step("layout file", lambda: self._file(self.layout_file))
        for p in self.files:
            self._step(os.path.basename(p), lambda p=p: self._file(p))
        if self.dnd:
            self._step("dnd", self._dnd)
        if self.cursor:
            self._step("cursor", self._cursor)
        self.out("restored: " + " | ".join(self.report), flush=True)
        return self.report


def forget_headless_blocks(path=None, hypr=None, sleep=time.sleep):
    """Omarchy gives every monitor it sees (by make, model and serial) a block of ten workspaces and remembers it for
    good in ~/.local/state/omarchy/monitor-workspaces. A virtual (headless) monitor uses up a block, so real monitors
    plugged in later get high workspace numbers. This removes the HEADLESS-n lines (a .omakit-backup copy is kept next
    to the file) and reloads Hyprland so Omarchy reads it again. Returns how many entries it removed. It reloads
    Hyprland, so call it explicitly, only after something created a virtual monitor (better: never create one)."""
    path = path or os.path.join(_state_home(), "omarchy", "monitor-workspaces")
    if not os.path.exists(path):
        return 0
    with open(path) as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    keep = [l for l in lines if not l.split("\t")[-1].startswith("HEADLESS-")]
    removed = len(lines) - len(keep)
    if removed:
        with open(path + ".omakit-backup", "w") as f:
            f.write("\n".join(lines) + "\n")
        with open(path, "w") as f:
            f.write("\n".join(keep) + "\n")
        (hypr or Hypr()).run(["hyprctl", "reload"])
        sleep(2.5)
    return removed
