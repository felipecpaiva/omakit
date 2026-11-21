"""Turn captured frames into a captioned GIF and MP4.
frames = [(seconds, path)], marks = [(seconds, caption)] (an empty caption clears it), total = length in seconds.
Frames are resampled at a fixed rate, so a slow capture does not change the timing."""
import os, shutil, subprocess, tempfile

FALLBACK_FONT = "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Bold.ttf"


def default_font(run=subprocess.run):
    """JetBrains Mono Bold as fontconfig finds it, else the path Arch's Nerd Font package uses."""
    try:
        r = run(["fc-match", "-f", "%{file}", "JetBrainsMono Nerd Font:style=Bold"], capture_output=True, text=True)
        path = (r.stdout or "").strip()
        if path and os.path.exists(path):
            return path
    except OSError:
        pass
    return FALLBACK_FONT


def _esc(t):  # drawtext's own escapes
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")


def captions(marks, total, font, fontsize=38, color="#e8e6ff", box="#16181dcc", y="h-90"):
    """The drawtext filters for the marks, joined with commas ('' when no caption has text)."""
    ends = [m[0] for m in marks[1:]] + [total]
    return ",".join(
        f"drawtext=fontfile={_esc(font)}:text='{_esc(c)}':fontsize={fontsize}:fontcolor={color}:box=1:boxcolor={box}"
        f":boxborderw=18:x=(w-text_w)/2:y={y}:enable='between(t,{a:.2f},{e:.2f})'"
        for (a, c), e in zip(marks, ends) if c)


def _check(r, argv):
    # Through a capturing runner a failed ffmpeg would raise with no message: show its stderr first.
    if getattr(r, "returncode", 0):
        raise RuntimeError(f"{argv[0]} failed: {(getattr(r, 'stderr', '') or '').strip()}")


def build(frames, total, marks, out_dir, name, width=960, fps=12, mp4_width=1280, fontsize=38, compose="", font=None,
          color="#e8e6ff", box="#16181dcc", y="h-90", mp4=True, run=subprocess.run):
    """compose: an ffmpeg filter graph from [0:v] to one unlabeled stream, applied before the captions (for example a
    crop, or a zoomed strip stacked over a panel). Returns the paths written."""
    if not frames:
        raise ValueError("no frames to build from")
    os.makedirs(out_dir, exist_ok=True)
    font = font or default_font(run)
    seq = tempfile.mkdtemp(prefix="omakit-seq-")
    try:
        n, j = max(1, int(total * fps)), 0
        for k in range(n):  # the latest captured frame at or before each tick
            while j + 1 < len(frames) and frames[j + 1][0] <= k / fps:
                j += 1
            os.symlink(os.path.abspath(frames[j][1]), os.path.join(seq, f"s{k:05d}.jpg"))
        draw = captions(marks, total, font, fontsize, color, box, y)
        pre = (compose + "," if compose else "") + (draw + "," if draw else "")
        src = ["-framerate", str(fps), "-i", os.path.join(seq, "s%05d.jpg")]
        out = [os.path.join(out_dir, name + ".gif")]
        gif = f"{pre}scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4"
        argv = ["ffmpeg", "-y", "-loglevel", "error", *src, "-filter_complex", gif, "-loop", "0", out[0]]
        _check(run(argv), argv)
        if mp4:
            out.append(os.path.join(out_dir, name + ".mp4"))
            argv = ["ffmpeg", "-y", "-loglevel", "error", *src, "-vf", f"{pre}scale={mp4_width}:-2", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "24", "-r", "30", out[1]]
            _check(run(argv), argv)
        return out
    finally:
        shutil.rmtree(seq, ignore_errors=True)
