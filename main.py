#!/usr/bin/env python3
"""Start PiPath.   python3 main.py   (add --scale 1.2 for bigger text on a large screen)"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.version_info < (3, 11):
    sys.exit("PiPath needs Python 3.11 or newer (Raspberry Pi OS Bookworm or later).")

from pipath.app import PiPathApp  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="PiPath: a Python coding tutor for Raspberry Pi")
    ap.add_argument("--scale", type=float, default=1.0, help="text size multiplier, e.g. 1.25")
    args = ap.parse_args()
    PiPathApp(scale=args.scale).mainloop()


if __name__ == "__main__":
    main()
