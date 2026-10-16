"""pipath_camera: V4L2 structures, MJPEG fixing, PNG writing, the Simulator, and friendly errors."""
import ctypes
import io
import random
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipath" / "student_lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipath_camera as pc  # noqa: E402
from pipath.hints import HintEngine, parse_traceback  # noqa: E402
from shimrun import run_shim  # noqa: E402

try:
    from PIL import Image
except ImportError:
    Image = None


class TestV4L2Layout(unittest.TestCase):
    """The ctypes structures must match the kernel's, or the ioctl numbers will be wrong."""

    def test_ioctl_numbers(self):
        ptr64 = ctypes.sizeof(ctypes.c_void_p) == 8
        expected = {
            "VIDIOC_QUERYCAP": 0x80685600,
            "VIDIOC_S_FMT": 0xc0d05605 if ptr64 else 0xc0cc5605,
            "VIDIOC_REQBUFS": 0xc0145608,
            "VIDIOC_QUERYBUF": 0xc0585609 if ptr64 else 0xc0445609,
            "VIDIOC_QBUF": 0xc058560f if ptr64 else 0xc044560f,
            "VIDIOC_DQBUF": 0xc0585611 if ptr64 else 0xc0445611,
            "VIDIOC_STREAMON": 0x40045612,
            "VIDIOC_STREAMOFF": 0x40045613,
        }
        for name, value in expected.items():
            self.assertEqual(getattr(pc, name), value, name)

    def test_fourcc(self):
        self.assertEqual(pc.MJPG, 0x47504A4D)
        self.assertEqual(pc.YUYV, 0x56595559)


class TestImages(unittest.TestCase):
    def test_huffman_tables_are_complete(self):
        self.assertEqual(sum(pc._AC_LUM_BITS), len(pc._AC_LUM_VALS))
        self.assertEqual(sum(pc._AC_CHR_BITS), len(pc._AC_CHR_VALS))

    @unittest.skipIf(Image is None, "Pillow is not installed")
    def test_mjpeg_without_tables_becomes_a_normal_jpeg(self):
        img = Image.new("RGB", (48, 32))
        img.putdata([(random.randrange(256), random.randrange(256), random.randrange(256)) for _ in range(48 * 32)])
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85, optimize=False)
        data = buf.getvalue()
        out, i = bytearray(data[:2]), 2              # strip the DHT segments, like many webcams do
        while data[i] == 0xFF and data[i + 1] != 0xDA:
            n = struct.unpack(">H", data[i + 2:i + 4])[0]
            if data[i + 1] != 0xC4:
                out += data[i:i + 2 + n]
            i += 2 + n
        out += data[i:]
        fixed = pc.complete_mjpeg(bytes(out))
        self.assertIn(b"\xff\xc4", fixed)
        a, b = Image.open(io.BytesIO(fixed)), Image.open(io.BytesIO(data))
        self.assertEqual(a.convert("RGB").tobytes(), b.convert("RGB").tobytes())
        self.assertEqual(pc.complete_mjpeg(data), data, "a complete JPEG is left alone")

    def test_write_png(self):
        path = Path(tempfile.mkdtemp()) / "t.png"
        try:
            pc.write_png(path, 3, 2, bytes(range(18)))
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"))
            idat = raw[raw.index(b"IDAT") + 4:raw.index(b"IEND") - 8]
            self.assertEqual(zlib.decompress(idat), b"\x00" + bytes(range(9)) + b"\x00" + bytes(range(9, 18)))
            if Image is not None:
                with Image.open(path) as im:
                    self.assertEqual(im.size, (3, 2))
        finally:
            path.unlink(missing_ok=True)


class TestSimulatedCamera(unittest.TestCase):
    def test_grid_and_photo(self):
        cam = pc.Camera("sim")
        grid = cam.capture_grid(16, 12)
        self.assertEqual((len(grid), len(grid[0])), (16, 12))
        self.assertTrue(all(0 <= v <= 255 for row in grid for v in row))

    def test_objects_look_different(self):
        rng = random.Random(1)
        dark = {o: sum(pc._grey(p) < 128 for p in pc.sim_scene(o, 16, 16, rng, 3)) for o in pc.SIM_OBJECTS}
        self.assertGreater(dark["box"], dark["nothing"])
        self.assertGreater(dark["ball"], dark["nothing"])

    def test_photo_reaches_pipath(self):
        code = ("from pipath_camera import Camera\n"
                "cam = Camera()\n"
                "print(cam.take_photo('snap.jpg'))\n"
                "cam.capture_grid(8, 8)\n")
        r = run_shim(code, keep_folder=True)
        self.assertEqual(r.rc, 0, r.stderr)
        photos = [m for m in r.messages if m.get("t") == "photo"]
        self.assertEqual(len(photos), 2)
        self.assertTrue(photos[0]["path"].endswith(("snap.jpg", "snap.png")))
        self.assertTrue(photos[1].get("grid"))
        self.assertTrue(any(p.name.startswith("snap.") for p in r.folder.iterdir()))


class TestCameraErrors(unittest.TestCase):
    @unittest.skipIf(pc.find_usb_cameras(), "a USB camera is plugged in")
    def test_missing_usb_camera_is_explained(self):
        code = "from pipath_camera import Camera\ncam = Camera('usb')\n"
        r = run_shim(code, env={"PIPATH_CAMERA": "usb"})
        err = parse_traceback(r.stderr, "student.py", code)
        self.assertIsNotNone(err, r.stderr)
        d = HintEngine().diagnose(err)
        self.assertEqual(d.entry_id, "camera_not_found")
        self.assertEqual(d.line, 2)

    def test_unknown_kind(self):
        with self.assertRaises(pc.CameraNotFound):
            pc.Camera("webcam")


if __name__ == "__main__":
    unittest.main()
