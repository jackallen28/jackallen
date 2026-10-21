// The About box.

import { h, icon } from "../dom.js";
import { openDialog } from "../widgets/window.js";
import { state } from "../state.js";

export function aboutContent() {
  return h("div", { class: "about" },
    h("div", { class: "about-head" },
      icon("app", "icon-48"),
      h("div", {},
        h("div", { class: "about-title", text: "CircuitPath" }),
        h("div", { class: "muted", text: `Version ${state.info?.version ?? ""}` }))),
    h("p", { text: "CircuitPath helps you learn to code Arduino and ESP boards, one part at a time." }),
    h("p", { text: "It was developed by the Banyule Nillumbik Tech School (BNTS) and reviewed by teachers." }),
    h("p", { text: "It is not hosted on AI. Every hint was written by people, and CircuitPath runs locally on your school's own server, so your work stays at school." }),
    h("p", { text: "CircuitPath aims to open up programming to every student by adapting to each student's needs." }));
}

export function showAbout() {
  let dlg;
  dlg = openDialog({
    title: "About CircuitPath",
    iconName: "about",
    content: aboutContent(),
    buttons: [h("button", { class: "btn default", type: "button", onclick: () => dlg.close() }, "OK")],
  });
  return dlg.result;
}
