"""Generic brand helpers: SVG building blocks, outlined lettering, PNG export, WCAG contrast, recolouring, an HTML
screenshot and a deliverables check. Each project keeps its own marks, accents and layouts.
fontTools is needed only for lettering() and is imported on first use."""
import os, re, shutil, subprocess, tempfile
from pathlib import Path

from .gifkit import FALLBACK_FONT

BG, WHITE, PAPER = "#16181d", "#f4f5f7", "#f4f3f0"
# Accents already used by the family; show them on a board so a new accent can be judged against them.
FAMILY = [("omagnet", "#8b7bff"), ("OmaBar", "#5cdbc0"), ("omahop", "#ffc83d"), ("omadials", "#ff8c78"), ("omaplace", "#5aa9ff")]

_fonts = {}


def _font(path):
    if path not in _fonts:
        from fontTools.ttLib import TTFont
        f = TTFont(path)
        _fonts[path] = (f, f.getGlyphSet(), f.getBestCmap())
    return _fonts[path]


def svg(body, w, h, view=None):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{view or f"0 0 {w} {h}"}">{body}</svg>\n'


def lettering(text, x, baseline, size, fill, font=FALLBACK_FONT):
    """Text as outlined paths (no <text>, so it renders the same everywhere)."""
    from fontTools.pens.svgPathPen import SVGPathPen
    f, glyphs, cmap = _font(str(font))
    scale = size / f["head"].unitsPerEm
    paths = []
    for ch in text:
        g = glyphs[cmap[ord(ch)]]
        pen = SVGPathPen(glyphs)
        g.draw(pen)
        paths.append(f'<path d="{pen.getCommands()}" transform="translate({x:g} {baseline:g}) scale({scale:g} {-scale:g})"/>')
        x += g.width * scale
    return f'<g fill="{fill}">' + "".join(paths) + "</g>"


def rect(x, y, w, h, r, c):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{c}"/>'


def path(d, c, width):
    return f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'


def png(src, out, w=None, h=None, run=subprocess.run):
    run(["rsvg-convert"] + (["-w", str(w)] if w else []) + (["-h", str(h)] if h else []) + ["-o", str(out), str(src)], check=True)


def luminance(h):
    rgb = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(c * w for c, w in zip(lin, (.2126, .7152, .0722)))


def contrast(a, b):
    """WCAG contrast ratio of two #rrggbb colours (1 to 21)."""
    x, y = sorted([luminance(a), luminance(b)])
    return (y + .05) / (x + .05)


def recolor(text, mapping):
    """Swap colours in one pass ({'#16181d': '#0f1b24', ...}, case-insensitive), so a new colour that equals another
    old one is not swapped twice."""
    low = {k.lower(): v for k, v in mapping.items()}
    if not low:
        return text
    return re.sub("|".join(re.escape(k) for k in sorted(low, key=len, reverse=True)), lambda m: low[m.group(0).lower()],
                  text, flags=re.I)


def shot(html, out, w, h, run=subprocess.run):
    """Screenshot an HTML string with headless Chromium at exactly w by h, using a throwaway profile."""
    tmp = tempfile.mkdtemp(prefix="omakit-shot-")
    try:
        page = os.path.join(tmp, "page.html")
        with open(page, "w") as f:
            f.write(html)
        run(["chromium", "--headless", "--disable-gpu", "--no-sandbox", "--disable-crash-reporter", "--hide-scrollbars",
             "--force-device-scale-factor=1", f"--user-data-dir={tmp}/profile", f"--window-size={w},{h}",
             f"--screenshot={os.path.abspath(out)}", "file://" + page], check=True, capture_output=True, timeout=90)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


DASHES = (chr(0x2013), chr(0x2014))
TEXT = (".py", ".md", ".html", ".svg", ".json", ".txt", ".sh", ".lua", ".qml", ".toml")


def verify(expected_files, root=".", sizes=None, dash_scan=True, run=subprocess.run):
    """Check deliverables: every expected file exists, raster sizes match (sizes = {'icon-16.png': '16x16'}, checked
    with magick identify) and no text file under root has an en or em dash. Raises AssertionError on the first
    problem; returns a small result dict."""
    root = Path(root)
    for name in expected_files:
        assert (root / name).is_file(), f"missing {name}"
    for name, want in (sizes or {}).items():
        got = run(["magick", "identify", "-format", "%wx%h", str(root / name)], capture_output=True, text=True, check=True).stdout
        assert got == want, f"{name} is {got}, expected {want}"
    scanned = 0
    if dash_scan:
        for p in root.rglob("*"):
            if p.is_file() and p.suffix in TEXT and ".git" not in p.parts:
                s = p.read_text(errors="replace")
                assert not any(d in s for d in DASHES), f"en or em dash in {p}"
                scanned += 1
    return {"status": "passed", "files": len(expected_files), "sizes": len(sizes or {}), "text_files_scanned": scanned}
