// The WIPE page: deletes every profile on this laptop, with all their code
// and progress, ready for the next group. It offers to save everyone's work
// first, and only wipes after WIPE is typed.

import { api } from "../api.js";
import { h, icon, joinNames, clear, fill } from "../dom.js";
import { messageBox } from "../widgets/window.js";

export function wipeScreen(root, { onDone, onCancel }) {
  const body = h("div", { class: "wizard-page" });
  const buttons = h("div", { class: "dialog-buttons" });
  clear(root).append(h("div", { class: "logon" },
    h("main", { class: "logon-stage", id: "main" },
      h("section", { class: "window wizard wipe", "aria-labelledby": "wipe-title" },
        h("div", { class: "titlebar" }, icon("warn", "app-icon"), h("span", { class: "title", id: "wipe-title", text: "Wipe this laptop" })),
        h("div", { class: "window-body" }, body, buttons))),
    h("img", { class: "bnts-pixels", src: "img/bnts-pixels.svg", alt: "" })));

  async function load() {
    let students;
    try {
      students = await api.students();
    } catch (err) {
      fill(body, h("div", { class: "note error", role: "alert" }, icon("warn"), h("span", { text: err.message })));
      fill(buttons, h("button", { class: "btn default", type: "button", onclick: onCancel }, "Back"));
      return;
    }
    if (students.length === 0) {
      fill(body,
        h("h2", { text: "This laptop is already clear" }),
        h("p", { text: "There are no profiles on this laptop. It's ready for the next group." }));
      fill(buttons, h("button", { class: "btn default", type: "button", onclick: onCancel }, "Back"));
      buttons.querySelector("button").focus();
      return;
    }

    const confirm = h("input", {
      class: "input big", id: "wipe-confirm", autocomplete: "off", spellcheck: "false", maxlength: 10,
      oninput: () => { wipe.disabled = confirm.value !== "WIPE"; },
    });
    const wipe = h("button", { class: "btn danger", type: "button", disabled: true, onclick: doWipe }, "Wipe this laptop");
    fill(body,
      h("p", { text: "This deletes every profile on this laptop, with all their code and progress. Use it at the end of a program, before the next group." }),
      h("div", { class: "field" },
        h("label", { text: `Profiles on this laptop (${students.length})` }),
        h("ul", { class: "wipe-list" }, students.map((s) => h("li", { text: `${joinNames(s.names)}, ${s.school}` })))),
      h("div", { class: "field" },
        h("label", { text: "1. Save a copy first (a good idea)" }),
        h("p", { class: "small muted", text: "Downloads everyone's work as one zip. Each student can open their own .circuit file later with Settings > My work > Open my work." }),
        h("a", { class: "btn", href: api.everyoneExportUrl, download: "" }, icon("download"), " Save everyone's work")),
      h("div", { class: "field" },
        h("label", { for: "wipe-confirm", text: "2. Type WIPE in capital letters" }),
        confirm),
      h("div", { class: "note safety" }, icon("warn"), h("span", { text: "This can't be undone." })));
    fill(buttons, h("button", { class: "btn", type: "button", onclick: onCancel }, "Cancel"), wipe);
    confirm.focus();

    async function doWipe() {
      wipe.disabled = true;
      try {
        await api.wipe();
      } catch (err) {
        wipe.disabled = false;
        messageBox({ kind: "error", instruction: "The laptop wasn't wiped.", text: err.message });
        return;
      }
      await messageBox({ kind: "info", instruction: "This laptop is wiped.", text: "Every profile is gone. It's ready for the next group." });
      onDone();
    }
  }

  load();
}
