/* VCE Blitz — local UI. Talks only to the Python process on this machine. */

const state = {
  subjects: [],
  subject: null,
  kk: new Set(),
  types: new Set(),
  // Questions chosen by hand in browse mode, id -> the question, in the
  // order they were picked.
  pinned: new Map(),
};

const $ = (sel) => document.querySelector(sel);

async function boot() {
  loadStudents();
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
  if (state.subject && state.subject.id !== id) {
    state.pinned.clear();
    $("#browse").hidden = true;
    renderPicked();
  }
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
        if (kk.available) {
          const browse = document.createElement("button");
          browse.type = "button";
          browse.className = "kkbtn";
          browse.textContent = "browse";
          browse.title = "Look through this dot point's questions and pick by hand";
          browse.onclick = () => openBrowse(kk);
          row.appendChild(browse);
        }
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
  const picked = state.pinned.size
    ? `, ${state.pinned.size} question${state.pinned.size === 1 ? "" : "s"} chosen by hand`
    : "";
  $("#kkcount").textContent = `${state.kk.size} selected${picked}`;
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

// ---- Browse mode: flick through one dot point's questions ----------------
const browse = { kk: null, items: [], at: 0 };

function currentStudent() {
  const v = $("#student").value;
  return v && v !== "__new__" ? v : "";
}

async function openBrowse(kk) {
  browse.kk = kk;
  browse.items = [];
  browse.at = 0;
  $("#browse").hidden = false;
  $("#browse-title").textContent = kk.text.length > 90
    ? kk.text.slice(0, 90) + "…" : kk.text;
  $("#browse-count").textContent = "Loading…";
  $("#browse-body").innerHTML = "";
  const params = new URLSearchParams({
    subject: state.subject.id, kk: kk.id, limit: "200",
  });
  const student = currentStudent();
  if (student) params.set("student", student);
  const res = await fetch("/api/questions?" + params);
  if (!res.ok) { $("#browse-count").textContent = "Could not load."; return; }
  browse.items = (await res.json()).questions;
  // Anything already picked, and anything the student has had, sorted last:
  // the point of browsing is to find something new.
  browse.items.sort((a, b) => (a.already_given ? 1 : 0) - (b.already_given ? 1 : 0));
  showBrowse();
  $("#browse").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function figures(list, role) {
  return list.filter((f) => f.role === role)
    .map((f) => `<img src="${f.url}" alt="">`).join("");
}

function showBrowse() {
  const body = $("#browse-body");
  if (!browse.items.length) {
    $("#browse-count").textContent = "";
    body.innerHTML = '<p class="hint">No questions for this dot point.</p>';
    $("#browse-pick").disabled = true;
    return;
  }
  const q = browse.items[browse.at];
  $("#browse-count").textContent = `${browse.at + 1} of ${browse.items.length}`;
  const picked = state.pinned.has(q.id);
  $("#browse-pick").disabled = false;
  $("#browse-pick").textContent = picked ? "Remove from sheet" : "Add to sheet";
  const flags = [];
  if (q.already_given) flags.push('<span class="warn">already given to this student</span>');
  if (q.pinned) flags.push("on the sheet");
  const shown = q.render_mode === "crop" && q.figures.some((f) => f.role === "question")
    ? figures(q.figures, "question")
    : `<p>${esc(q.context ? q.context + " " : "")}${esc(q.body)}</p>${figures(q.figures, "question")}`;
  const options = q.options
    ? `<ol type="A">${q.options.map((o) => `<li>${esc(o)}</li>`).join("")}</ol>` : "";
  body.innerHTML = `
    <p class="meta"><b>${esc(q.serial || "")}</b> · ${esc(q.type_label)} ·
      ${q.marks ?? "?"} mark${q.marks === 1 ? "" : "s"} · ${esc(q.citation || q.source_id)}
      ${flags.length ? " · " + flags.join(" · ") : ""}</p>
    ${shown}${options}
    <details><summary>Worked solution</summary>${
      q.answer_mode === "crop" && q.figures.some((f) => f.role === "answer")
        ? figures(q.figures, "answer")
        : (q.answer ? `<p>${esc(q.answer)}</p>` : '<p class="hint">None in the source.</p>')
    }</details>`;
}

function step(by) {
  if (!browse.items.length) return;
  browse.at = (browse.at + by + browse.items.length) % browse.items.length;
  showBrowse();
}

function togglePick() {
  const q = browse.items[browse.at];
  if (!q) return;
  if (state.pinned.has(q.id)) state.pinned.delete(q.id);
  else state.pinned.set(q.id, q);
  renderPicked();
  showBrowse();
}

function renderPicked() {
  const box = $("#picked");
  const list = $("#picked-list");
  box.hidden = state.pinned.size === 0;
  list.innerHTML = [...state.pinned.values()].map((q) => `
    <li><span><b>${esc(q.serial || "")}</b> ${esc((q.body || "").slice(0, 90))}…</span>
      <button type="button" class="kkbtn" data-unpick="${esc(q.id)}">remove</button></li>`).join("");
  for (const btn of list.querySelectorAll("[data-unpick]")) {
    btn.onclick = () => {
      state.pinned.delete(btn.dataset.unpick);
      renderPicked();
      if (!$("#browse").hidden) showBrowse();
    };
  }
  updateCount();
}

$("#browse-prev").onclick = () => step(-1);
$("#browse-next").onclick = () => step(1);
$("#browse-pick").onclick = togglePick;
$("#browse-close").onclick = () => { $("#browse").hidden = true; };

async function loadStudents() {
  const res = await fetch("/api/students");
  if (!res.ok) return;
  const data = await res.json();
  const sel = $("#student");
  sel.innerHTML = '<option value="">Nobody in particular</option>';
  for (const s of data.students) {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = `${s.name} (${s.questions} question${s.questions === 1 ? "" : "s"} so far)`;
    sel.appendChild(opt);
  }
  const opt = document.createElement("option");
  opt.value = "__new__";
  opt.textContent = "New student or class…";
  sel.appendChild(opt);
  const wanted = new URLSearchParams(location.search).get("student");
  if (wanted && data.students.some((s) => s.id === wanted)) sel.value = wanted;
  sel.onchange = () => { $("#newstudent").hidden = sel.value !== "__new__"; };
}

function payload() {
  const student = $("#student").value;
  return {
    subject_id: state.subject.id,
    student_id: student && student !== "__new__" ? student : null,
    student_name: student === "__new__" ? $("#student_name").value.trim() || null : null,
    allow_repeats: $("#repeats").checked,
    pinned_question_ids: [...state.pinned.keys()],
    kk_ids: [...state.kk],
    question_type_ids: [...state.types],
    notes: $("#notes").value,
    title: $("#title").value,
    length: $("#length").value,
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
    setStatus(data.student ? `Logged against ${data.student.name}.` : "");
    if (data.student) {
      await loadStudents();
      $("#student").value = data.student.id;
      $("#newstudent").hidden = true;
    }
  } catch (err) {
    setStatus(err.message);
  } finally {
    btn.disabled = false;
  }
};

function guard() {
  if (state.kk.size || state.pinned.size) return true;
  setStatus("Pick at least one dot point, or choose a question by hand.");
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
        `<li>${q.generated ? '<span class="gen">°</span> ' : ""}<b>${esc(q.serial || "")}</b> ${esc(q.preview)}…
         <em>${esc(q.citation)}</em></li>`).join("")}</ul>
     ${warnList(data.warnings)}`;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showSheet(data) {
  const el = $("#result");
  el.hidden = false;
  const columns = data.columns === 1
    ? " · single column (page crops)"
    : data.wide ? ` · page 2: ${data.wide} full-width page extract${data.wide === 1 ? "" : "s"}` : "";
  el.innerHTML =
    `<h2>Your Blitz is ready</h2>
     <div class="summary">
       <div class="stat"><b>${data.questions}</b>questions</div>
       <div class="stat"><b>${data.total_marks}</b>marks</div>
       <div class="stat"><b>${data.question_pages}</b>pages of questions</div>
       <div class="stat"><b>${data.total_pages}</b>${data.solutions === false ? "pages total" : "pages with solutions"}</div>
     </div>
     <div class="viewer-bar">
       <a class="chip on" href="${data.url}?download=1" download>Download PDF</a>
       <a class="chip" href="${data.url}" target="_blank" rel="noopener">Open in a new tab</a>
       <button type="button" class="chip" id="printsheet">Print</button>
       <span class="count">${esc(data.filename)}${columns}</span>
     </div>
     ${warnList(data.warnings)}
     <iframe id="sheetview" src="${data.url}#view=FitH" title="Your Blitz"></iframe>`;
  // Printing goes through the viewer so the sheet prints, not the page around it.
  $("#printsheet").onclick = () => {
    const frame = $("#sheetview");
    try {
      frame.contentWindow.focus();
      frame.contentWindow.print();
    } catch {
      window.open(`${data.url}`, "_blank", "noopener");
    }
  };
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
