"""Small helpers around hyprctl. Every command goes through Hypr.run, so tests can inject a fake runner.
Creating a Hypr runs nothing; the module level functions use a shared default instance."""
import glob, json, os, subprocess, time


def _env():
    """The environment with a live HYPRLAND_INSTANCE_SIGNATURE: agent shells often carry a stale one."""
    e = dict(os.environ)
    base = os.path.join(e.get("XDG_RUNTIME_DIR", "/tmp"), "hypr")
    sig = e.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    if not sig or not os.path.exists(os.path.join(base, sig, ".socket.sock")):
        live = sorted(glob.glob(os.path.join(base, "*", ".socket.sock")), key=os.path.getmtime)
        if live:
            e["HYPRLAND_INSTANCE_SIGNATURE"] = os.path.basename(os.path.dirname(live[-1]))
    return e


def default_run(argv, **kw):
    """subprocess.run with captured text output and the live Hyprland signature."""
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("env", _env())
    return subprocess.run(argv, **kw)


class Hypr:
    def __init__(self, run=None, sleep=time.sleep):
        self.run, self.sleep = run or default_run, sleep

    def sh(self, *argv):
        """Run a command, return its stdout stripped ('' when it prints nothing)."""
        return (self.run(list(argv)).stdout or "").strip()

    def ev(self, lua):
        """Run Lua in Hyprland (Omarchy's Hyprland takes Lua through hyprctl eval)."""
        self.run(["hyprctl", "eval", lua])

    def json(self, *what, default=None):
        out = self.sh("hyprctl", *what, "-j")
        return json.loads(out) if out else default

    def clients(self):
        return self.json("clients", default=[])

    def active_ws(self):
        return (self.json("activeworkspace", default={}) or {}).get("id")

    def monitor(self, name=None):
        """The focused monitor (or the named one) with its scale and its logical size and position.
        width and height are logical (a 2560x1600 panel at scale 1.6 is 1600x1000); pwidth and pheight are physical;
        reserved is the space bars keep, [left, top, right, bottom] as hyprctl reports it ([0, 0, 0, 0] when absent)."""
        mons = self.json("monitors", default=[]) or []
        if not mons:
            raise RuntimeError("hyprctl reported no monitors")
        m = next((m for m in mons if m["name"] == name), None) if name else next((m for m in mons if m.get("focused")), mons[0])
        if m is None:
            raise RuntimeError(f"no monitor named {name}")
        pw, ph = (m["height"], m["width"]) if m.get("transform", 0) % 2 else (m["width"], m["height"])
        s = m["scale"]
        return {"name": m["name"], "x": m["x"], "y": m["y"], "scale": s, "width": round(pw / s), "height": round(ph / s),
                "pwidth": pw, "pheight": ph, "reserved": list(m.get("reserved") or [0, 0, 0, 0])}

    def physical(self, v, name=None):
        """Logical px to physical px, for uinput relative moves (uinput moves in physical pixels)."""
        return round(v * self.monitor(name)["scale"])

    def cursor(self):
        c = self.json("cursorpos", default={}) or {}
        return (c["x"], c["y"]) if "x" in c else None

    def move_cursor(self, x, y):
        self.ev(f"hl.dispatch(hl.dsp.cursor.move({{ x = {round(x)}, y = {round(y)} }}))")

    def focus_ws(self, ws):
        self.ev(f'hl.dispatch(hl.dsp.focus({{ workspace = "{ws}" }}))')

    def close(self, address):
        self.ev(f'local w = hl.get_window("address:{address}"); if w then hl.dispatch(hl.dsp.window.close({{ window = w }})) end')

    def pixel(self, x, y):
        """The (r, g, b) of one screen pixel at logical (x, y), from a 1x1 grim capture."""
        raw = self.run(["grim", "-g", f"{round(x)},{round(y)} 1x1", "-t", "ppm", "-"], text=False).stdout
        if not raw or len(raw) < 3:
            raise RuntimeError(f"grim gave no pixel at {x},{y}")
        return tuple(raw[-3:])

    def layout_mode(self, ws):
        """dwindle, scrolling or floating, as Omarchy reads it (its saved file, else the default, else Hyprland)."""
        return self.sh("omarchy-hyprland-workspace-layout-current", str(ws)) or "dwindle"

    def set_layout_mode(self, ws, mode):
        self.ev(f'o.workspace_mode({{ workspace = "{ws}", mode = "{mode}" }})')


default = Hypr()
sh, ev, clients, active_ws, monitor, cursor = default.sh, default.ev, default.clients, default.active_ws, default.monitor, default.cursor
