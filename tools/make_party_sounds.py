"""Make the six little sounds for the Dice DJ activity: data/demo_files/p3/party/1.wav ... 6.wav.

Sound n is n rising beeps, so students can hear which number they rolled. Standard library only.
Run it again if the files are lost:  python3 tools/make_party_sounds.py
"""
import math
import wave
from pathlib import Path

RATE = 11025
OUT = Path(__file__).resolve().parent.parent / "data" / "demo_files" / "p3" / "party"
NOTES = [523.25, 587.33, 659.25, 783.99, 880.00, 1046.50]     # C D E G A C: a happy scale


def beep(freq: float, seconds: float) -> bytes:
    n = int(RATE * seconds)
    frames = []
    for i in range(n):
        fade = min(1.0, i / 200, (n - i) / 200)                   # no clicks at the ends
        frames.append(int(127 + 90 * fade * math.sin(2 * math.pi * freq * i / RATE)))
    return bytes(frames)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    gap = bytes([128]) * int(RATE * 0.07)
    for n in range(1, 7):
        audio = b"".join(beep(NOTES[i], 0.13) + gap for i in range(n))
        with wave.open(str(OUT / f"{n}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(1)
            w.setframerate(RATE)
            w.writeframes(audio)
    print("Made", ", ".join(f"{n}.wav" for n in range(1, 7)), "in", OUT)


if __name__ == "__main__":
    main()
