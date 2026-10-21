// What the app knows: the server's info, the content catalogue, and the
// logged-in student (null when nobody is logged in).

export const state = {
  info: null,
  catalogue: null,
  me: null, // { student, settings }
};

export function board(id = state.me?.settings.board) {
  return state.catalogue?.boards.find((b) => b.id === id) ?? null;
}

export function visibleBoards() {
  return (state.catalogue?.boards ?? []).filter((b) => !b.optional || b.id === state.me?.settings.board);
}

export function tier(id) {
  return state.catalogue?.tiers.find((t) => t.id === id) ?? null;
}

export function partName(type, count = 1) {
  const p = state.catalogue?.parts[type];
  if (!p) return type;
  return count === 1 ? p.name : `${count} ${p.plural}`;
}

/** Does a project's boards list include this board? */
export function projectSuits(project, b) {
  if (!b) return true;
  return project.boards.some((k) =>
    k === "all" || k === b.id || k === b.family || (k === "esp" && (b.family === "esp8266" || b.family === "esp32")));
}

/** What a project needs that isn't in the class kit (per board, for 2-board projects). */
export function missingFromKit(project) {
  const kit = state.catalogue?.kit?.parts ?? {};
  const perBoard = project.board_count || 1;
  return project.parts.filter((p) => (kit[p.type] ?? 0) < Math.ceil((p.count || 1) / perBoard));
}

/** "3 LEDs, 3 220Ω resistors and a push button" */
export function partsSummary(project) {
  const names = project.parts.map((p) => partName(p.type, p.count || 1));
  if (names.length === 0) return "No parts: screen only";
  if (names.length === 1) return names[0];
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}
