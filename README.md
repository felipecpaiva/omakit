# omakit

A small helper library shared by a family of Omarchy plugin projects (omagnet, OmaBar Configurator, omahop, omadials,
omaplace). It holds the parts every project copied into its own `branding/tools` and `tests` folders: real input
through uinput, hyprctl helpers, a screen recorder that makes captioned GIFs, a safe stage for live demos and tests,
brand asset helpers and a privacy scrub.

Python 3 standard library only. The external commands are the ones the projects already use: `hyprctl`, `grim`,
`ffmpeg`, `rsvg-convert`, `magick`, `chromium`, `gio`, `omarchy-shell`. `fontTools` is needed only for outlined
lettering.

What stays in each project: its scenes, mark geometry, colours, captions and test lists. omakit has no project data.

## Install

Clone it next to the plugin repos, so a project finds it as the sibling `../omakit`:

```sh
git clone <omakit repo url> omakit
```

A project script adds it to `sys.path`, from `OMAKIT_PATH` when set, else from the sibling checkout:

```python
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # the project repo
sys.path.insert(0, os.environ.get("OMAKIT_PATH") or os.path.join(os.path.dirname(ROOT), "omakit"))
from omakit.stage import Stage
```

Run the tests with `python3 -m unittest` from the omakit folder. They never touch the live desktop: every command
goes through an injected fake runner, and `subprocess.run` is patched to fail if a real one slips through.

## Modules

**`omakit.uinput`**: a virtual keyboard and mouse made through `/dev/uinput`, so Hyprland sees real input (wtype's
modifiers do not trigger binds). Needs write access to `/dev/uinput`.

```python
with Keyboard() as kb: kb.tap("ctrl+alt+left"); kb.down("alt"); kb.up("alt")
with Mouse() as m: m.press(); m.move(-3000, 0); m.release(); m.click("right"); m.wheel(-3)
```

`KEYS` covers letters, digits, F1 to F12, arrows, modifiers and common punctuation. Mouse moves are in physical
pixels: convert logical ones with `Hypr.physical`.

**`omakit.hypr`**: `Hypr(run=None, sleep=time.sleep)` with `sh(*argv)`, `ev(lua)` (hyprctl eval),
`json(*what)`, `clients()`, `active_ws()`, `monitor(name=None)` (scale, logical `width` and `height`, physical
`pwidth` and `pheight`, `reserved` bar space), `physical(v)`, `cursor()`, `move_cursor(x, y)`, `focus_ws(ws)`, `close(address)`,
`layout_mode(ws)` and `set_layout_mode(ws, mode)`. The default runner picks a live `HYPRLAND_INSTANCE_SIGNATURE` when
the shell carries a stale one. Module level `sh`, `ev`, `clients`, `active_ws`, `monitor` and `cursor` use a shared
default instance.

