"""PiPath's camera helper: the same simple code for every kind of camera.

    from pipath_camera import Camera

    cam = Camera()                    # the camera chosen on PiPath's board
    cam.take_photo("me.jpg")          # save a photo (PiPath shows it on the board)
    grid = cam.capture_grid(16, 16)   # a tiny greyscale picture: 16 rows of 16 numbers, 0 = black, 255 = white

Camera kinds (PiPath sets PIPATH_CAMERA, or pass Camera("usb")):
    "sim"     the Simulator: made-up pictures, no camera needed
    "ribbon"  a Raspberry Pi camera on the ribbon (CSI) cable: Picamera2, or the rpicam-still command
    "usb"     a USB webcam (UVC), read straight from Linux (V4L2), with Picamera2 as a fallback

Only the standard library is needed. Picamera2, numpy and Pillow (all part of Raspberry Pi OS
Desktop) are used when they're there.
"""
from __future__ import annotations

import ctypes
import fcntl
import json
import math
import mmap
import os
import random
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

SIM_OBJECTS = ["face", "ball", "box", "cone", "nothing"]


class CameraNotFound(Exception):
    """No camera of the chosen kind could be found or started."""


class CameraBusy(Exception):
    """Another program is already using the camera."""


# ====================================================================== talking to PiPath

def _shim():
    return sys.modules.get("pipath_shim")


def _tell_pipath(path: Path, preview: Path | None, kind: str) -> None:
    shim = _shim()
    if shim is not None:
        shim.send({"t": "photo", "path": str(path.resolve()),
                   "preview": str(preview) if preview else "", "kind": kind})


def _sim_object() -> str:
    shim = _shim()
    if shim is not None:
        return shim.camera_view.get("object", "face")
    return os.environ.get("PIPATH_CAMERA_OBJECT", "face")


# ====================================================================== images without any libraries

def write_png(path: Path, width: int, height: int, rgb: bytes, grey: bool = False) -> None:
    """Save raw RGB (or greyscale) bytes as a PNG file, using only zlib."""
    bpp = 1 if grey else 3
    rows = b"".join(b"\x00" + rgb[y * width * bpp:(y + 1) * width * bpp] for y in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    head = struct.pack(">IIBBBBB", width, height, 8, 0 if grey else 2, 0, 0, 0)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) +
                           chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def _preview_path() -> Path:
    return Path(tempfile.gettempdir()) / f"pipath_preview_{os.getpid()}_{time.monotonic_ns()}.png"


# ---------------------------------------------------------------- the Simulator's pretend world

PALETTE = {"face": (255, 205, 60), "ball": (220, 50, 50), "box": (40, 90, 210), "cone": (200, 100, 0)}


def _inside(obj: str, x: float, y: float, cx: float, cy: float, r: float) -> tuple[int, int, int] | None:
    """Colour at (x, y) if it's part of the object, else None. Coordinates are 0..1."""
    dx, dy = x - cx, y - cy
    if obj in ("face", "ball"):
        d = math.hypot(dx, dy * 1.333)
        if d > r:
            return None
        if obj == "face":
            for ex in (-r * .38, r * .38):                      # eyes
                if math.hypot(dx - ex, (dy + r * .25) * 1.333) < r * .13:
                    return (30, 30, 30)
            if dy > r * .1 and r * .45 < math.hypot(dx, (dy - r * .05) * 1.333) < r * .62:   # smile
                return (150, 40, 40)
        return PALETTE[obj]
    if obj == "box":
        return PALETTE[obj] if abs(dx) < r and abs(dy * 1.333) < r else None
    if obj == "cone":
        h = r * 1.6
        top = cy - h / 2 / 1.333
        if top <= y <= top + h / 1.333:
            half = (y - top) / (h / 1.333) * r * .9
            return PALETTE[obj] if abs(dx) <= half else None
    return None


