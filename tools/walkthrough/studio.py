"""The walkthrough studio: record PiPath being used, then add the overlay layer.

Two halves:

1. Record (inside a scene script, under Xvfb, with the Python that has Tk + gpiozero):
       studio = Studio(app, out_dir)
       studio.chapter("1 · Getting started"); studio.say("**Mia** makes a profile.")
       studio.click(widget); studio.type(entry, "Mia"); studio.wait(800) ...
       studio.run()
   The real app is driven like a student would use it: the pointer glides (eased, ~0.65 s) to each
   target and pauses before clicking, typing goes one key at a time (85–160 ms). ffmpeg records
   the screen (x11grab, wall-clock timestamps) and every pointer move, click, caption, chapter and
   pause is logged to timeline.json with the same clock.

2. Render (any Python with Pillow; ffmpeg):
       python3 tools/walkthrough/studio.py render OUT_DIR "Title" "Subtitle" "Small line"
   Scales 1600×900 → 1920×1080 and draws the overlay: a white arrow pointer with a teal click
   ripple, Vista-style caption balloons (key words in BNTS purple), a teal chapter pill and
   opening / closing title cards. Writes two videos:
       walkthrough_captions.mp4   everything
       walkthrough_clean.mp4      pointer only; no captions, chapters or title cards; pauses cut to 55 %

Dev tool only (not part of the app), so Pillow is fine here.
"""
from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

SRC_W, SRC_H = 1600, 900          # the screen the app runs on (a laptop)
SCALE = 1.2                       # → 1920 × 1080
OUT_W, OUT_H = int(SRC_W * SCALE), int(SRC_H * SCALE)
FPS = 30
GLIDE_S = 0.65                    # pointer move, eased in and out
PRE_CLICK_S = 0.25                # the little pause before a click
KEY_MS = (85, 160)                # typing speed per key
CLEAN_PAUSE = 0.55                # the clean version keeps this much of each pause

PURPLE = (0x70, 0x49, 0x88)
TEAL_A, TEAL_B = (0x19, 0xC1, 0xCA), (0x0B, 0x9A, 0xA1)


def caption_seconds(text: str) -> float:
    """How long a caption stays up: 0.9 s + 0.33 s a word, at least 2.6 s."""
    return max(2.6, 0.9 + 0.33 * len(text.replace("**", "").split()))


# ====================================================================== 1. recording

