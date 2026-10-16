"""The Wiring card for GPIO activities: safety, parts, how to connect, and a 40-pin header map."""
from __future__ import annotations

import re
import tkinter as tk

from ..gpio import HEADER, SAFETY
from .board import LED_COLOURS
from .theme import C
from .widgets import PButton, RichText, label

POWER_COLOURS = {"5V": "#D7263D", "3V3": "#E07A00", "GND": "#1E2330", "ID": "#B4B0A6"}


class WiringCard(tk.Frame):
    """Collapsible. Rows are ticked (✓) or crossed (✗) by "Check my wiring"."""

    def __init__(self, master, lesson: dict, project: dict, parts: list[dict], open_: bool = False,
                 on_check=None):
        super().__init__(master, bg=C["panel"], highlightthickness=1, highlightbackground=C["info"])
        self.parts = parts
        self.marks: dict[int, tk.Label] = {}
        head = tk.Frame(self, bg=C["info_soft"], padx=14, pady=8, cursor="hand2")
        head.pack(fill="x")
        self.arrow = label(head, "", font="ui_bold", fg=C["info"], bg=C["info_soft"])
        self.arrow.pack(side="left")
        label(head, "WIRING + SAFETY", font="small_bold", fg=C["info"], bg=C["info_soft"]).pack(side="left", padx=(6, 0))
        n = len(parts)
        label(head, f"{n} part{'s' if n != 1 else ''}", font="small", fg=C["info"], bg=C["info_soft"]).pack(side="right")
        for w in (head, *head.winfo_children()):
            w.bind("<Button-1>", lambda e: self.toggle())

        self.body = tk.Frame(self, bg=C["panel"], padx=14, pady=10)
        self._build(lesson, project, on_check)
        self.is_open = not open_
        self.toggle()

    def toggle(self) -> None:
        self.is_open = not self.is_open
        self.arrow.configure(text="▾" if self.is_open else "▸")
        if self.is_open:
            self.body.pack(fill="x")
        else:
            self.body.pack_forget()

    def _build(self, lesson, project, on_check) -> None:
        b = self.body
        safe = tk.Frame(b, bg=C["warn_soft"], padx=10, pady=8)
        safe.pack(fill="x")
        label(safe, "⚠  Safety first", font="small_bold", fg=C["warn"], bg=C["warn_soft"]).pack(anchor="w")
        rt = RichText(safe, bg=C["warn_soft"], font="small")
        rt.tag_configure("b", font="small_bold")
        rt.pack(fill="x")
        rt.render("\n".join(f"- {s}" for s in SAFETY))

        if project.get("parts"):
            label(b, "YOU NEED", font="small_bold", fg=C["muted"], bg=C["panel"]).pack(anchor="w", pady=(10, 2))
            label(b, "  •  ".join(project["parts"]), font="small", bg=C["panel"], wraplength=330).pack(anchor="w")

        label(b, "CONNECT", font="small_bold", fg=C["muted"], bg=C["panel"]).pack(anchor="w", pady=(10, 2))
        for row in lesson.get("wiring", []):
            r = tk.Frame(b, bg=C["panel"])
            r.pack(fill="x", pady=2)
            mark = tk.Label(r, text="•", font="ui_bold", width=2, fg=C["faint"], bg=C["panel"])
            mark.pack(side="left", anchor="n")
            txt = RichText(r, bg=C["panel"], font="small")
            txt.tag_configure("b", font="small_bold")
            txt.pack(side="left", fill="x", expand=True)
            txt.render(f"**{row.get('part', '')}:** {row.get('connect', '')}")
            for p in [row.get("pin")] + list(row.get("pins", [])):
                if p is not None:
                    self.marks[int(p)] = mark

        self._header_map(b)
        label(b, "Pin 1 is the corner pin nearest the SD card slot (it has a square pad underneath).",
              font="small", fg=C["muted"], bg=C["panel"], wraplength=330).pack(anchor="w", pady=(2, 0))
        if on_check:
            row = tk.Frame(b, bg=C["panel"])
            row.pack(fill="x", pady=(10, 0))
            PButton(row, "Check my wiring", on_check, kind="secondary", font="small_bold", pady=5).pack(side="left")
            label(row, "  Tests each part, one at a time.", font="small", fg=C["muted"], bg=C["panel"]).pack(side="left")

    def _header_map(self, master) -> None:
        """The 40-pin header as two columns, with the pins this activity uses highlighted."""
        used: dict[int, tuple[str, str]] = {}
        for p in self.parts:
            for i, g in enumerate(p["pins"]):
                colour = LED_COLOURS.get(p.get("colour", ""), C["accent"]) if p["kind"] == "led" else C["accent"]
                if p["kind"] == "rgbled":
                    colour = ("#FF3B30", "#2ED158", "#3B82F6")[i % 3]
                name = p["label"].split(" (")[0]
                name = name if len(name) <= 13 else name[:12] + "…"
                used[g] = (name + (f" {'RGB'[i]}" if p["kind"] == "rgbled" else ""), colour)
        row_h, w = 15, 340
        cv = tk.Canvas(master, width=w, height=20 * row_h + 16, bg=C["panel"], highlightthickness=0)
        cv.pack(anchor="w", pady=(10, 0))
        lx, rx = w // 2 - 12, w // 2 + 12
        cv.create_rectangle(lx - 9, 4, rx + 9, 20 * row_h + 10, fill="#2B2F36", outline="")
        for phys, what in HEADER.items():
            row, right = (phys - 1) // 2, phys % 2 == 0
            x, y = (rx if right else lx), 12 + row * row_h
            if isinstance(what, int):
                name = f"GPIO{what}"
                part = used.get(what)
                fill = part[1] if part else "#C9A227"
                text = f"{name}  {part[0]}" if part else name
                tcol, font = (C["ink"], "small_bold") if part else (C["faint"], "small")
            else:
                fill = POWER_COLOURS.get(what, "#999999")
                text, tcol, font = what, C["muted"], "small"
            cv.create_oval(x - 5, y - 5, x + 5, y + 5, fill=fill, outline="#FFFFFF" if isinstance(what, int) and used.get(what) else "")
            cv.create_text(x + (12 if right else -12), y, text=text, anchor="w" if right else "e", fill=tcol, font=font)

    def mark_from_output(self, text: str) -> int:
        """Tick or cross rows from 'Check my wiring' output lines like '✓ Button (GPIO23) works!'."""
        n = 0
        for m in re.finditer(r"^([✓✗]).*?GPIO(\d+)", text, re.M):
            mark = self.marks.get(int(m.group(2)))
            if mark is not None:
                ok = m.group(1) == "✓"
                mark.configure(text="✓" if ok else "✗", fg=C["ok"] if ok else C["err"])
                n += 1
        return n