def sim_scene(obj: str, width: int, height: int, rng: random.Random, samples: int = 1) -> list[tuple[int, int, int]]:
    """Render the pretend camera's view: a background with one object, a little different each time."""
    cx = .5 + rng.uniform(-.05, .05)      # never quite in the same place,
    cy = .5 + rng.uniform(-.05, .05)
    r = .32 * rng.uniform(.92, 1.08)      # the same size,
    light = rng.uniform(.88, 1.05)        # or in the same light: just like a real camera
    bg = (175, 190, 205) if obj != "face" else tuple(rng.choice([(120, 200, 230), (190, 160, 230), (150, 220, 160)]))
    out = []
    step = 1 / samples
    for py in range(height):
        for px in range(width):
            acc = [0, 0, 0]
            for sy in range(samples):
                for sx in range(samples):
                    x = (px + (sx + .5) * step) / width
                    y = (py + (sy + .5) * step) / height
                    c = _inside(obj, x, y, cx, cy, r) if obj != "nothing" else None
                    if c is None:
                        shade = 1 - .25 * y
                        c = (bg[0] * shade, bg[1] * shade, bg[2] * shade)
                    acc[0] += c[0]
                    acc[1] += c[1]
                    acc[2] += c[2]
            n = samples * samples
            noise = rng.uniform(-8, 8)
            out.append(tuple(max(0, min(255, int(v / n * light + noise))) for v in acc))
    return out


def _grey(c) -> int:
    return int(.299 * c[0] + .587 * c[1] + .114 * c[2])


# ====================================================================== USB webcams via V4L2 (Linux)

def _ioc(direction: int, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (ord("V") << 8) | nr


class _Capability(ctypes.Structure):
    _fields_ = [("driver", ctypes.c_char * 16), ("card", ctypes.c_char * 32), ("bus_info", ctypes.c_char * 32),
                ("version", ctypes.c_uint32), ("capabilities", ctypes.c_uint32),
                ("device_caps", ctypes.c_uint32), ("reserved", ctypes.c_uint32 * 3)]


class _PixFormat(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in ("width", "height", "pixelformat", "field", "bytesperline",
                                                "sizeimage", "colorspace", "priv", "flags", "ycbcr_enc",
                                                "quantization", "xfer_func")]


class _FormatUnion(ctypes.Union):
    # the kernel's union also holds structs with pointers, so it's pointer-aligned
    _fields_ = [("pix", _PixFormat), ("raw", ctypes.c_uint8 * 200), ("_align", ctypes.c_void_p)]


class _Format(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("fmt", _FormatUnion)]


class _RequestBuffers(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in ("count", "type", "memory", "capabilities", "reserved")]


class _Timeval(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long)]


class _Timecode(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("flags", ctypes.c_uint32), ("frames", ctypes.c_uint8),
                ("seconds", ctypes.c_uint8), ("minutes", ctypes.c_uint8), ("hours", ctypes.c_uint8),
                ("userbits", ctypes.c_uint8 * 4)]


class _BufferM(ctypes.Union):
    _fields_ = [("offset", ctypes.c_uint32), ("userptr", ctypes.c_ulong), ("planes", ctypes.c_void_p),
                ("fd", ctypes.c_int32)]


class _Buffer(ctypes.Structure):
    _fields_ = [("index", ctypes.c_uint32), ("type", ctypes.c_uint32), ("bytesused", ctypes.c_uint32),
                ("flags", ctypes.c_uint32), ("field", ctypes.c_uint32), ("timestamp", _Timeval),
                ("timecode", _Timecode), ("sequence", ctypes.c_uint32), ("memory", ctypes.c_uint32),
                ("m", _BufferM), ("length", ctypes.c_uint32), ("reserved2", ctypes.c_uint32),
                ("request_fd", ctypes.c_int32)]


