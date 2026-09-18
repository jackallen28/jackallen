// Questions: search by serial or words, see the question and its solution
// (text or the page crop), and flag it as incomplete, corrupt or wrong.

const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function boot() {
  const data = await (await fetch("/api/subjects")).json();
  const sel = $("#subject");
  for (const s of data.subjects) {
    const opt = document.createElement("option");
    opt.value = s.id; opt.textContent = s.name;
    sel.appendChild(opt);
  }
  const params = new URLSearchParams(location.search);
  if (params.get("subject")) sel.value = params.get("subject");
  if (params.get("q")) $("#q").value = params.get("q");
  if (params.get("flagged")) $("#flagged").checked = true;
  if (params.get("q") || params.get("flagged")) search();
}

async function search() {
  const params = new URLSearchParams({
    subject: $("#subject").value, q: $("#q").value.trim(),
    flagged: $("#flagged").checked ? "1" : "",
  });
  history.replaceState(null, "", "?" + params);
  $("#count").textContent = "Searching…";
  const res = await fetch("/api/questions?" + params);
  if (!res.ok) { $("#count").textContent = "Search failed."; return; }
  const data = await res.json();
  $("#count").textContent = data.total
    ? `${data.total} question${data.total === 1 ? "" : "s"}${data.total > data.questions.length ? `, showing the first ${data.questions.length}` : ""}`
    : "Nothing matched.";
  $("#results").innerHTML = data.questions.map(card).join("");
  for (const btn of document.querySelectorAll("[data-flag]")) btn.onclick = () => flag(btn);
}

function figures(list, role) {
  return list.filter((f) => f.role === role)
    .map((f) => `<img src="${f.url}" alt="" style="max-width:100%;border:1px solid var(--line);margin:6px 0;background:#fff">`)
    .join("");
}

function card(q) {
  const flagged = q.flag
    ? `<p class="hint" style="color:#a00"><b>Flagged ${esc(q.flag)}</b>${q.flag_note ? ": " + esc(q.flag_note) : ""} (${esc((q.flagged_at || "").slice(0, 10))})</p>`
    : "";
  const body = q.render_mode === "crop" && q.figures.some((f) => f.role === "question")
    ? figures(q.figures, "question")
    : `<p>${esc(q.context ? q.context + " " : "")}${esc(q.body)}</p>${figures(q.figures, "question")}`;
  const options = q.options ? `<ol type="A">${q.options.map((o) => `<li>${esc(o)}</li>`).join("")}</ol>` : "";
  const answer = q.answer_mode === "crop" && q.figures.some((f) => f.role === "answer")
    ? figures(q.figures, "answer")
    : (q.answer ? `<p>${esc(q.answer)}</p>${figures(q.figures, "answer")}` : "<p class=\"hint\">No worked solution in the source.</p>");
  return `
  <fieldset id="q-${esc(q.id)}">
    <legend>${esc(q.serial)} · ${esc(q.citation || q.source_id)}</legend>
    <p class="hint">${esc(q.type_label)} · ${q.marks ?? "?"} mark${q.marks === 1 ? "" : "s"} · ${q.kk.map(esc).join("; ")}${q.given ? ` · given ${q.given} time${q.given === 1 ? "" : "s"}` : ""}</p>
    ${flagged}
    ${body}${options}
    <details><summary><b>Worked solution</b></summary>${answer}</details>
    <div class="row" style="margin-top:10px">
      ${q.flag
        ? `<button type="button" class="ghost" data-flag="" data-id="${esc(q.id)}">Clear the flag</button>`
        : `<button type="button" class="ghost" data-flag="incomplete" data-id="${esc(q.id)}">Flag incomplete</button>
           <button type="button" class="ghost" data-flag="corrupt" data-id="${esc(q.id)}">Flag corrupt</button>
           <button type="button" class="ghost" data-flag="wrong" data-id="${esc(q.id)}">Flag wrong</button>`}
    </div>
  </fieldset>`;
}

async function flag(btn) {
  const id = btn.dataset.id;
  const value = btn.dataset.flag;
  let note = "";
  if (value) {
    note = prompt(`Flag ${id.split("-").slice(-1)} as ${value}. A note (optional):`, "") ;
    if (note === null) return;
  }
  const res = await fetch(`/api/questions/${encodeURIComponent(id)}/flag`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ flag: value || null, note }),
  });
  if (!res.ok) { alert("Could not save the flag."); return; }
  search();
}

$("#search").onclick = search;
$("#q").addEventListener("keydown", (e) => { if (e.key === "Enter") search(); });
$("#flagged").addEventListener("change", search);
boot();
