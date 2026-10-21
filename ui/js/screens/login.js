// The login screen, in the style of Vista's welcome screen:
// pick your class → pick your name (or make a new profile) → tap your pictures.

import { api } from "../api.js";
import { h, icon, joinNames, clear, fill } from "../dom.js";
import { pictureGrid } from "../widgets/pictures.js";
import { showAbout } from "../dialogs/about.js";
import { state } from "../state.js";

export function loginScreen(root, { onLoggedIn }) {
  const stage = h("main", { class: "logon-stage", id: "main" });
  const screen = h("div", { class: "logon" },
    h("header", { class: "logon-brand" },
      icon("app", "icon-48"),
      h("div", {},
        h("div", { class: "logon-title", text: "CircuitPath" }),
        h("div", { class: "logon-school", text: state.info?.school ?? "" }))),
    stage,
    h("footer", { class: "logon-footer" },
      h("button", { class: "logon-link", type: "button", onclick: showAbout }, icon("about"), " About CircuitPath")),
    h("img", { class: "bnts-pixels", src: "img/bnts-pixels.svg", alt: "" }));
  clear(root).append(screen);

  let classes = [];
  let classId = 0;
  let students = [];

  function show(...children) {
    fill(stage, ...children);
    const focus = stage.querySelector("[autofocus]") || stage.querySelector("button");
    if (focus) focus.focus();
  }

  function errorNote(err) {
    return h("div", { class: "logon-message", role: "alert" }, icon("warn"), h("span", { text: err.message }));
  }

  async function start() {
    try {
      classes = (await api.classes()).sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    } catch (err) {
      show(h("h1", { text: "Welcome!" }), errorNote(err), h("button", { class: "pill", onclick: start }, "Try again"));
      return;
    }
    if (classes.length === 0) {
      classId = 0;
      await pickName();
    } else {
      pickClass();
    }
  }

  function pickClass() {
    show(
      h("h1", { text: "Welcome!" }),
      h("p", { class: "logon-lead", text: "Pick your class." }),
      h("div", { class: "tiles" }, classes.map((c) =>
        h("button", { class: "tile class-tile", type: "button", onclick: () => { classId = c.id; pickName(c.name); } },
          h("span", { class: "tile-frame" }, icon("users", "icon-48")),
          h("span", { class: "tile-name", text: c.name })))));
  }

  async function pickName(className) {
    try {
      students = await api.students(classId);
    } catch (err) {
      show(h("h1", { text: "Who are you?" }), errorNote(err), backButton());
      return;
    }
    const tiles = students.map((s) =>
      h("button", { class: "tile user-tile", type: "button", onclick: () => enterPictures(s) },
        h("span", { class: "tile-frame" }, avatar(s.names)),
        h("span", { class: "tile-name", text: joinNames(s.names) }),
        h("span", { class: "tile-sub", text: s.school })));
    tiles.push(h("button", { class: "tile new-tile", type: "button", onclick: () => newProfile(className) },
      h("span", { class: "tile-frame" }, icon("plus", "icon-48")),
      h("span", { class: "tile-name", text: "I'm new here" }),
      h("span", { class: "tile-sub", text: "Make a profile" })));
    show(
      h("h1", { text: className ? `Who are you? (${className})` : "Who are you?" }),
      h("p", { class: "logon-lead", text: students.length ? "Pick your name. New? Make a profile." : "No one has made a profile here yet. Be the first!" }),
      h("div", { class: "tiles" }, tiles),
      classes.length ? backButton("Back to classes", pickClass) : null);
  }

  function backButton(label = "Back", onclick = start) {
    return h("button", { class: "logon-back", type: "button", onclick }, icon("back"), h("span", { text: label }));
  }

  function enterPictures(student) {
    const message = h("div", { class: "logon-message", role: "alert", hidden: true });
    let lockTimer = null;
    const grid = pictureGrid({
      label: "Your secret pictures",
      onChange: (picks) => { if (picks.length) message.hidden = true; },
      onComplete: async (picks) => {
        grid.setDisabled(true);
        try {
          const me = await api.login(student.id, picks);
          onLoggedIn(me);
        } catch (err) {
          grid.reset();
          grid.shake();
          message.replaceChildren(icon("warn"), h("span", { text: err.message }));
          message.hidden = false;
          if (err.code === "locked") {
            clearTimeout(lockTimer);
            lockTimer = setTimeout(() => { grid.setDisabled(false); message.hidden = true; }, err.retryAfter * 1000);
          } else {
            grid.setDisabled(false);
          }
        }
      },
    });
    show(
      h("div", { class: "who" },
        h("span", { class: "tile-frame big" }, avatar(student.names)),
        h("div", {},
          h("h1", { text: `Hi ${joinNames(student.names)}!` }),
          h("p", { class: "logon-lead", text: "Tap your 3 secret pictures, in order." }))),
      grid.el,
      message,
      h("p", { class: "logon-hint", text: "Forgotten your pictures? Your teacher can reset them." }),
      backButton("Not you? Go back", () => { clearTimeout(lockTimer); pickName(); }));
    grid.focus();
  }

  function newProfile(className) {
    newProfileWizard(stage, {
      classId,
      className,
      schools: [...new Set(students.map((s) => s.school))],
      onCancel: () => pickName(className),
      onCreated: onLoggedIn,
    });
  }

  start();
}

/** Initials in a coloured circle, for a user tile. */
export function avatar(names) {
  const initials = names.map((n) => [...n][0]).join("").slice(0, 4).toUpperCase();
  const hue = [...names.join("")].reduce((a, c) => (a * 31 + c.codePointAt(0)) % 360, 7);
  const el = h("span", { class: `avatar avatar-${initials.length}`, "aria-hidden": "true", text: initials });
  el.style.setProperty("--avatar-hue", String(hue));
  return el;
}