class Studio:
    def __init__(self, app, out_dir: Path):
        self.app = app
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.queue: list[tuple] = []
        self.events: list[dict] = []
        self.pointer = [SRC_W * 0.55, SRC_H * 0.6]
        self.caption_until = 0.0
        self.proc = None

    # ---------------------------------------------------------------- the script (queued)
    def chapter(self, text):            self.queue.append(("chapter", text))
    def say(self, text, pos="bottom"):  self.queue.append(("say", text, pos))
    def move(self, target):             self.queue.append(("move", target))
    def click(self, target, action=None):   self.queue.append(("click", target, action))
    def type(self, widget, text):       self.queue.append(("type", widget, text))
    def wait(self, ms):                 self.queue.append(("wait", ms))
    def hold(self):                     self.queue.append(("hold",))    # until the caption has been read
    def do(self, fn):                   self.queue.append(("do", fn))
    def scroll(self, canvas, to):       self.queue.append(("scroll", canvas, to))
    def until(self, test, timeout_ms=20000):  self.queue.append(("until", test, timeout_ms))

    # ---------------------------------------------------------------- helpers
    def log(self, kind, **kw):
        self.events.append({"t": time.time(), "kind": kind, **kw})

    def xy(self, target):
        """A widget (its centre), a callable returning a widget or (x, y), or (x, y)."""
        if callable(target):
            target = target()
        if isinstance(target, tuple):
            return target
        w = target
        return (w.winfo_rootx() - self.app.winfo_rootx() + w.winfo_width() / 2,
                w.winfo_rooty() - self.app.winfo_rooty() + w.winfo_height() / 2)

    def _warp(self, x, y):
        self.pointer = [x, y]
        self.app.event_generate("<Motion>", warp=True, x=int(x), y=int(y))
        self.log("pointer", x=round(x, 1), y=round(y, 1))

    # ---------------------------------------------------------------- running the queue
    def run(self):
        self.app.after(800, self._begin)
        self.app.mainloop()

    def _begin(self):
        self.proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab", "-draw_mouse", "0", "-framerate", str(FPS),
             "-video_size", f"{SRC_W}x{SRC_H}", "-i", os.environ["DISPLAY"], "-copyts",
             "-c:v", "libx264", "-preset", "ultrafast", "-qp", "8", str(self.out / "raw.mkv")],
            stdin=subprocess.PIPE)
        self._warp(*self.pointer)
        self.app.after(1000, self._next)

    def _next(self, delay=0):
        self.app.after(delay, self._step)

    def _step(self):
        if not self.queue:
            self.app.after(600, self._finish)
            return
        item, *args = self.queue.pop(0)
        try:
            getattr(self, "_" + item)(*args)
        except Exception:
            import traceback
            traceback.print_exc()
            self._next(50)

    def _chapter(self, text):
        self.log("chapter", text=text)
        self._next()

    def _say(self, text, pos):
        wait = max(0.0, self.caption_until - time.time())     # let the last caption be read first
        def show():
            self.log("caption", text=text, pos=pos)
            self.caption_until = time.time() + (caption_seconds(text) if text else 0)
            self._next()
        self.app.after(int(wait * 1000), show)

    def _hold(self):
        wait = max(0.0, self.caption_until - time.time())
        self.log("pause", ms=int(wait * 1000))
        self._next(int(wait * 1000))

    def _wait(self, ms):
        self.log("pause", ms=ms)
        self._next(ms)

    def _do(self, fn):
        fn()
        self._next(60)

    def _until(self, test, timeout_ms):
        start = time.time()
        def poll():
            if test() or (time.time() - start) * 1000 > timeout_ms:
                self._next(100)
            else:
                self.app.after(100, poll)
        poll()

    def _glide(self, to, then):
        (x0, y0), (x1, y1) = self.pointer, to
        steps = max(2, int(GLIDE_S * 60 * min(1.0, 0.4 + math.dist((x0, y0), (x1, y1)) / 900)))
        def stepper(k=1):
            f = k / steps
            f = f * f * (3 - 2 * f)                       # ease in and out
            self._warp(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
            if k < steps:
                self.app.after(16, stepper, k + 1)
            else:
                then()
        stepper()

    def _move(self, target):
        self._glide(self.xy(target), lambda: self._next(150))

    def _click(self, target, action):
        w = target() if callable(target) else target
        def press():
            self.log("click", x=self.pointer[0], y=self.pointer[1])
            if action is not None:
                action()
                self._next(250)
            elif hasattr(w, "_press"):                   # a PiPath PButton: press in, then release
                w._press()
                self.app.after(150, lambda: (w._release(), self._next(250)))
            else:
                w.event_generate("<Button-1>")
                self._next(250)
        self._glide(self.xy(w if not isinstance(w, tuple) else w),
                    lambda: self.app.after(int(PRE_CLICK_S * 1000), press))

    def _type(self, widget, text):
        w = widget() if callable(widget) else widget
        def one(k=0):
            if k >= len(text):
                self._next(200)
                return
            w.insert("insert", text[k])
            if hasattr(w, "edit_modified"):              # the code editor: let it highlight and save
                w.event_generate("<<Modified>>")
                w.event_generate("<KeyRelease>")
            self.app.after(random.randint(*KEY_MS), one, k + 1)
        w.focus_set()
        self._glide(self.xy((w.winfo_rootx() - self.app.winfo_rootx() + 40,
                             w.winfo_rooty() - self.app.winfo_rooty() + w.winfo_height() / 2))
                    if not hasattr(w, "edit_modified") else self.pointer, one)

    def _scroll(self, canvas, to):
        cv = canvas() if callable(canvas) else canvas
        target = to() if callable(to) else to
        y0 = cv.yview()[0]
        def stepper(k=1, steps=36):
            f = k / steps
            f = f * f * (3 - 2 * f)
            cv.yview_moveto(y0 + (target - y0) * f)
            if k < steps:
                self.app.after(16, stepper, k + 1)
            else:
                self._next(150)
        stepper()

    def _finish(self):
        self.log("caption", text=None, pos="bottom")
        self.log("end")
        self.proc.communicate(b"q", timeout=120)
        start = float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                      "stream=start_time", "-of", "default=nw=1:nk=1", str(self.out / "raw.mkv")],
                                     capture_output=True, text=True).stdout.strip())
        for e in self.events:
            e["t"] = round(e["t"] - start, 3)              # seconds into the recording
        (self.out / "timeline.json").write_text(json.dumps(self.events, indent=0))
        print(f"recorded {self.events[-1]['t']:.1f} s, {len(self.events)} events")
        self.app.quit_app()


