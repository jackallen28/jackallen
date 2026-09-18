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
  $("#designs").addEventListener("change", designRows);
  for (const btn of document.querySelectorAll("[data-mode]")) btn.onclick = () => go(btn.dataset.mode);
}

// A first guess at the subject's name from what the file is called; the
// server guesses the same way if this is left empty, but showing it means
// nobody ends up with a subject called "2023PhysicsSD".
function guessName(filename) {
  const stem = filename.replace(/\.[^.]+$/, "");
  const noise = new Set(["sd", "studydesign", "study", "design", "vcaa", "vce",
    "units", "unit", "final", "accredited", "curriculum", "adjusted"]);
  const words = stem.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/[-_]/g, " ")
    .split(/\s+/)
    .filter((w) => w && !/^(20\d{2}|\d{1,2})$/.test(w) && !noise.has(w.toLowerCase().replace(/\.$/, "")));
  const name = words.join(" ").trim();
  if (!name) return "New subject";
  return /[A-Z]/.test(name.slice(1)) ? name
    : name.replace(/\b\w/g, (c) => c.toUpperCase());
}

function designRows() {
  const files = [...$("#designs").files];
  $("#designrows").innerHTML = files.map((f, i) => `
    <div class="row" style="margin-top:6px">
      <span class="hint" style="margin:0;flex:1;min-width:140px">${esc(f.name)}</span>
      <input type="text" name="design_name" data-i="${i}" value="${esc(guessName(f.name))}"
             style="max-width:240px" aria-label="Subject name for ${esc(f.name)}">
    </div>`).join("");
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
    const files = [...$("#designs").files];
    const names = [...document.querySelectorAll('input[name="design_name"]')];
    files.forEach((f, i) => {
      fd.append("designs", f);
      fd.append("design_names", names[i] ? names[i].value.trim() : "");
    });
    if (!files.length && !document.querySelectorAll('input[name="subject"]:checked').length) {
      // Allowed, but say so: an empty index with no subjects does nothing yet.
      if (!confirm("No subjects chosen. Set up an empty Blitz anyway?")) return;
    }
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