VIDIOC_QUERYCAP = _ioc(2, 0, ctypes.sizeof(_Capability))
VIDIOC_S_FMT = _ioc(3, 5, ctypes.sizeof(_Format))
VIDIOC_REQBUFS = _ioc(3, 8, ctypes.sizeof(_RequestBuffers))
VIDIOC_QUERYBUF = _ioc(3, 9, ctypes.sizeof(_Buffer))
VIDIOC_QBUF = _ioc(3, 15, ctypes.sizeof(_Buffer))
VIDIOC_DQBUF = _ioc(3, 17, ctypes.sizeof(_Buffer))
VIDIOC_STREAMON = _ioc(1, 18, ctypes.sizeof(ctypes.c_int))
VIDIOC_STREAMOFF = _ioc(1, 19, ctypes.sizeof(ctypes.c_int))
CAPTURE, MMAP = 1, 1
CAP_VIDEO_CAPTURE, CAP_DEVICE_CAPS = 0x1, 0x80000000


def fourcc(s: str) -> int:
    return ord(s[0]) | ord(s[1]) << 8 | ord(s[2]) << 16 | ord(s[3]) << 24


MJPG, YUYV = fourcc("MJPG"), fourcc("YUYV")


def find_usb_cameras() -> list[str]:
    """/dev/videoN capture devices that use the UVC (USB webcam) driver."""
    found = []
    base = Path("/sys/class/video4linux")
    for node in sorted(base.glob("video*"), key=lambda p: int(p.name[5:]) if p.name[5:].isdigit() else 99):
        try:
            driver = os.path.basename(os.path.realpath(node / "device" / "driver"))
        except OSError:
            continue
        if driver != "uvcvideo":
            continue
        dev = f"/dev/{node.name}"
        try:
            fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
        except OSError:
            continue
        try:
            cap = _Capability()
            fcntl.ioctl(fd, VIDIOC_QUERYCAP, cap)
            caps = cap.device_caps if cap.capabilities & CAP_DEVICE_CAPS else cap.capabilities
            if caps & CAP_VIDEO_CAPTURE:
                found.append(dev)
        except OSError:
            pass
        finally:
            os.close(fd)
    return found


def v4l2_grab(device: str, width: int, height: int, pixfmt: int, warmup: int = 8) -> tuple[bytes, int, int, int, int]:
    """Grab one frame. Returns (data, width, height, bytes_per_line, pixel_format) as the camera gave it."""
    try:
        fd = os.open(device, os.O_RDWR)
    except PermissionError as e:
        raise CameraNotFound(f"No permission to use {device}. Ask your teacher to add you to the 'video' group.") from e
    except OSError as e:
        raise CameraNotFound(f"Couldn't open {device}: {e.strerror}") from e
    maps, streaming = [], False
    try:
        f = _Format()
        f.type = CAPTURE
        f.fmt.pix.width, f.fmt.pix.height, f.fmt.pix.pixelformat = width, height, pixfmt
        try:
            fcntl.ioctl(fd, VIDIOC_S_FMT, f)
        except OSError as e:
            if e.errno == 16:
                raise CameraBusy("Another program is using the USB camera. Close it and try again.") from e
            raise
        req = _RequestBuffers(count=3, type=CAPTURE, memory=MMAP)
        fcntl.ioctl(fd, VIDIOC_REQBUFS, req)
        for i in range(req.count):
            b = _Buffer(index=i, type=CAPTURE, memory=MMAP)
            fcntl.ioctl(fd, VIDIOC_QUERYBUF, b)
            maps.append(mmap.mmap(fd, b.length, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE,
                                  offset=b.m.offset))
            fcntl.ioctl(fd, VIDIOC_QBUF, b)
        fcntl.ioctl(fd, VIDIOC_STREAMON, ctypes.c_int(CAPTURE))
        streaming = True
        frame = b""
        for _ in range(warmup + 1):          # the first frames are dark while the camera adjusts
            if not select.select([fd], [], [], 5)[0]:
                raise CameraNotFound("The USB camera didn't send a picture. Unplug it, plug it back in, and try again.")
            b = _Buffer(type=CAPTURE, memory=MMAP)
            fcntl.ioctl(fd, VIDIOC_DQBUF, b)
            frame = bytes(maps[b.index][:b.bytesused])
            fcntl.ioctl(fd, VIDIOC_QBUF, b)
        pix = f.fmt.pix
        return frame, pix.width, pix.height, pix.bytesperline or pix.width * 2, pix.pixelformat
    finally:
        if streaming:
            try:
                fcntl.ioctl(fd, VIDIOC_STREAMOFF, ctypes.c_int(CAPTURE))
            except OSError:
                pass
        for m in maps:
            m.close()
        os.close(fd)