# ====================================================================== 2. rendering

def _fonts():
    from PIL import ImageFont
    base = "/usr/share/fonts/truetype/dejavu/"
    return {"cap": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 26),
            "pill": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 22),
            "h1": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 96),
            "h2": ImageFont.truetype(base + "DejaVuSans.ttf", 40),
            "small": ImageFont.truetype(base + "DejaVuSans.ttf", 24)}


def _rich_lines(text, font, max_w):
    """Split '**key** words' into wrapped lines of (word, purple?) runs."""
    words, purple = [], False
    for i, part in enumerate(text.split("**")):
        purple = i % 2 == 1
        words += [(w, purple) for w in part.split()]
    lines, line, width = [], [], 0
    space = font.getlength(" ")
    for w, p in words:
        wl = font.getlength(w)
        if line and width + space + wl > max_w:
            lines.append(line)
            line, width = [], 0
        line.append((w, p))
        width += (space if len(line) > 1 else 0) + wl
    if line:
        lines.append(line)
    return lines


def caption_balloon(text, fonts):
    """A Vista notification balloon: white → cream, gold border, rounded, soft shadow."""
    from PIL import Image, ImageDraw, ImageFilter
    font = fonts["cap"]
    lines = _rich_lines(text, font, 1400)
    lh = 38
    space = font.getlength(" ")
    widths = [sum(font.getlength(w) for w, _ in ln) + space * (len(ln) - 1) for ln in lines]
    bw, bh = int(max(widths) + 64), int(len(lines) * lh + 34)
    pad = 24
    im = Image.new("RGBA", (bw + pad * 2, bh + pad * 2), (0, 0, 0, 0))
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((pad + 2, pad + 6, pad + bw + 2, pad + bh + 6), 14, fill=(0, 0, 0, 110))
    im = Image.alpha_composite(im, shadow.filter(ImageFilter.GaussianBlur(8)))
    grad = Image.new("RGBA", (bw, bh))
    gd = ImageDraw.Draw(grad)
    for y in range(bh):                               # white at the top → cream at the bottom
        f = y / max(1, bh - 1)
        gd.line((0, y, bw, y), fill=(255, int(255 - 7 * f), int(255 - 34 * f), 250))
    mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw - 1, bh - 1), 14, fill=255)
    im.paste(grad, (pad, pad), mask)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((pad, pad, pad + bw - 1, pad + bh - 1), 14, outline=(0xC9, 0x9A, 0x2E), width=2)
    d.rounded_rectangle((pad + 3, pad + 3, pad + bw - 4, pad + 18), 10, fill=(255, 255, 255, 90))  # top sheen
    y = pad + 17
    for ln, w in zip(lines, widths):
        x = pad + (bw - w) / 2
        for word, purple in ln:
            d.text((x, y), word, font=font, fill=PURPLE if purple else (0x22, 0x22, 0x22))
            x += font.getlength(word) + space
        y += lh
    return im


