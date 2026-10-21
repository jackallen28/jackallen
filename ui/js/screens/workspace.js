// The project workspace. In this first build it has the code editor with
// autosave; the Wiring Wizard, simulator, Upload, Serial Monitor and the
// step-by-step guide arrive in the next build steps.

import { api } from "../api.js";
import { h, icon, clear, fill, download } from "../dom.js";
import { appWindow, tool, separator, spacer, messageBox } from "../widgets/window.js";
import { codeEditor } from "../widgets/editor.js";
import { Autosaver, Status, statusText } from "../autosave.js";
import { offlineStore } from "../offline-store.js";
import { state, board, tier, partName } from "../state.js";

const SOON = "Coming soon";

export function starterSketch(title) {
  return `// ${title}
// Your code saves by itself.

void setup() {
  // This runs once, when the board starts.

}

void loop() {
  // This runs again and again, forever.

}
`;
}

export function workspaceScreen(root, { projectId, openSettings, back }) {
  const isFreePlay = projectId === "freeplay";
  const summary = isFreePlay ? null : state.catalogue.projects.find((p) => p.id === projectId);
  const title = isFreePlay ? "Free Play" : summary?.title ?? "Project";

  const saveCell = h("span", { class: "cell save-status", "aria-live": "polite" });
  const cursorCell = h("span", { class: "cell" });
  const boardCell = h("span", { class: "cell" });
  const panel = h("aside", { class: "side-panel", "aria-label": "About this project" });
  const editorHolder = h("main", { class: "editor-holder", id: "main" }, h("p", { class: "muted loading", text: "Opening..." }));

  const win = appWindow({
    title,
    className: "workspace",
    toolbar: [
      tool("back", "Projects", back),
      separator(),
      tool("wiring", "Wiring", null, { disabled: true, title: SOON }),
      tool("run", "Run", null, { disabled: true, title: SOON }),
      tool("upload", "Upload", null, { disabled: true, title: SOON }),
      tool("serial", "Serial Monitor", null, { disabled: true, title: SOON }),
      separator(),
      tool("download", "Download .ino", () => downloadIno()),
      spacer(),
      tool("settings", "Settings", () => openSettings({ onSaved: showBoard })),
    ],
    body: h("div", { class: "split" }, panel, editorHolder),
    status: [saveCell, boardCell, h("span", { class: "cell grow" }), cursorCell],
  });
  clear(root).append(win);

  const key = `${state.me.student.id}:${projectId}`;
  const saver = new Autosaver({
    key,
    store: offlineStore,
    send: (code) => api.saveSketch(projectId, code),
    onStatus: (s, detail) => {
      saveCell.className = `cell save-status ${s}`;
      fill(saveCell, s === Status.ERROR || s === Status.OFFLINE ? icon("warn") : null, statusText(s, detail));
    },
  });
  saver.onStatus(Status.SAVED);
  let editor = null;

  function showBoard() {
    const b = board();
    boardCell.replaceChildren(icon("board"), b ? b.name : "No board");
  }
  showBoard();

  function downloadIno() {
    const code = editor ? editor.value : "";
    const name = `${(title.replace(/[^A-Za-z0-9]+/g, "_").replace(/^_|_$/g, "") || "sketch")}.ino`;
    download(new Blob([code], { type: "text/plain" }), name);
  }

  function renderPanel(project) {
    const t = project ? tier(project.tier) : null;
    fill(panel,
      isFreePlay
        ? h("div", { class: "panel-head" }, icon("freeplay", "icon-32"), h("h2", { text: "Free Play" }))
        : h("div", { class: "panel-head" }, h("span", { class: `badge tier-${project.tier}`, text: t?.name ?? "" }), h("h2", { text: project.title })),
      h("p", { text: isFreePlay ? "Build anything you like! Write your own code here." : project.intro }),
      !isFreePlay && project.parts.length ? h("fieldset", { class: "groupbox" },
        h("legend", { text: "Parts" }),
        h("ul", { class: "parts-list" }, project.parts.map((p) =>
          h("li", {}, icon("parts"), h("span", { text: `${partName(p.type, p.count || 1)}${p.note ? ` (${p.note})` : ""}` }))))) : null,
      h("div", { class: "note info" }, icon("about"), h("div", {},
        h("strong", { text: isFreePlay ? "More is on the way" : "The guide is on its way" }),
        h("p", { text: isFreePlay
          ? "Soon you'll be able to add parts, wire them with the Wiring Wizard and run your code in the simulator."
          : "Soon this project will start with the Wiring Wizard, then guide you one part at a time." }),
        h("p", { text: "You can already write code here. It saves by itself." }))),
      !isFreePlay && project.parts.length ? h("div", { class: "note safety" }, icon("warn"), h("div", {},
        h("strong", { text: "Wiring safely" }),
        h("ul", {},
          h("li", { text: "Unplug the USB cable before you change any wires. Plug it back in after." }),
          board()?.logic_volts === 3.3 ? h("li", { text: "Your board runs on 3.3V. Never connect 5V to one of its pins." }) : null,
          project.parts.some((p) => p.type === "led") ? h("li", { text: "Always use a resistor with an LED." }) : null))) : null);
  }

  let closed = false;
  async function open() {
    let project = summary;
    try {
      if (!isFreePlay) project = await api.project(projectId);
    } catch (err) {
      if (err.status === 404) {
        await messageBox({ kind: "warn", instruction: "That project isn't here.", text: "It may have been removed. Pick another one." });
        back();
        return;
      }
      project = summary;
    }
    if (closed) return;
    renderPanel(project ?? { title, intro: "", parts: [], tier: "" });

    let serverCode = starterSketch(title);
    let updatedAt = 0;
    let isNew = true;
    try {
      const sk = await api.sketch(projectId);
      serverCode = sk.code;
      updatedAt = sk.updated_at;
      isNew = false;
    } catch (err) {
      if (err.status !== 404) {
        editorHolder.replaceChildren(h("div", { class: "note error" }, icon("warn"), h("span", { text: err.message })));
        return;
      }
    }
    if (closed) return;
    const code = await saver.recover(serverCode, updatedAt);
    editor = codeEditor({
      value: code,
      label: `${title} code`,
      onChange: (v) => saver.change(v),
      onCursor: (row, col) => { cursorCell.textContent = `Line ${row}, Col ${col}`; },
    });
    editorHolder.replaceChildren(editor.el);
    editor.focus();
    if (isNew) api.saveProgress(projectId, { step: 0, started_at: Date.now() }).catch(() => {});
  }

  const onOnline = () => saver.retry();
  const onLeave = () => {
    if (saver.dirty) {
      saver.keep(saver.code);
      api.saveSketch(projectId, saver.code, { keepalive: true }).catch(() => {});
    }
  };
  window.addEventListener("online", onOnline);
  window.addEventListener("pagehide", onLeave);
  open();

  return async () => {
    closed = true;
    window.removeEventListener("online", onOnline);
    window.removeEventListener("pagehide", onLeave);
    await saver.flush();
    saver.stop();
  };
}