# Standard JPEG Huffman tables (JPEG spec, Annex K.3). Many webcams leave them out of MJPEG frames.
_DC_BITS = ([0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0], [0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0])
_AC_LUM_BITS = [0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 0x7d]
_AC_LUM_VALS = bytes.fromhex(
    "01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a"
    "3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a929394"
    "95969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8"
    "e9eaf1f2f3f4f5f6f7f8f9fa")
_AC_CHR_BITS = [0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 0x77]
_AC_CHR_VALS = bytes.fromhex(
    "000102031104052131061241510761711322328108144291a1b1c109233352f0156272d10a162434e125f11718191a2627"
    "28292a35363738393a434445464748494a535455565758595a636465666768696a737475767778797a82838485868788898a"
    "92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae2e3e4e5e6"
    "e7e8e9eaf2f3f4f5f6f7f8f9fa")


def _dht_segment() -> bytes:
    tables = [(0x00, _DC_BITS[0], bytes(range(12))), (0x01, _DC_BITS[1], bytes(range(12))),
              (0x10, _AC_LUM_BITS, _AC_LUM_VALS), (0x11, _AC_CHR_BITS, _AC_CHR_VALS)]
    body = b"".join(bytes([tc]) + bytes(bits) + vals for tc, bits, vals in tables)
    return b"\xff\xc4" + struct.pack(">H", len(body) + 2) + body


def complete_mjpeg(frame: bytes) -> bytes:
    """Make an MJPEG frame a normal JPEG file by adding the standard Huffman tables if they're missing."""
    if not frame.startswith(b"\xff\xd8"):
        raise CameraNotFound("The USB camera sent a picture PiPath can't read.")
    i = 2
    while i + 4 <= len(frame) and frame[i] == 0xFF:
        marker = frame[i + 1]
        if marker == 0xC4:
            return frame                               # it already has tables
        if marker == 0xDA:                             # start of the picture data: tables must come before
            break
        i += 2 + struct.unpack(">H", frame[i + 2:i + 4])[0]
    return frame[:i] + _dht_segment() + frame[i:]


# ====================================================================== the Camera