**`omakit.record`**: `Recorder(region, scale=1, cursor=False, quality=88, hypr=None)` is a context manager that runs
grim in a loop. `region` is `(x, y, w, h)` or `"x,y wxh"` in logical pixels (grim's layout coordinates). `scale=1`
gives frames at the logical size; `scale="native"` uses the monitor scale for full resolution frames (needed when a
gifkit `compose` crops in physical pixels).
`look(region, scale=1)` switches region and scale together mid recording, for a zoom onto one part; keep the
frame size (half the region at scale 2), or ffmpeg gets frames of two sizes.

```python
with Recorder((0, 36, 1280, 764)) as r:
    r.caption("Hold Alt"); ...        # r.mark is the same call
    r.finish("switch", out_dir="branding/demo", width=960, fontsize=30)   # extra keywords go to gifkit.build
```

**`omakit.gifkit`**: `build(frames, total, marks, out_dir, name, width=960, fps=12, mp4_width=1280, fontsize=38,
compose="", font=None, color="#e8e6ff", box="#16181dcc", y="h-90", mp4=True)` writes `name.gif` and `name.mp4`.
`frames` is `[(seconds, path)]`, `marks` is `[(seconds, caption)]` (an empty caption clears it). Frames are resampled
at a fixed rate, so a slow capture keeps real timing. `compose` is an ffmpeg filter graph applied before the captions.
The default font is JetBrains Mono Bold as `fc-match` finds it, with the usual Arch path as a fallback.

**`omakit.stage`**: `Stage(spare=8, dnd=True, restore_files=(), cursor=True, countdown=0, mode=None)` stages a live
demo or test on a spare workspace.

```python
with Stage(spare=8, mode="floating", restore_files=["~/.config/myplugin/config.json"], countdown=10):
    ...  # open demo windows on workspace 8, record
```

On entry it refuses a spare workspace that has any window, then records the workspace you are on, the spare's
layout mode and Omarchy's saved layout file for it (`workspace-layouts/<n>.lua`), Do Not Disturb, the listed files
and the pointer. It turns Do Not Disturb on with `omarchy-shell notifications setDnd on`, focuses the spare and sets
`mode` when given. On exit, also after an error, it closes every window left on the spare (it was empty, so they are
all yours), focuses the origin workspace, puts back the layout mode, the layout file (or moves it to the trash with
`gio trash` when the run created it), the listed files (their bytes, or the trash when they did not exist), Do Not
Disturb and the pointer, and prints one `restored:` line. Each step runs on its own, and a failed step says FAILED in
that line.

`forget_headless_blocks()` removes the virtual monitor entries from Omarchy's `monitor-workspaces` state and reloads
Hyprland. Call it only after something created a virtual monitor.

**`omakit.brand`**: `svg(body, w, h)`, `lettering(text, x, baseline, size, fill, font=...)` (outlined glyphs, no
`<text>`), `rect`, `path`, `png(src, out, w, h)` (rsvg-convert), `luminance`, `contrast(a, b)` (WCAG ratio),
`recolor(text, mapping)` (one pass, so swaps do not chain), `shot(html, out, w, h)` (headless Chromium with a throwaway
profile), `verify(expected_files, root, sizes=None)` (files exist, raster sizes, no en or em dash in text files),
the colours `BG`, `WHITE`, `PAPER`, and `FAMILY`, the accents of the family:

| Project | Accent |
|---|---|
| omagnet | `#8b7bff` |
| OmaBar | `#5cdbc0` |
| omahop | `#ffc83d` |
| omadials | `#ff8c78` |
| omaplace | `#5aa9ff` |

**`bin/omakit-scrub [repo-dir]`**: fails when private data is in a file of a git repo (tracked or new). Built in:
home paths, LAN addresses, e-mail addresses (noreply ones are fine), en and em dashes. More patterns, one Perl regex
per line, come from:

- `.scrub-patterns` at the repo root: public patterns of that repo, committed.
- a private file outside every repo: `$OMAKIT_SCRUB_PRIVATE`, else `~/.config/omakit/scrub-private.patterns`. Machine
  names, client names and anything else that must never be public go here and only here.

Use `(?i)` for a pattern that ignores case, and end a line with ` !! <pathspec> ...` to skip paths for that pattern
only. A pattern that does not compile fails the scrub. The output says how many repo and private patterns it checked,
and says so when the private file is missing.

## Privacy rules for recording

Demos are public. Every frame must be safe to publish.

- **Do Not Disturb** is on for the whole recording (`Stage` does it), so no notification lands in a frame.
- **A spare, empty workspace.** `Stage` refuses one that has windows. Your own windows are never on screen.
- **Public demo content only**: the project's own README, docs or release notes, example.com, coloured test windows.
  Never real mail, chats, notification text, window titles of your own apps, or a settings page that shows a home path.
- **Never create virtual monitors** for a demo or a test: Omarchy keeps a workspace block for every monitor it has
  seen. Record the real screen on a spare workspace.
- **Check the frames** before publishing: look through the GIF and run `omakit-scrub` on the repo.
