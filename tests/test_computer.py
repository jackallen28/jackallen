"""The students' pipath_computer helper: the Pi's numbers, and opening files (never for real here)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipath" / "student_lib"))
sys.path.insert(0, str(ROOT / "tests"))

import pipath_computer as pc  # noqa: E402
from shimrun import HAVE_GPIOZERO, run_shim  # noqa: E402


class TestNumbers(unittest.TestCase):
    def test_numbers_are_sensible(self):
        for value in (pc.cpu_temp(), pc.cpu_load(), pc.ram_used()):
            self.assertIsInstance(value, float)
        self.assertTrue(0 <= pc.cpu_load() <= 100)
        self.assertTrue(0 <= pc.ram_used() <= 100)
        self.assertTrue(-20 < pc.cpu_temp() < 120)

    def test_simulator_can_pretend(self):
        with mock.patch.dict(os.environ, {"PIPATH_SIM_TEMP": "71.26", "PIPATH_SIM_LOAD": "150",
                                          "PIPATH_SIM_RAM": "40"}):
            self.assertEqual(pc.cpu_temp(), 71.3)
            self.assertEqual(pc.cpu_load(), 100.0)          # kept between 0 and 100
            self.assertEqual(pc.ram_used(), 40.0)

    def test_reads_the_temperature_file(self):
        with tempfile.NamedTemporaryFile("w", suffix="temp", delete=False) as f:
            f.write("48312\n")
        try:
            with mock.patch.object(pc, "TEMP_FILE", f.name), mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("PIPATH_SIM_TEMP", None)
                self.assertEqual(pc.cpu_temp(), 48.3)
        finally:
            os.unlink(f.name)


class TestOpening(unittest.TestCase):
    def test_demo_only_says_what_it_would_open(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "song.wav"
            path.write_bytes(b"RIFF")
            with mock.patch.dict(os.environ, {"PIPATH_DEMO": "1", "DISPLAY": ":0"}), \
                    mock.patch.object(pc, "_launch") as launch, mock.patch("builtins.print") as out:
                pc.open_file(path)
                pc.open_website("https://example.com")
            launch.assert_not_called()
            self.assertIn("Opening song.wav", out.call_args_list[0].args[0])

    def test_opens_with_the_desktop_app(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "photo.png"
            path.write_bytes(b"x")
            env = {"DISPLAY": ":0"}
            with mock.patch.dict(os.environ, env), mock.patch.object(pc, "_launch") as launch, \
                    mock.patch("builtins.print"):
                os.environ.pop("PIPATH_DEMO", None)
                pc.open_file(path)
            launch.assert_called_once_with(str(path.resolve()))

    def test_friendly_errors(self):
        with self.assertRaises(FileNotFoundError):
            pc.open_file("no_such_file.mp4")
        with self.assertRaises(ValueError):
            pc.open_website("youtube.com")


@unittest.skipUnless(HAVE_GPIOZERO, "gpiozero is not installed")
class TestShimStats(unittest.TestCase):
    def test_watch_the_goal_sets_pretend_numbers(self):
        code = ("from pipath_computer import cpu_load\nfrom time import sleep\n"
                "for i in range(6):\n    print(cpu_load())\n    sleep(0.3)\n")
        r = run_shim(code, events=["0.6 stat load 87"], env={"PIPATH_DEMO": "1"})
        self.assertEqual(r.rc, 0, r.stderr)
        self.assertIn("87.0", r.stdout)


if __name__ == "__main__":
    unittest.main()
