/* VCE Blitz — local UI. Talks only to the Python process on this machine. */

const state = {
  subjects: [],
  subject: null,
  kk: new Set(),
  types: new Set(),
};

const $ = (sel) => document.querySelector(sel);

async function boot() {
  const res = await fetch("/api/subjects");
  const data = await res.json();
  state.subjects = data.subjects;
  if (!state.subjects.length) {
    $("#banner").hidden = false;
    $("#banner").textContent =
      "No study designs installed. Run `blitz init` and restart.";
    return;
  }
  renderSubjects();
  selectSubject(state.subjects[0].id);
}

function renderSubjects() {
  const host = $("#subjects");
  host.innerHTML = "";
  for (const s of state.subjects) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.role = "radio";
    b.textContent = s.name;
    b.setAttribute("aria-pressed", "false");
    b.onclick = () => selectSubject(s.id);
    b.dataset.subject = s.id;
    host.appendChild(b);
  }
}

function selectSubject(id) {
  state.subject = state.subjects.find((s) => s.id === id);
  state.kk.clear();
  state.types.clear();
  document.querySelectorAll("[data-subject]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.subject === id)));
  renderBanner();
  renderTree();
  renderTypes();
  updateCount();
  $("#result").hidden = true;
}

function renderBanner() {
  const el = $("#banner");
  const s = state.subject;
  if (s.verified) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML =
    `<b>${s.name}: the study design has not been imported yet.</b> ` +
    "The dot points below were reconstructed by hand and are marked with a " +
    "<span style='color:#8a6d1f'>*</span>. Import the official VCAA PDF to " +
    "replace them:<br><code>blitz import-study-design &lt;pdf&gt; --subject " +
    `${s.id}</code>`;
}

function renderTree() {
  const host = $("#tree");
  host.innerHTML = "";
  for (const unit of state.subject.units) {
    const u = document.createElement("div");
    u.className = "unit";
    u.innerHTML = `<h3>Unit ${unit.number}: ${esc(unit.title)}</h3>`;
    for (const aos of unit.areas) {
      const box = document.createElement("div");
      box.className = "aos";
      const head = document.createElement("h4");
      head.innerHTML = `AOS ${aos.number}: ${esc(aos.title)}`;
      const pick = document.createElement("button");
      pick.type = "button";
      pick.className = "aosbtn";
      pick.textContent = "select all";
      pick.onclick = () => {
        const ids = aos.key_knowledge.map((k) => k.id);
        const allOn = ids.every((i) => state.kk.has(i));
        ids.forEach((i) => (allOn ? state.kk.delete(i) : state.kk.add(i)));
        syncChecks();
      };
      head.appendChild(pick);
      box.appendChild(head);
      if (aos.outcome) {
        const o = document.createElement("p");
        o.className = "outcome";
        o.textContent = aos.outcome;
        box.appendChild(o);
      }
      for (const kk of aos.key_knowledge) {
        const row = document.createElement("div");
        row.className = "kk" + (kk.available ? "" : " none");
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.id = kk.id;
        cb.dataset.kk = kk.id;
        cb.onchange = () => {
          cb.checked ? state.kk.add(kk.id) : state.kk.delete(kk.id);
          updateCount();
        };
        const label = document.createElement("label");
        label.htmlFor = kk.id;
        label.innerHTML = esc(kk.text) +
          (kk.verified ? "" : ' <span class="unverified" title="Wording not yet imported from the official VCAA study design">*</span>');
        const avail = document.createElement("span");
        avail.className = "avail";
        avail.textContent = kk.available;
        avail.title = `${kk.available} question(s) in the index`;
        row.append(cb, label, avail);
        box.appendChild(row);
      }
      u.appendChild(box);
    }
    host.appendChild(u);
  }
}

function renderTypes() {
  const host = $("#types");
  host.innerHTML = "";
  for (const qt of state.subject.question_types) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip" + (qt.available ? "" : " empty");
    b.title = qt.description + (qt.available ? "" : " — none in the index yet");
    b.innerHTML = `${esc(qt.label)}<span class="avail">${qt.available}</span>`;
    b.setAttribute("aria-pressed", "false");
    b.onclick = () => {
      state.types.has(qt.id) ? state.types.delete(qt.id) : state.types.add(qt.id);
      b.setAttribute("aria-pressed", String(state.types.has(qt.id)));
    };
    host.appendChild(b);
  }
}

