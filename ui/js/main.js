// CircuitPath's web app: starts up, then shows the right screen for the
// address (#/projects, #/project/<id>, #/freeplay...).

import { api, onLoggedOut } from "./api.js";
import { h, clear, loadSprites } from "./dom.js";
import { state } from "./state.js";
import { messageBox } from "./widgets/window.js";
import { loginScreen } from "./screens/login.js";
import { setupScreen } from "./screens/setup.js";
import { pickerScreen } from "./screens/picker.js";
import { workspaceScreen } from "./screens/workspace.js";
import { openSettings } from "./dialogs/settings.js";

const root = document.getElementById("app");
let cleanup = null;
let routing = Promise.resolve();

function go(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}

async function leaveScreen() {
  const fn = cleanup;
  cleanup = null;
  if (fn) {
    try {
      await fn();
    } catch {
      // Leaving must never get stuck.
    }
  }
}

function route() {
  routing = routing.then(async () => {
    await leaveScreen();
    const hash = location.hash || "#/";
    if (!state.me) {
      if (hash !== "#/") history.replaceState(null, "", "#/");
      loginScreen(root, { onLoggedIn });
      return;
    }
    if (!state.me.settings.help_level && hash !== "#/setup") {
      go("#/setup");
      return;
    }
    const [, page, id] = hash.split("/");
    switch (page) {
      case "setup":
        setupScreen(root, { onDone: () => go("#/projects") });
        break;
      case "project":
      case "freeplay":
        cleanup = workspaceScreen(root, {
          projectId: page === "freeplay" ? "freeplay" : decodeURIComponent(id || ""),
          openSettings,
          back: () => go("#/projects"),
        });
        break;
      default:
        if (hash !== "#/projects") history.replaceState(null, "", "#/projects");
        cleanup = pickerScreen(root, {
          openSettings,
          logOut,
          openProject: (pid) => go(pid === "freeplay" ? "#/freeplay" : `#/project/${encodeURIComponent(pid)}`),
        });
    }
    document.title = "CircuitPath";
  });
  return routing;
}

function onLoggedIn(me) {
  state.me = me;
  go(me.settings.help_level ? "#/projects" : "#/setup");
}

async function logOut() {
  await leaveScreen();
  try {
    await api.logout();
  } catch {
    // Logged out on this laptop either way.
  }
  state.me = null;
  go("#/");
}

onLoggedOut(() => {
  if (!state.me) return;
  state.me = null;
  messageBox({ kind: "info", instruction: "Please log in again.", text: "You've been logged out. Your code is kept in this browser and will save after you log in." })
    .then(() => go("#/"));
});

async function start() {
  await loadSprites(["img/icons.svg", "img/pictures.svg"]);
  try {
    [state.info, state.catalogue] = await Promise.all([api.info(), api.catalogue()]);
  } catch (err) {
    clear(root).append(h("div", { class: "logon" },
      h("main", { class: "logon-stage" },
        h("h1", { text: "CircuitPath can't start" }),
        h("p", { class: "logon-lead", text: err.message }),
        h("button", { class: "pill", type: "button", onclick: () => location.reload() }, "Try again"))));
    return;
  }
  try {
    state.me = await api.me();
  } catch {
    state.me = null;
  }
  window.addEventListener("hashchange", route);
  route();
}

start();
