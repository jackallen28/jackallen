"""The Output box, with a typing line for answering input() questions."""
from __future__ import annotations

import tkinter as tk

from .theme import C
from .widgets import PButton

MAX_LINES = 1500
PROMPT = "Type your answer here, then press Enter ▸"
SHORT_PROMPT = "Answer ▸"          # when the Output is narrow (the board takes the room on a small screen)


class Console(tk.Frame):
    def __init__(self, master, on_send=None):
        super().__init__(master, bg=C["con_bg"])
        self.on_send = on_send

        head = tk.Frame(self, bg="#1B1F26")
        head.pack(fill="x")
        tk.Label(head, text="OUTPUT", font="small_bold", fg="#8B93A1", bg="#1B1F26",
                 padx=12, pady=5).pack(side="left")
        self.status = tk.Label(head, text="", font="small", fg="#8B93A1", bg="#1B1F26", padx=12)
        self.status.pack(side="right")

        body = tk.Frame(self, bg=C["con_bg"])
        body.pack(fill="both", expand=True)
        self.text = tk.Text(body, bg=C["con_bg"], fg=C["con_fg"], font="code", wrap="word",
                            relief="flat", bd=0, highlightthickness=0, padx=12, pady=8,
                            insertwidth=0, cursor="arrow", height=8)
        sb = tk.Scrollbar(body, command=self.text.yview, width=12)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("err", foreground=C["con_err"])
        self.text.tag_configure("in", foreground=C["con_in"], font="code")
        self.text.tag_configure("info", foreground=C["con_info"], font="code_ui")
        self.text.tag_configure("warn", foreground="#FFD27A", font="code_ui")
        self.text.configure(state="disabled")

        # input row
        self.in_row = tk.Frame(self, bg="#1B1F26", padx=8, pady=6)
        self.in_row.pack(fill="x")
        self.in_label = tk.Label(self.in_row, text=PROMPT, font="small_bold", fg="#5A606B", bg="#1B1F26")
        self.in_label.pack(side="left", padx=(4, 8))
        self.entry = tk.Entry(self.in_row, font="code", bg="#262B34", fg="#FFFFFF",
                              insertbackground="#FFFFFF", relief="flat", highlightthickness=2,
                              highlightbackground="#262B34", highlightcolor=C["go"],
                              disabledbackground="#20242B")
        self.entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.send_btn = PButton(self.in_row, "Send", self._send, kind="dark", pady=4)
        self.send_btn.pack(side="left", padx=(8, 0))
        self.entry.bind("<Return>", self._send)
        self.entry.bind("<KP_Enter>", self._send)
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
        self.write(text + "\n", "in")
        if self.on_send:
            self.on_send(text)
        return "break"

    def set_input_enabled(self, on: bool) -> None:
        self.entry.configure(state="normal" if on else "disabled",
                             highlightcolor=C["go"] if on else "#262B34")
        self.send_btn.set_enabled(on)
        self.in_label.configure(fg=C["con_in"] if on else "#5A606B")
        if on:
            self.entry.focus_set()

    def write(self, text: str, tag: str | None = None) -> None:
        t = self.text
        t.configure(state="normal")
        t.insert("end", text, (tag,) if tag else ())
        lines = int(t.index("end-1c").split(".")[0])
        if lines > MAX_LINES:
            t.delete("1.0", f"{lines - MAX_LINES}.0")
        t.configure(state="disabled")
        t.see("end")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def set_status(self, text: str, colour: str = "#8B93A1") -> None:
        self.status.configure(text=text, fg=colour)
