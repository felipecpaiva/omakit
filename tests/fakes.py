"""A fake command runner, so tests never reach the live desktop. Also guards subprocess.run while a test runs."""
import json, subprocess, types
from unittest import mock


class FakeRun:
    """Records every argv. Answers hyprctl queries from a small fake desktop state."""

    def __init__(self, clients=(), ws=3, mode="dwindle", dnd="off", cursor=(800, 500), scale=1.6, on=None):
        # saved_mode is what Omarchy reads back (its file or default); a mode set by eval only lands in applied
        self.calls, self.clients, self.ws, self.saved_mode, self.applied, self.dnd = [], list(clients), ws, mode, None, dnd
        self.cursor, self.scale, self.on = cursor, scale, on or {}

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        out = ""
        a = list(argv)
        if a[0] in self.on:
            out = self.on[a[0]](a) or ""
        elif a[:2] == ["hyprctl", "clients"]:
            out = json.dumps(self.clients)
        elif a[:2] == ["hyprctl", "activeworkspace"]:
            out = json.dumps({"id": self.ws})
        elif a[:2] == ["hyprctl", "cursorpos"]:
            out = json.dumps({"x": self.cursor[0], "y": self.cursor[1]})
        elif a[:2] == ["hyprctl", "monitors"]:
            out = json.dumps([{"name": "eDP-1", "x": 0, "y": 0, "width": 2560, "height": 1600, "scale": self.scale,
                               "transform": 0, "focused": True}])
        elif a[:2] == ["hyprctl", "eval"]:
            lua = a[2]
            if "o.workspace_mode" in lua:
                self.applied = lua.split('mode = "')[1].split('"')[0]
            if "window.close" in lua:
                addr = lua.split("address:")[1].split('"')[0]
                self.clients = [c for c in self.clients if c["address"] != addr]
            if "focus({ workspace" in lua:
                self.ws = int(lua.split('workspace = "')[1].split('"')[0])
        elif a[0] == "omarchy-hyprland-workspace-layout-current":
            out = self.saved_mode
        elif a[:3] == ["omarchy-shell", "notifications", "isDnd"]:
            out = self.dnd
        elif a[:3] == ["omarchy-shell", "notifications", "setDnd"]:
            self.dnd = a[3]
        return types.SimpleNamespace(stdout=out, stderr="", returncode=0)

    def evals(self):
        return [c[2] for c in self.calls if c[:2] == ["hyprctl", "eval"]]


def no_subprocess():
    """Patch subprocess.run to fail, so an un-faked command cannot reach the desktop."""
    def refuse(*a, **kw):
        raise AssertionError(f"un-faked command: {a[0] if a else kw}")
    return mock.patch.object(subprocess, "run", refuse)


def put(path, mode, data):
    with open(path, mode) as f:
        f.write(data)


def get(path, mode="r"):
    with open(path, mode) as f:
        return f.read()