def chapter_pill(text, fonts):
    from PIL import Image, ImageDraw
    font = fonts["pill"]
    w, h = int(font.getlength(text) + 44), 44
    grad = Image.new("RGBA", (w, h))
    gd = ImageDraw.Draw(grad)
    for x in range(w):
        f = x / max(1, w - 1)
        gd.line((x, 0, x, h), fill=tuple(int(a + (b - a) * f) for a, b in zip(TEAL_A, TEAL_B)) + (245,))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=255)
    im = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((3, 5, w + 3, h + 5), h // 2, fill=(0, 0, 0, 60))
    im.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, outline=(255, 255, 255, 140), width=1)
    d.text((22, 9), text, font=font, fill="white")
    return im


def title_card(heading, sub, small, fonts):
    """Teal (centre) → purple (edges) radial gradient, big white heading."""
    from PIL import Image, ImageDraw
    g = Image.radial_gradient("L").resize((OUT_W * 2, OUT_W * 2)).crop(
        (OUT_W - OUT_W // 2, OUT_W - OUT_H // 2, OUT_W + OUT_W // 2, OUT_W + OUT_H // 2))
    g = g.point(lambda v: min(255, int(v * 1.35)))
    card = Image.composite(Image.new("RGB", (OUT_W, OUT_H), (0x5A, 0x34, 0x74)),
                           Image.new("RGB", (OUT_W, OUT_H), TEAL_A), g)
    d = ImageDraw.Draw(card)
    for text, font, y, fill in ((heading, fonts["h1"], OUT_H * 0.36, "white"),
                                (sub, fonts["h2"], OUT_H * 0.52, "white"),
                                (small, fonts["small"], OUT_H * 0.62, (225, 240, 245))):
        d.text(((OUT_W - font.getlength(text)) / 2, y), text, font=font, fill=fill)
    return card


def pointer_image():
    """A white arrow with a black outline (classic Windows), drawn at 1.2×."""
    from PIL import Image, ImageDraw
    pts = [(0, 0), (0, 21), (5, 16), (9, 25), (12, 24), (8, 15), (15, 15)]
    s = SCALE * 1.15
    im = Image.new("RGBA", (34, 36), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    poly = [(2 + x * s, 2 + y * s) for x, y in pts]
    d.polygon([(x + 1.5, y + 2) for x, y in poly], fill=(0, 0, 0, 70))          # soft shadow
    d.polygon(poly, fill="white", outline="black")
    d.line(poly + [poly[0]], fill="black", width=2)
    return im


def render(out_dir: Path, heading: str, sub: str, small: str):
    from PIL import Image, ImageDraw
    out_dir = Path(out_dir)
    events = json.loads((out_dir / "timeline.json").read_text())
    fonts = _fonts()
    arrow = pointer_image()
    end_t = next(e["t"] for e in events if e["kind"] == "end")

    # ---- what's on screen at time t
    pointer = [(e["t"], e["x"] * SCALE, e["y"] * SCALE) for e in events if e["kind"] == "pointer"]
    clicks = [(e["t"], e["x"] * SCALE, e["y"] * SCALE) for e in events if e["kind"] == "click"]
    caps = [(e["t"], e["text"], e.get("pos", "bottom")) for e in events if e["kind"] == "caption"]
    chaps = [(e["t"], e["text"]) for e in events if e["kind"] == "chapter"]
    pauses = [(e["t"], e["t"] + e["ms"] / 1000) for e in events if e["kind"] == "pause" and e["ms"] > 0]
    cut = [(a + (b - a) * CLEAN_PAUSE, b) for a, b in pauses]      # the clean version drops these

    def latest(seq, t, default=None):
        val = default
        for item in seq:
            if item[0] <= t:
                val = item
            else:
                break
        return val

    cap_cache, pill_cache = {}, {}

    def overlay(frame, t, full):
        p = latest(pointer, t)
        if p:
            for ct, cx, cy in clicks:                    # teal ripple ring, 0.55 s
                age = t - ct
                if 0 <= age < 0.55:
                    r = 10 + 30 * age / 0.55
                    a = int(230 * (1 - age / 0.55))
                    ring = Image.new("RGBA", frame.size, (0, 0, 0, 0))
                    ImageDraw.Draw(ring).ellipse((cx - r, cy - r, cx + r, cy + r), outline=TEAL_A + (a,), width=5)
                    frame.alpha_composite(ring)
            frame.alpha_composite(arrow, (int(p[1]) - 2, int(p[2]) - 2))
        if not full:
            return frame
        ch = latest(chaps, t)
        if ch and ch[1]:
            if ch[1] not in pill_cache:
                pill_cache[ch[1]] = chapter_pill(ch[1], fonts)
            pill = pill_cache[ch[1]]
            frame.alpha_composite(pill, (OUT_W - pill.width - 26, 22))
        c = latest(caps, t)
        if c and c[1]:
            if c[1] not in cap_cache:
                cap_cache[c[1]] = caption_balloon(c[1], fonts)
            b = cap_cache[c[1]]
            fade = min(1.0, (t - c[0]) / 0.18)
            if fade < 1:
                b = b.copy()
                b.putalpha(b.getchannel("A").point(lambda v: int(v * fade)))
            y = 70 if c[2] == "top" else OUT_H - b.height - 26
            frame.alpha_composite(b, ((OUT_W - b.width) // 2, y))
        return frame

    def encoder(name):
        return subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}",
             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(out_dir / name)], stdin=subprocess.PIPE)

    full_enc, clean_enc = encoder("walkthrough_captions.mp4"), encoder("walkthrough_clean.mp4")
    card_open = title_card(heading, sub, small, fonts)
    card_close = title_card(heading, "Thanks for watching", small, fonts)

    decoder = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", str(out_dir / "raw.mkv"), "-vf",
         f"fps={FPS},scale={OUT_W}:{OUT_H}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    size = OUT_W * OUT_H * 3
    first = None
    k = 0
    while True:
        raw = decoder.stdout.read(size)
        if len(raw) < size:
            break
        t = k / FPS
        k += 1
        if t > end_t:
            break
        frame = Image.frombytes("RGB", (OUT_W, OUT_H), raw).convert("RGBA")
        if first is None:                                # the opening card: 3 s, then a 0.5 s cross-fade
            first = frame.convert("RGB")
            for i in range(int(3.5 * FPS)):
                f = max(0.0, (i - 3.0 * FPS) / (0.5 * FPS))
                full_enc.stdin.write(Image.blend(card_open, first, f).tobytes())
        full_enc.stdin.write(overlay(frame.copy(), t, True).convert("RGB").tobytes())
        if not any(a <= t < b for a, b in cut):
            clean_enc.stdin.write(overlay(frame, t, False).convert("RGB").tobytes())
        last = frame.convert("RGB")
    for i in range(int(4 * FPS)):                        # the closing card: 0.5 s cross-fade, then 3.5 s
        f = min(1.0, i / (0.5 * FPS))
        full_enc.stdin.write(Image.blend(last, card_close, f).tobytes())
    for enc in (full_enc, clean_enc):
        enc.stdin.close()
        enc.wait()
    decoder.stdout.close()                               # we may stop reading early (at "end"): don't wait on it
    decoder.kill()
    decoder.wait()
    for name in ("walkthrough_captions.mp4", "walkthrough_clean.mp4"):
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                            "default=nw=1:nk=1", str(out_dir / name)], capture_output=True, text=True).stdout
        print(f"{name}: {float(d):.1f} s")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "render":
        render(Path(sys.argv[2]), *(sys.argv[3:6] + ["PiPath", "A walkthrough", ""])[:3])
    else:
        print(__doc__)
