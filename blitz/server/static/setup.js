// First run: restore a backup, keep an index that is already here, or start
// from scratch with the shipped study designs as optional starters.

const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function boot() {
  const st = await (await fetch("/api/status")).json();
  if (st.set_up) { location.href = "/"; return; }
  $("#root").textContent = st.root;
  $("#shipped").innerHTML = st.shipped.map((s) => `
    <label class="check" style="display:flex;gap:6px;margin-top:6px">
      <input type="checkbox" name="subject" value="${esc(s.id)}" checked>
      ${esc(s.name)} <span class="hint" style="margin:0">· ${s.dot_points} dot points${s.lexicon ? ", concept lexicon included" : ""}</span>
    </label>`).join("") || '<p class="hint">No study designs ship with this copy; upload one on the Index materials page after setup.</p>';
  if (st.existing.index) {
    $("#adopt").hidden = false;
    $("#adopt-text").textContent =
      `An index is already in this folder: ${st.existing.questions} questions` +
      (st.existing.subjects.length ? ` (${st.existing.subjects.join(", ")})` : "") +
      `, ${st.existing.students} students. It was made before this setup page existed.`;
    $("#replace-wrap").hidden = false;
    $("#erase-wrap").hidden = false;
  }
  for (const btn of document.querySelectorAll("[data-mode]")) btn.onclick = () => go(btn.dataset.mode);
}

async function go(mode) {
  const fd = new FormData();
  fd.append("mode", mode);
  if (mode === "restore") {
    if (!$("#zip").files.length) { $("#status").textContent = "Choose the backup zip first."; return; }
    fd.append("backup", $("#zip").files[0]);
    fd.append("replace", $("#replace").checked ? "1" : "");
  } else if (mode === "scratch") {
    for (const c of document.querySelectorAll('input[name="subject"]:checked')) fd.append("subjects", c.value);
    fd.append("samples", $("#samples").checked ? "1" : "");
    fd.append("erase", $("#erase").checked ? "1" : "");
  }
  for (const b of document.querySelectorAll("[data-mode]")) b.disabled = true;
  $("#status").textContent = mode === "restore" ? "Restoring…" : "Setting up…";
  try {
    const res = await fetch("/api/setup", { method: "POST", body: fd });
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).detail || msg; } catch (_) {}
      throw new Error(msg);
    }
    $("#status").textContent = "Done. Opening Blitz…";
    location.href = "/";
  } catch (e) {
    $("#status").textContent = "Could not set up: " + e.message;
    for (const b of document.querySelectorAll("[data-mode]")) b.disabled = false;
  }
}

boot();
