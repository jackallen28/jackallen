"""The Output box (a terminal), with a typing line for answering input() questions.

Up / Down in the typing line bring back earlier answers. Right-click the Output to copy or
clear it. Programs that print with end="\\r" (a progress counter) rewrite their line.
"""
from __future__ import annotations

import tkinter as tk

from .theme import C
from .widgets import PButton, PopupMenu

MAX_LINES = 1500
MAX_WRITE = 60_000            # characters drawn at once: a flood of output is trimmed, not frozen on
PROMPT = "Type your answer here, then press Enter ▸"
SHORT_PROMPT = "Answer ▸"          # when the Output is narrow (the board takes the room on a small screen)


class Console(tk.Frame):
    def __init__(self, master, on_send=None):
        super().__init__(master, bg=C["bg"], relief="sunken", bd=2)
        self.on_send = on_send
        self.history: list[str] = []
        self._cr_pending = False
        self._hist_i = 0

        head = tk.Frame(self, bg=C["bg"], relief="raised", bd=1)
        head.pack(fill="x")
        tk.Label(head, text="OUTPUT", font="small_bold", fg=C["ink"], bg=C["bg"], padx=10, pady=3).pack(side="left")
        self.status = tk.Label(head, text="", font="small", fg=C["muted"], bg=C["bg"], padx=10)
        self.status.pack(side="right")

        body = tk.Frame(self, bg=C["con_bg"])
        body.pack(fill="both", expand=True)
        self.text = tk.Text(body, bg=C["con_bg"], fg=C["con_fg"], font="code", wrap="word",
                            relief="flat", bd=0, highlightthickness=0, padx=12, pady=8,
                            insertwidth=0, cursor="arrow", height=8, selectbackground=C["con_fg"],
                            selectforeground=C["con_bg"])
        sb = tk.Scrollbar(body, command=self.text.yview, width=14)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("err", foreground=C["con_err"])
        self.text.tag_configure("in", foreground=C["con_in"], font="code")
        self.text.tag_configure("info", foreground=C["con_info"], font="code_ui")
        self.text.tag_configure("warn", foreground=C["con_warn"], font="code_ui")
        self.text.configure(state="disabled")
        self.text.bind("<Button-3>", self._menu)

        # input row
        self.in_row = tk.Frame(self, bg=C["bg"], padx=6, pady=4, relief="raised", bd=1)
        self.in_row.pack(fill="x")
        self.in_label = tk.Label(self.in_row, text=PROMPT, font="small_bold", fg=C["faint"], bg=C["bg"])
        self.in_label.pack(side="left", padx=(4, 8))
        self.entry = tk.Entry(self.in_row, font="code", bg="#FFFFFF", fg=C["ink"], insertbackground=C["ink"],
                              relief="sunken", bd=2, highlightthickness=1, highlightbackground=C["bg"],
                              highlightcolor=C["go"], disabledbackground=C["panel_alt"])
        self.send_btn = PButton(self.in_row, "Send", self._send, kind="secondary", pady=2)
        self.send_btn.pack(side="right", padx=(8, 0))         # packed first, so it always has room
        self.entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.entry.bind("<Return>", self._send)
        self.entry.bind("<KP_Enter>", self._send)
        self.entry.bind("<Up>", lambda e: self._recall(-1))
        self.entry.bind("<Down>", lambda e: self._recall(1))
        for seq in ("<Control-k>", "<Control-t>", "<Control-d>", "<Control-h>", "<Control-w>"):
            self.entry.bind(seq, lambda e: "break")       # Tk's Emacs keys: easy to press by accident
        self.in_row.bind("<Configure>", self._fit_prompt)
        self.set_input_enabled(False)

    def _fit_prompt(self, e) -> None:
        """Keep the answer box visible: a shorter label when the Output is narrow."""
        text = PROMPT if e.width >= 520 else SHORT_PROMPT
        if self.in_label.cget("text") != text:
            self.in_label.configure(text=text)

    def _send(self, _e=None):
        if str(self.entry.cget("state")) == "disabled":
            return "break"
        text = self.entry.get()
        self.entry.delete(0, "end")
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self._hist_i = len(self.history)
        self.write(text + "\n", "in")
        if self.on_send:
            self.on_send(text)
        return "break"

    def _recall(self, step: int):
        """Up / Down: an earlier answer, like a shell."""
        if not self.history or str(self.entry.cget("state")) == "disabled":
            return "break"
        self._hist_i = max(0, min(len(self.history), self._hist_i + step))
        self.entry.delete(0, "end")
        if self._hist_i < len(self.history):
            self.entry.insert(0, self.history[self._hist_i])
        return "break"

    def set_input_enabled(self, on: bool, focus: bool = False) -> None:
        self.entry.configure(state="normal" if on else "disabled")
        self.send_btn.set_enabled(on)
        self.in_label.configure(fg=C["go"] if on else C["faint"])
        if on and focus:
            self.entry.focus_set()

    def waiting_for_answer(self) -> None:
        """The program called input(): put the cursor in the answer box (like Thonny does)."""
        if str(self.entry.cget("state")) == "normal":
            focus = self.focus_get()
            if not isinstance(focus, tk.Entry) or focus is self.entry:
                self.entry.focus_set()
            self.status.configure(text="waiting for your answer", fg=C["go"])

    def write(self, text: str, tag: str | None = None) -> None:
        if len(text) > MAX_WRITE:      # keep the end: that's what the student is looking at
            text = "... (lots of output skipped) ...\n" + text[-MAX_WRITE:]
        t = self.text
        at_bottom = t.yview()[1] >= 0.999
        t.configure(state="normal")
        if self._cr_pending:               # the last write ended in \r: this one writes over that line
            self._cr_pending = False
            if not text.startswith("\n"):
                t.delete("end-1c linestart", "end-1c")
        text = text.replace("\r\n", "\n")
        if text.endswith("\r"):            # "Loading 3\r": keep it on screen until the next text comes
            text = text.rstrip("\r")
            self._cr_pending = True
        if "\r" in text:
            parts = text.split("\r")
            t.insert("end", parts[0], (tag,) if tag else ())
            for part in parts[1:]:          # \r: back to the start of the line, and write over it
                t.delete("end-1c linestart", "end-1c")
                t.insert("end", part, (tag,) if tag else ())
        else:
            t.insert("end", text, (tag,) if tag else ())
        lines = int(t.index("end-1c").split(".")[0])
        if lines > MAX_LINES:
            t.delete("1.0", f"{lines - MAX_LINES}.0")
        t.configure(state="disabled")
        if at_bottom:                  # scrolled up to read something? Don't jump away from it
            t.see("end")

    def clear(self) -> None:
        self._cr_pending = False
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def set_status(self, text: str, colour: str | None = None) -> None:
        self.status.configure(text=text, fg=colour or C["muted"])

    # ---------------------------------------------------------------- right-click menu
    def _copy(self) -> None:
        t = self.text
        text = t.get("sel.first", "sel.last") if t.tag_ranges("sel") else t.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)

    def _menu(self, e):
        has_sel = bool(self.text.tag_ranges("sel"))
        PopupMenu.of(self).show([
            ("Copy" if has_sel else "Copy all the output", "Ctrl+C", self._copy, True),
            ("Select all", "", lambda: self.text.tag_add("sel", "1.0", "end-1c"), True),
            None,
            ("Clear the output", "", self.clear, True),
        ], e.x_root, e.y_root)
        return "break"