function syncChecks() {
  document.querySelectorAll("[data-kk]").forEach((cb) => {
    cb.checked = state.kk.has(cb.dataset.kk);
  });
  updateCount();
}

function updateCount() {
  $("#kkcount").textContent = `${state.kk.size} selected`;
}

document.addEventListener("click", (e) => {
  const mode = e.target.dataset?.select;
  if (!mode || !state.subject) return;
  state.kk.clear();
  if (mode !== "none") {
    for (const u of state.subject.units) {
      for (const a of u.areas) {
        for (const kk of a.key_knowledge) {
          if (mode === "all" || kk.available > 0) state.kk.add(kk.id);
        }
      }
    }
  }
  syncChecks();
});

function payload() {
  return {
    subject_id: state.subject.id,
    kk_ids: [...state.kk],
    question_type_ids: [...state.types],
    notes: $("#notes").value,
    title: $("#title").value,
    difficulty: $("#difficulty").value,
    include_solutions: $("#solutions").checked,
    prefer_figures: $("#figures").checked,
    allow_generated: $("#generated").checked,
  };
}

async function post(url) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload()),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || "request failed");
  }
  return res.json();
}

$("#preview").onclick = async () => {
  if (!guard()) return;
  setStatus("Working out what fits…");
  try {
    const data = await post("/api/preview");
    showPreview(data);
    setStatus("");
  } catch (err) {
    setStatus(err.message);
  }
};

$("#generate").onclick = async () => {
  if (!guard()) return;
  const btn = $("#generate");
  btn.disabled = true;
  setStatus("Building your Blitz…");
  try {
    const data = await post("/api/generate");
    showSheet(data);
    setStatus("");
  } catch (err) {
    setStatus(err.message);
  } finally {
    btn.disabled = false;
  }
};

function guard() {
  if (state.kk.size) return true;
  setStatus("Pick at least one dot point first.");
  return false;
}

function setStatus(text) { $("#status").textContent = text; }

function showPreview(data) {
  const el = $("#result");
  el.hidden = false;
  el.innerHTML =
    `<h2>Preview</h2>
     <div class="summary">
       <div class="stat"><b>${data.count}</b>questions</div>
       <div class="stat"><b>${data.total_marks}</b>marks</div>
       <div class="stat"><b>${data.uncovered.length}</b>dot points with no room</div>
     </div>
     <ul class="qlist">${data.questions.map((q) =>
        `<li>${q.generated ? '<span class="gen">°</span> ' : ""}${esc(q.preview)}…
         <em>${esc(q.citation)}</em></li>`).join("")}</ul>
     ${warnList(data.warnings)}`;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showSheet(data) {
  const el = $("#result");
  el.hidden = false;
  el.innerHTML =
    `<h2>Your Blitz is ready</h2>
     <div class="summary">
       <div class="stat"><b>${data.questions}</b>questions</div>
       <div class="stat"><b>${data.total_marks}</b>marks</div>
       <div class="stat"><b>${data.question_pages}</b>pages of questions</div>
       <div class="stat"><b>${data.total_pages}</b>pages with solutions</div>
     </div>
     <p><a class="chip on" href="${data.url}" download>Download ${esc(data.filename)}</a></p>
     ${warnList(data.warnings)}
     <iframe src="${data.url}" title="Your Blitz"></iframe>`;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

function warnList(warnings) {
  if (!warnings || !warnings.length) return "";
  return `<ul>${warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>`;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

boot();