class Camera:
    def __init__(self, kind: str | None = None):
        self.kind = (kind or os.environ.get("PIPATH_CAMERA") or self._guess()).lower()
        if self.kind not in ("sim", "ribbon", "usb"):
            raise CameraNotFound(f"'{self.kind}' isn't a camera type. Use 'sim', 'ribbon' or 'usb'.")
        self._rng = random.Random()
        self._picam = None
        self._usb = None
        if self.kind == "usb":
            cams = find_usb_cameras()
            if cams:
                self._usb = cams[0]
            else:
                self._picam = self._start_picamera2(usb=True)
                if self._picam is None:
                    raise CameraNotFound("No USB camera found. Check it's plugged in and try again. "
                                     "No camera? Switch the camera panel on the board to Simulated.")
        elif self.kind == "ribbon":
            self._picam = self._start_picamera2(usb=False)
            if self._picam is None and not (shutil.which("rpicam-still") or shutil.which("libcamera-still")):
                raise CameraNotFound("No ribbon camera found. Ask your teacher to check the ribbon cable "
                                     "(blue side facing the right way), then try again.")

    @staticmethod
    def _guess() -> str:
        if find_usb_cameras():
            return "usb"
        try:
            if "Raspberry Pi" in Path("/proc/device-tree/model").read_text(errors="ignore"):
                return "ribbon"
        except OSError:
            pass
        return "sim"

    # ---------------------------------------------------------------- Picamera2
    def _start_picamera2(self, usb: bool):
        try:
            from picamera2 import Picamera2
        except ImportError:
            return None
        try:
            infos = Picamera2.global_camera_info()
            index = next((i for i, c in enumerate(infos) if ("usb" in str(c.get("Id", "")).lower()) == usb), None)
            if index is None:
                return None
            cam = Picamera2(index)
            config = cam.create_still_configuration(main={"size": (1280, 720), "format": "RGB888"},
                                                    lores=None if usb else {"size": (320, 240)})
            cam.configure(config)
            cam.start()
            time.sleep(1.5)       # let the camera adjust to the light
            return cam
        except RuntimeError as e:
            if "busy" in str(e).lower():
                raise CameraBusy("Another program is using the camera. Close it and try again.") from e
            return None
        except Exception:
            return None

    def _picam_array(self):
        arr = self._picam.capture_array("main")
        return arr[:, :, :3] if arr.ndim == 3 else arr

    # ---------------------------------------------------------------- public
    def take_photo(self, file_name: str = "photo.jpg") -> str:
        """Save a photo and return the name it was saved as."""
        path = Path(file_name)
        if path.parent != Path("."):
            path.parent.mkdir(parents=True, exist_ok=True)
        preview = _preview_path()
        if self.kind == "sim":
            path = self._sim_photo(path, preview)
        elif self._usb:
            frame, *_ = v4l2_grab(self._usb, 1280, 720, MJPG)
            path.write_bytes(complete_mjpeg(frame))
            preview = self._preview_from_file(path, preview)
        elif self._picam is not None:
            self._picam.capture_file(str(path))
            preview = self._preview_from_file(path, preview)
        else:
            cmd = shutil.which("rpicam-still") or shutil.which("libcamera-still")
            r = subprocess.run([cmd, "-n", "-t", "1500", "--width", "1280", "--height", "720", "-o", str(path)],
                               capture_output=True, text=True)
            if r.returncode != 0 or not path.exists():
                raise CameraNotFound("The ribbon camera didn't take a photo. Check the cable and try again.")
            preview = self._preview_from_file(path, preview)
        _tell_pipath(path, preview, self.kind)
        return str(path)

    def capture_grid(self, rows: int = 16, cols: int = 16) -> list[list[int]]:
        """A tiny greyscale picture: rows lists of cols numbers from 0 (black) to 255 (white)."""
        if rows < 1 or cols < 1 or rows > 120 or cols > 160:
            raise ValueError("capture_grid needs between 1 and 160 columns, and 1 and 120 rows")
        if self.kind == "sim":
            obj = _sim_object()
            pix = sim_scene(obj, cols, rows, self._rng, samples=3)
            grid = [[_grey(pix[y * cols + x]) for x in range(cols)] for y in range(rows)]
            self._send_grid_preview(grid)
            return grid
        if self._usb:
            data, w, h, bpl, fmt = v4l2_grab(self._usb, 160, 120, YUYV, warmup=6)
            if fmt == YUYV:
                grid = self._sample(lambda x, y: data[y * bpl + x * 2], w, h, rows, cols)
                self._send_grid_preview(grid)
                return grid
            data, *_ = v4l2_grab(self._usb, 320, 240, MJPG, warmup=6)
            return self._grid_from_jpeg(complete_mjpeg(data), rows, cols)
        if self._picam is not None:
            arr = self._picam_array()
            h, w = arr.shape[:2]
            grey = arr.mean(axis=2) if arr.ndim == 3 else arr
            grid = self._sample(lambda x, y: grey[y, x], w, h, rows, cols)
            self._send_grid_preview(grid)
            return grid
        path = Path(tempfile.gettempdir()) / f"pipath_grid_{os.getpid()}.jpg"
        cmd = shutil.which("rpicam-still") or shutil.which("libcamera-still")
        subprocess.run([cmd, "-n", "-t", "800", "--width", "320", "--height", "240", "-o", str(path)],
                       capture_output=True)
        return self._grid_from_jpeg(path.read_bytes(), rows, cols)

    def close(self) -> None:
        if self._picam is not None:
            try:
                self._picam.close()
            except Exception:
                pass
            self._picam = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _sample(get, w: int, h: int, rows: int, cols: int, n: int = 3) -> list[list[int]]:
        """Average a few points in each cell (fast, even in pure Python on a Pi 3B)."""
        grid = []
        for r in range(rows):
            line = []
            for c in range(cols):
                total = 0
                for sy in range(n):
                    for sx in range(n):
                        x = min(w - 1, int((c + (sx + .5) / n) * w / cols))
                        y = min(h - 1, int((r + (sy + .5) / n) * h / rows))
                        total += int(get(x, y))
                line.append(total // (n * n))
            grid.append(line)
        return grid

    def _grid_from_jpeg(self, data: bytes, rows: int, cols: int) -> list[list[int]]:
        try:
            from PIL import Image
        except ImportError as e:
            raise CameraNotFound("This camera needs the Pillow library to make a grid "
                                 "(sudo apt install python3-pil).") from e
        import io
        img = Image.open(io.BytesIO(data)).convert("L").resize((cols, rows))
        px = list(img.tobytes())
        grid = [px[r * cols:(r + 1) * cols] for r in range(rows)]
        self._send_grid_preview(grid)
        return grid

    def _send_grid_preview(self, grid: list[list[int]]) -> None:
        """Show the grid (blown up) on PiPath's board, so students see what the computer sees."""
        if _shim() is None:
            return
        rows, cols = len(grid), len(grid[0])
        scale = max(1, 120 // max(rows, cols))
        data = b"".join(bytes(v for v in row for _ in range(scale)) * scale for row in grid)
        preview = _preview_path()
        write_png(preview, cols * scale, rows * scale, data, grey=True)
        shim = _shim()
        shim.send({"t": "photo", "path": "", "preview": str(preview), "kind": self.kind, "grid": True})

    def _sim_photo(self, path: Path, preview: Path) -> Path:
        obj = _sim_object()
        w, h = 160, 120
        pix = sim_scene(obj, w, h, self._rng)
        rgb = bytes(v for p in pix for v in p)
        write_png(preview, w, h, rgb)
        try:
            from PIL import Image
            Image.frombytes("RGB", (w, h), rgb).resize((w * 2, h * 2)).save(path)
        except ImportError:
            if path.suffix.lower() != ".png":
                path = path.with_suffix(".png")       # no JPEG writer without Pillow
            write_png(path, w, h, rgb)
        return path

    @staticmethod
    def _preview_from_file(path: Path, preview: Path) -> Path | None:
        try:
            from PIL import Image
            img = Image.open(path)
            img.thumbnail((320, 240))
            img.convert("RGB").save(preview)
            return preview
        except Exception:
            return None


if __name__ == "__main__":     # quick check: python3 pipath_camera.py [sim|ribbon|usb]
    cam = Camera(sys.argv[1] if len(sys.argv) > 1 else None)
    print("Camera kind:", cam.kind, "| USB devices:", find_usb_cameras())
    print("Saved", cam.take_photo("pipath_camera_test.jpg"))
    for row in cam.capture_grid(8, 8):
        print(" ".join(f"{v:3d}" for v in row))
    cam.close()
    print(json.dumps({"ok": True}))