/** The "I'm new here" wizard: names and school → pick pictures → tap them again. */
function newProfileWizard(stage, { classId, className, schools, onCancel, onCreated }) {
  const names = [""];
  let school = "";
  let chosen = [];
  const pageHolder = h("div", { class: "wizard-page" });
  const dots = h("ol", { class: "step-dots", "aria-label": "Steps" });
  const buttons = h("div", { class: "dialog-buttons" });
  const win = h("section", { class: "window wizard", "aria-labelledby": "wizard-title" },
    h("div", { class: "titlebar" }, icon("user", "app-icon"), h("span", { class: "title", id: "wizard-title", text: "Make your profile" })),
    h("div", { class: "window-body" }, dots, pageHolder, buttons));
  clear(stage).append(win);

  function setPage(n, content, btns) {
    fill(dots, ...["Your names", "Pick pictures", "Check them"].map((label, i) =>
      h("li", { class: i === n ? "current" : i < n ? "done" : "", "aria-current": i === n ? "step" : null },
        h("span", { class: "visually-hidden", text: label }))));
    fill(pageHolder, content);
    fill(buttons, btns);
    const focus = pageHolder.querySelector("[autofocus]") || pageHolder.querySelector("input, button");
    if (focus) focus.focus();
  }

  function pageNames(error) {
    const list = h("div", { class: "name-list" });
    const schoolInput = h("input", {
      class: "input big", id: "school", list: "school-list", autocomplete: "off", maxlength: 60, value: school,
      oninput: (e) => { school = e.target.value; },
    });
    function renderNames() {
      fill(list, names.map((n, i) => h("div", { class: "name-row" },
        h("input", {
          class: "input big", value: n, maxlength: 30, autocomplete: "off", spellcheck: "false",
          "aria-label": i === 0 ? "First name" : `First name ${i + 1}`, autofocus: i === names.length - 1 ? true : null,
          oninput: (e) => { names[i] = e.target.value; },
        }),
        names.length > 1 ? h("button", {
          class: "btn remove-name", type: "button", "aria-label": "Remove this name", title: "Remove",
          onclick: () => { names.splice(i, 1); renderNames(); },
        }, "✕") : null)));
      addBtn.hidden = names.length >= 4;
    }
    const addBtn = h("button", { class: "link-button", type: "button", onclick: () => { names.push(""); renderNames(); list.querySelector("div:last-child input").focus(); } },
      "+ Add another name (sharing a kit)");
    renderNames();
    const form = h("form", {
      id: "names-form",
      onsubmit: (e) => {
        e.preventDefault();
        const filled = names.map((n) => n.trim()).filter(Boolean);
        if (filled.length === 0) return pageNames("Type your first name.");
        if (!school.trim()) return pageNames("Type your school's name.");
        names.splice(0, names.length, ...filled);
        pagePictures();
      },
    },
    h("h2", { text: className ? `Welcome to ${className}!` : "Welcome!" }),
    h("div", { class: "field" },
      h("label", { text: "Your first name" }),
      list,
      h("div", { class: "small muted", text: "Just first names, no last names. Sharing a laptop and kit? Add everyone's first name (up to 4)." }),
      addBtn),
    h("div", { class: "field" },
      h("label", { for: "school", text: "Your school" }),
      schoolInput,
      h("datalist", { id: "school-list" }, schools.map((s) => h("option", { value: s })))),
    error ? h("div", { class: "note error", role: "alert" }, icon("warn"), h("span", { text: error })) : null);
    setPage(0, form, [
      h("button", { class: "btn", type: "button", onclick: onCancel }, "Back"),
      h("button", { class: "btn default", type: "submit", form: "names-form" }, "Next"),
    ]);
  }

  function pagePictures(error) {
    const next = h("button", { class: "btn default", type: "button", disabled: true, onclick: () => pageConfirm() }, "Next");
    const grid = pictureGrid({
      label: "Pick 3 secret pictures",
      onChange: (picks) => { chosen = picks; next.disabled = picks.length < 3; },
    });
    setPage(1, [
      h("h2", { text: "Pick your secret pictures" }),
      h("p", { text: "Pick 3 pictures, in order. You'll tap them each time you log in, so remember them! Keep them secret from your classmates." }),
      error ? h("div", { class: "note error", role: "alert" }, icon("warn"), h("span", { text: error })) : null,
      grid.el,
    ], [
      h("button", { class: "btn", type: "button", onclick: () => pageNames() }, "Back"),
      next,
    ]);
  }

  function pageConfirm(error) {
    const message = h("div", { class: "note error", role: "alert", hidden: !error }, icon("warn"), h("span", { text: error || "" }));
    const grid = pictureGrid({
      label: "Tap your pictures again",
      onComplete: async (picks) => {
        if (picks.join() !== chosen.join()) {
          pagePictures("Those didn't match. Pick 3 pictures again.");
          return;
        }
        grid.setDisabled(true);
        try {
          const me = await api.createStudent({ class_id: classId, names, school: school.trim(), pictures: chosen });
          onCreated(me);
        } catch (err) {
          if (err.code === "bad_names" || err.code === "bad_school" || err.code === "exists") {
            pageNames(err.message);
          } else {
            pageConfirm(err.message);
          }
        }
      },
    });
    setPage(2, [
      h("h2", { text: "Tap them again" }),
      h("p", { text: "Tap your 3 pictures again, in the same order, to check you remember them." }),
      message,
      grid.el,
    ], [
      h("button", { class: "btn", type: "button", onclick: () => pagePictures() }, "Back"),
    ]);
  }

  pageNames();
}
