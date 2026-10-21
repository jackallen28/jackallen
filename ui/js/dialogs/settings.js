// Settings: how much help, which board, nudges; Save my work / Open my
// work; About. Students can open it from every screen.

import { api, request } from "../api.js";
import { h, icon, joinNames, download } from "../dom.js";
import { openDialog, messageBox } from "../widgets/window.js";
import { aboutContent } from "./about.js";
import { state, visibleBoards } from "../state.js";

export const HELP_LEVELS = [
  { id: "beginner", name: "Beginner", text: "Lots of help: full explanations, and hints any time you want them." },
  { id: "moderate", name: "Moderate", text: "Some help: each project gives you a little less help as you go." },
  { id: "advanced", name: "Advanced", text: "Tutorial off (good for Years 9 and 10): see the goal first, real compiler messages, fewer hints, and Level up challenges." },
];

/** A list of choices that look like Vista option cards (works as radio buttons). */
export function optionCards({ name, options, value, onChange, className = "" }) {
  const cards = options.map((o) => {
    const input = h("input", { type: "radio", name, value: o.id, checked: o.id === value, class: "visually-hidden" });
    const card = h("label", { class: ["option-card", "selectable", o.id === value && "selected"] },
      input,
      o.icon ? icon(o.icon, "icon-32") : null,
      h("span", { class: "option-text" },
        h("span", { class: "option-name", text: o.name }),
        o.text ? h("span", { class: "option-desc", text: o.text }) : null,
        o.chips?.length ? h("span", { class: "chips" }, o.chips.map((c) => h("span", { class: "chip", text: c }))) : null));
    input.addEventListener("change", () => {
      cards.forEach((c) => c.classList.toggle("selected", c === card));
      onChange(o.id);
    });
    return card;
  });
  return h("div", { class: ["option-cards", className], role: "radiogroup" }, cards);
}

export function boardOptions() {
  return visibleBoards().map((b) => ({
    id: b.id,
    name: b.name,
    icon: "board",
    text: b.notes,
    chips: [b.logic_volts === 5 ? "5V" : "3.3V", b.wifi ? "WiFi" : null, b.bluetooth ? "Bluetooth" : null].filter(Boolean),
  }));
}

/** Opens Settings on a tab ("me", "work" or "about"). Resolves when closed. */
export function openSettings({ tab = "me", onSaved = () => {} } = {}) {
  const settings = { ...state.me.settings };
  let dlg;

  const tabs = [
    { id: "me", label: "Help and board", render: renderMe },
    { id: "work", label: "My work", render: renderWork },
    { id: "about", label: "About", render: () => aboutContent() },
  ];
  const panel = h("div", { class: "tab-panel", role: "tabpanel" });
  const tabButtons = tabs.map((t) => h("button", {
    class: "tab", type: "button", role: "tab", id: `tab-${t.id}`,
    onclick: () => select(t.id),
  }, t.label));

  function select(id) {
    tabButtons.forEach((b, i) => b.setAttribute("aria-selected", String(tabs[i].id === id)));
    panel.setAttribute("aria-labelledby", `tab-${id}`);
    panel.replaceChildren(tabs.find((t) => t.id === id).render());
  }

  function renderMe() {
    const varSelect = h("div");
    function renderVariant() {
      const b = state.catalogue.boards.find((x) => x.id === settings.board);
      if (!b?.variants?.length) {
        settings.board_variant = "";
        varSelect.replaceChildren();
        return;
      }
      if (!b.variants.some((v) => v.id === settings.board_variant)) settings.board_variant = "";
      varSelect.replaceChildren(h("label", { class: "check" },
        h("input", {
          type: "checkbox", checked: settings.board_variant === b.variants[0].id,
          onchange: (e) => { settings.board_variant = e.target.checked ? b.variants[0].id : ""; },
        }),
        h("span", { text: b.variants[0].label })));
    }
    renderVariant();
    return h("div", {},
      h("fieldset", { class: "groupbox" },
        h("legend", { text: "How much help would you like?" }),
        optionCards({ name: "help", options: HELP_LEVELS, value: settings.help_level, onChange: (v) => { settings.help_level = v; } })),
      h("fieldset", { class: "groupbox" },
        h("legend", { text: "Which board do you have?" }),
        optionCards({ name: "board", options: boardOptions(), value: settings.board, className: "compact", onChange: (v) => { settings.board = v; renderVariant(); } }),
        varSelect),
      h("fieldset", { class: "groupbox" },
        h("legend", { text: "The Coach" }),
        h("label", { class: "check" },
          h("input", { type: "checkbox", checked: settings.nudges, onchange: (e) => { settings.nudges = e.target.checked; } }),
          h("span", { text: "Offer help when I seem stuck" }))));
  }

  function renderWork() {
    const fileInput = h("input", { type: "file", accept: ".circuit", class: "visually-hidden", onchange: (e) => openMyWork(e.target) });
    return h("div", {},
      h("fieldset", { class: "groupbox" },
        h("legend", { text: "Save my work" }),
        h("p", { text: "Download all your projects as a .circuit file, to keep or take home. You can open it again on any CircuitPath." }),
        h("button", { class: "pill", type: "button", onclick: saveMyWork }, icon("save"), "Save my work")),
      h("fieldset", { class: "groupbox" },
        h("legend", { text: "Open my work" }),
        h("p", { text: "Open a .circuit file you saved before. Projects you don't have here are added. If the file has a newer copy of a project, you'll be asked first." }),
        h("button", { class: "pill purple", type: "button", onclick: () => fileInput.click() }, icon("open"), "Open my work"),
        fileInput));
  }

  async function save() {
    try {
      const saved = await api.saveSettings(settings);
      state.me.settings = saved;
      dlg.close(true);
      onSaved(saved);
    } catch (err) {
      messageBox({ kind: "error", instruction: "Your settings couldn't be saved.", text: err.message });
    }
  }

  dlg = openDialog({
    title: "Settings",
    iconName: "settings",
    wide: true,
    content: h("div", { class: "property-sheet" }, h("div", { class: "tabs", role: "tablist" }, tabButtons), panel),
    buttons: [
      h("button", { class: "btn default", type: "button", onclick: save }, "OK"),
      h("button", { class: "btn", type: "button", onclick: () => dlg.close(false) }, "Cancel"),
    ],
  });
  select(tab);
  return dlg.result;
}

