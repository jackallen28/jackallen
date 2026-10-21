// The picture-password grid (3 × 3 pictures) and the row of 3 slots that
// shows what has been tapped so far.

import { h, icon } from "../dom.js";
import { PICTURES, PICTURE_COUNT, pictureLabel } from "../pictures.js";

/**
 * pictureGrid({ onChange(picks), onComplete(picks) })
 * Returns { el, reset(), setDisabled(bool), shake() }.
 */
export function pictureGrid({ onChange = () => {}, onComplete = () => {}, label = "Pictures" } = {}) {
  let picks = [];
  let disabled = false;
  const slots = slotRow();
  const buttons = PICTURES.map((p) => {
    const b = h("button", {
      class: "picture",
      type: "button",
      "aria-pressed": "false",
      "aria-label": p.label,
      onclick: () => pick(p.id),
    }, icon(`p-${p.id}`, "picture-art"), h("span", { class: "picture-label", text: p.label }), h("span", { class: "picture-order" }));
    b.dataset.picture = p.id;
    return b;
  });
  const grid = h("div", { class: "picture-grid", role: "group", "aria-label": label }, buttons);
  const el = h("div", { class: "picture-pad" }, slots.el, grid);

  function render() {
    for (const b of buttons) {
      const i = picks.indexOf(b.dataset.picture);
      b.setAttribute("aria-pressed", i >= 0 ? "true" : "false");
      b.querySelector(".picture-order").textContent = i >= 0 ? String(i + 1) : "";
      b.disabled = disabled;
    }
    slots.update(picks);
  }

  function pick(id) {
    if (disabled || picks.length >= PICTURE_COUNT) return;
    if (picks.includes(id)) {
      // Tapping the last picture again takes it back.
      if (picks[picks.length - 1] === id) picks = picks.slice(0, -1);
    } else {
      picks = [...picks, id];
    }
    render();
    onChange(picks);
    if (picks.length === PICTURE_COUNT) onComplete(picks);
  }

  render();
  return {
    el,
    get picks() { return picks; },
    reset() { picks = []; render(); onChange(picks); },
    setDisabled(v) { disabled = v; render(); },
    shake() {
      el.classList.remove("shake");
      void el.offsetWidth;
      el.classList.add("shake");
    },
    focus() { buttons[0].focus(); },
  };
}

function slotRow() {
  const slots = Array.from({ length: PICTURE_COUNT }, (_, i) =>
    h("span", { class: "slot", "aria-label": `Picture ${i + 1}` }, h("span", { class: "slot-number", text: String(i + 1) })));
  const live = h("span", { class: "visually-hidden", "aria-live": "polite" });
  return {
    el: h("div", { class: "slots" }, slots, live),
    update(picks) {
      slots.forEach((s, i) => {
        s.replaceChildren(picks[i] ? icon(`p-${picks[i]}`, "slot-art") : h("span", { class: "slot-number", text: String(i + 1) }));
        s.classList.toggle("filled", Boolean(picks[i]));
      });
      live.textContent = picks.length ? `${picks.length} of ${PICTURE_COUNT}: ${picks.map(pictureLabel).join(", ")}` : "";
    },
  };
}
