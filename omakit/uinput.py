"""A virtual keyboard and mouse made through /dev/uinput, so Hyprland sees real input events (wtype's modifiers do not
trigger binds). Needs write access to /dev/uinput. Nothing is opened until you enter the context manager.
    with Keyboard() as kb: kb.tap("ctrl+alt+left")
    with Mouse() as m: m.press(); m.move(-3000, 0); m.release()
Key codes are from linux/input-event-codes.h."""
import fcntl, os, string, struct, time

EV_SYN, EV_KEY, EV_REL = 0, 1, 2
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT, UI_DEV_SETUP = 0x40045564, 0x40045565, 0x40045566, 0x405C5503
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
REL_X, REL_Y, REL_WHEEL = 0, 1, 8
BUTTONS = {"left": 0x110, "right": 0x111, "middle": 0x112}

KEYS = {
    "escape": 1, "minus": 12, "equal": 13, "backspace": 14, "tab": 15, "bracketleft": 26, "bracketright": 27, "return": 28,
    "ctrl": 29, "semicolon": 39, "apostrophe": 40, "grave": 41, "shift": 42, "backslash": 43, "comma": 51, "dot": 52,
    "slash": 53, "rshift": 54, "alt": 56, "space": 57, "rctrl": 97, "print": 210, "ralt": 100, "home": 102, "up": 103,
    "pageup": 104, "left": 105, "right": 106, "end": 107, "down": 108, "pagedown": 109, "insert": 110, "delete": 111,
    "super": 125,
}
KEYS.update({str(d): 2 + (d - 1) % 10 for d in range(10)})  # 1..9 are 2..10, 0 is 11
KEYS.update(zip(string.ascii_lowercase, (30, 48, 46, 32, 18, 33, 34, 35, 23, 36, 37, 38, 50, 49, 24, 25, 16, 19, 31, 20, 22, 47, 17, 45, 21, 44)))
KEYS.update({f"f{i}": 58 + i for i in range(1, 11)})
KEYS.update({"f11": 87, "f12": 88})


def codes(combo):
    """'ctrl+alt+left' -> [29, 56, 105]. Raises KeyError for an unknown key."""
    return [KEYS[p] for p in combo.lower().split("+")]


class _Device:
    product = 0x5678

    def __init__(self, name):
        self.name = name

    def _setup(self):
        pass

    def __enter__(self):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        try:
            self._setup()
            name = self.name.encode()[:79].ljust(80, b"\0")
            fcntl.ioctl(self.fd, UI_DEV_SETUP, struct.pack("<HHHH80sI", 0x03, 0x1234, self.product, 1, name, 0))
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except OSError:
            os.close(self.fd)
            raise
        time.sleep(0.8)  # let the compositor pick the new device up
        return self

    def __exit__(self, *exc):
        fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        os.close(self.fd)

    def _emit(self, type_, code, value):
        os.write(self.fd, struct.pack("<qqHHi", 0, 0, type_, code, value))

    def _sync(self):
        self._emit(EV_SYN, 0, 0)


class Keyboard(_Device):
    def __init__(self, name="omakit-keyboard"):
        super().__init__(name)

    def _setup(self):
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
        for code in set(KEYS.values()):
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)

    def tap(self, combo, hold=0.05):
        """Press the modifiers, tap the last key, release in reverse. combo like 'ctrl+alt+left'."""
        cs = codes(combo)
        for c in cs:
            self._emit(EV_KEY, c, 1); self._sync(); time.sleep(0.02)
        time.sleep(hold)
        for c in reversed(cs):
            self._emit(EV_KEY, c, 0); self._sync(); time.sleep(0.02)

    def down(self, key):
        self._emit(EV_KEY, KEYS[key.lower()], 1); self._sync(); time.sleep(0.05)

    def up(self, key):
        self._emit(EV_KEY, KEYS[key.lower()], 0); self._sync(); time.sleep(0.05)


class Mouse(_Device):
    """A relative mouse. Moves are in physical pixels (see Hypr.physical). A huge move (for example -3000) pushes the
    pointer to the screen edge, which reaches edges and corners without depending on pointer acceleration."""
    product = 0x5679

    def __init__(self, name="omakit-mouse"):
        super().__init__(name)

    def _setup(self):
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
        for code in BUTTONS.values():
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_REL)
        for rel in (REL_X, REL_Y, REL_WHEEL):
            fcntl.ioctl(self.fd, UI_SET_RELBIT, rel)

    def press(self, button="left"):
        self._emit(EV_KEY, BUTTONS[button], 1); self._sync(); time.sleep(0.05)

    def release(self, button="left"):
        self._emit(EV_KEY, BUTTONS[button], 0); self._sync(); time.sleep(0.05)

    def click(self, button="left"):
        self.press(button); self.release(button)

    def move(self, dx, dy, steps=20, pause=0.01):
        """Move in small steps, like a hand, so the compositor sees a drag and not a jump."""
        for i in range(1, steps + 1):
            self._emit(EV_REL, REL_X, int(dx * i / steps) - int(dx * (i - 1) / steps))
            self._emit(EV_REL, REL_Y, int(dy * i / steps) - int(dy * (i - 1) / steps))
            self._sync(); time.sleep(pause)

    def wheel(self, clicks, pause=0.05):
        """Scroll: negative clicks scroll down (content moves up), positive scroll up."""
        step = 1 if clicks > 0 else -1
        for _ in range(abs(clicks)):
            self._emit(EV_REL, REL_WHEEL, step); self._sync(); time.sleep(pause)