/** Save my work: downloads <Name>_CircuitPath_<date>.circuit. */
export async function saveMyWork() {
  try {
    const res = await request("GET", api.exportUrl, undefined, { raw: true });
    const cd = res.headers.get("Content-Disposition") || "";
    const utf = /filename\*=UTF-8''([^;]+)/.exec(cd);
    const ascii = /filename="([^"]+)"/.exec(cd);
    const name = utf ? decodeURIComponent(utf[1]) : ascii ? ascii[1] : "My_CircuitPath.circuit";
    download(await res.blob(), name);
  } catch (err) {
    if (err.code !== "logged_out") messageBox({ kind: "error", instruction: "Your work couldn't be saved to a file.", text: err.message });
  }
}

/** Open my work: preview what would change, ask before replacing, then apply. */
async function openMyWork(input) {
  const file = input.files[0];
  input.value = "";
  if (!file) return;
  let preview;
  try {
    preview = await api.previewImport(file);
  } catch (err) {
    messageBox({ kind: "error", instruction: "That file can't be opened.", text: err.message });
    return;
  }
  const add = preview.changes.filter((c) => c.action === "add");
  const replace = preview.changes.filter((c) => c.action === "replace");
  const keep = preview.changes.filter((c) => c.action === "keep");
  if (!preview.same_name && preview.names?.length) {
    const go = await messageBox({
      kind: "question",
      instruction: `This file belongs to ${joinNames(preview.names)}.`,
      text: "Open it anyway?",
      buttons: [{ id: "yes", label: "Open it" }, { id: "no", label: "Cancel", default: true, cancel: true }],
    });
    if (go !== "yes") return;
  }
  if (add.length === 0 && replace.length === 0) {
    messageBox({ instruction: "Nothing new in that file.", text: keep.length ? "Your work here is the same or newer, so nothing was changed." : "The file has no projects in it." });
    return;
  }
  let doReplace = false;
  if (replace.length) {
    const titles = replace.map((c) => projectTitle(c.project_id));
    const answer = await messageBox({
      kind: "question",
      instruction: "Replace your work with the copy from the file?",
      text: [`The file has a newer copy of: ${titles.join(", ")}.`, "Replace your work here with the file's copy?"],
      buttons: [
        { id: "replace", label: "Replace" },
        { id: "keep", label: "Keep mine", default: true, cancel: true },
      ],
    });
    doReplace = answer === "replace";
  }
  try {
    const done = await api.applyImport(file, doReplace);
    const parts = [];
    if (done.added) parts.push(`${done.added} project${done.added === 1 ? "" : "s"} added`);
    if (done.replaced) parts.push(`${done.replaced} replaced`);
    messageBox({ instruction: "Your work is open.", text: parts.length ? `${parts.join(", ")}.` : "Nothing needed changing." });
    window.dispatchEvent(new CustomEvent("circuitpath:work-changed"));
  } catch (err) {
    messageBox({ kind: "error", instruction: "That file can't be opened.", text: err.message });
  }
}

function projectTitle(id) {
  if (id === "freeplay") return "Free Play";
  return state.catalogue.projects.find((p) => p.id === id)?.title ?? id;
}
