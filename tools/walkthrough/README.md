# Walkthrough videos

Records PiPath being used (the real app, driven by a script) and renders two 1920×1080 videos:
`walkthrough_captions.mp4` (captions, chapter labels, title cards) and `walkthrough_clean.mp4`
(pointer only, pauses cut to 55 %).

```
RECORD_PY=python3 RENDER_PY=python3 tools/walkthrough/make.sh walkthrough_out
```

- `studio.py`: the recorder (Xvfb + ffmpeg, a timeline of pointer moves, clicks, captions, chapters
  and pauses) and the renderer (pointer + teal click ripple, Vista caption balloons with key words in
  BNTS purple, the teal chapter pill, title cards). Needs ffmpeg and Xvfb; rendering needs Pillow.
- `traffic_lights.py`: the story (Mia builds Traffic Lights). Copy it to make a walkthrough of
  another activity.

Style: a 1600×900 screen scaled ×1.2; the pointer glides ~0.65 s (eased) and pauses before clicks;
typing 85–160 ms a key; captions are one sentence, up for 0.9 s + 0.33 s a word (at least 2.6 s).
Dev tool only: not part of the app.
