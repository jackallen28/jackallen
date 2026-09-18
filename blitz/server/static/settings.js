// Settings: the things you touch once in a while, kept off the pages you
// use every day. Subjects and their context documents, and backups.

const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function mb(bytes) {
  return bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

let data = null;

async function load() {
  data = await (await fetch("/api/settings")).json();
  $("#root").textContent = `Everything lives in ${data.root}`;
  $("#about").textContent = [
    `folder      ${data.root}`,
    `set up      ${data.setup.created_at || "unknown"} (${data.setup.mode || "?"})`,
    `subjects    ${data.subjects.map((s) => s.id).join(", ") || "none"}`,
  ].join("\n");

  $("#subjects").innerHTML = data.subjects.map(subjectCard).join("")
    || '<p class="hint">No subjects yet. Add one on the Index materials page.</p>';
  $("#backups").innerHTML = data.backups.length
    ? `<p class="hint" style="margin-top:10px">Recent backups: ${data.backups.map((b) =>
        `<a href="/backups/${encodeURIComponent(b.name)}">${esc(b.name)}</a> (${mb(b.bytes)})`).join(" · ")}</p>`
    : "";

  for (const el of document.querySelectorAll("[data-context-for]")) {
    el.onchange = () => upload(el.dataset.contextFor, el);
  }
  for (const el of document.querySelectorAll("[data-remove]")) {
    el.onclick = () => removeDoc(el.dataset.subject, el.dataset.remove);
  }
  for (const el of document.querySelectorAll("[data-clear-lexicon]")) {
    el.onclick = () => clearLexicon(el.dataset.clearLexicon);
  }
}

function subjectCard(s) {
  const lex = s.lexicon
    ? `<b>concept lexicon:</b> ${s.lexicon} of ${s.dot_points} dot points
       <button type="button" class="ghost" style="padding:2px 8px;font-size:12px"
               data-clear-lexicon="${esc(s.id)}">remove</button>`
    : `<b>concept lexicon:</b> none — tagging falls back on word overlap, which is weaker`;
  const docs = s.context.length
    ? `<ul class="files">${s.context.map((c) => `<li>${esc(c.name)} (${mb(c.bytes)})
        <button type="button" class="ghost" style="padding:1px 7px;font-size:12px"
                data-subject="${esc(s.id)}" data-remove="${esc(c.name)}">remove</button></li>`).join("")}</ul>`
    : '<p class="hint" style="margin:2px 0 0">No context documents yet.</p>';
  return `
  <div class="step" style="box-shadow:none;margin-bottom:12px">
    <b>${esc(s.name)}</b> <span class="hint" style="margin:0">· ${s.questions} questions ·
      ${s.covered} of ${s.dot_points} dot points covered${s.verified ? "" : " · draft wording"}</span>
    <p class="hint" style="margin:6px 0 0">${lex}</p>
    <p class="hint" style="margin:6px 0 0">Folder: <code>${esc(s.folder)}</code>
      (its dot points and indexing notes are in there)</p>
    ${docs}
    <div class="row" style="margin-top:8px">
      <a href="/api/subjects/${encodeURIComponent(s.id)}/briefing">
        <button type="button" class="ghost">Download briefing questions</button></a>
      <label class="check" style="display:flex;gap:6px;font-size:13px">Upload context document
        <input type="file" multiple accept=".md,.markdown,.txt,.yaml,.yml,.json"
               data-context-for="${esc(s.id)}"></label>
      <span class="hint" id="ctx-${esc(s.id)}" style="margin:0"></span>
    </div>
  </div>`;
}

async function upload(subjectId, input) {
  const out = $(`#ctx-${CSS.escape(subjectId)}`);
  if (!input.files.length) return;
  const fd = new FormData();
  for (const f of input.files) fd.append("files", f);
  out.textContent = "Reading…";
  const res = await fetch(`/api/subjects/${encodeURIComponent(subjectId)}/context`,
    { method: "POST", body: fd });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (_) {}
    out.textContent = msg;
    return;
  }
  const r = await res.json();
  const parts = [`Kept ${r.stored.length} document${r.stored.length === 1 ? "" : "s"}.`];
  if (r.lexicon) {
    parts.push(`Installed a concept lexicon covering ${r.lexicon.dot_points} dot points`
      + ` (${Math.round(r.lexicon.coverage * 100)}%).`);
    if (r.lexicon.unknown.length) {
      parts.push(`Ignored ${r.lexicon.unknown.length} id(s) this study design does not have.`);
    }
  }
  parts.push(...r.notes);
  out.textContent = parts.join(" ");
  const keep = out.textContent;
  await load();
  const again = $(`#ctx-${CSS.escape(subjectId)}`);
  if (again) again.textContent = keep;
}

async function removeDoc(subjectId, name) {
  if (!confirm(`Remove ${name}? Any lexicon it installed stays in use.`)) return;
  await fetch(`/api/subjects/${encodeURIComponent(subjectId)}/context/${encodeURIComponent(name)}`,
    { method: "DELETE" });
  load();
}

async function clearLexicon(subjectId) {
  if (!confirm("Remove this subject's concept lexicon? Tagging goes back to word "
    + "overlap with the study design's own wording, which is weaker.")) return;
  await fetch(`/api/subjects/${encodeURIComponent(subjectId)}/lexicon/clear`,
    { method: "POST" });
  load();
}

$("#backup").onclick = async () => {
  const btn = $("#backup");
  const out = $("#backup-result");
  btn.disabled = true;
  out.textContent = "Zipping…";
  try {
    const res = await fetch("/api/backup", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ include_sources: $("#withsources").checked }),
    });
    if (!res.ok) throw new Error(res.statusText);
    const d = await res.json();
    out.innerHTML = `Saved ${esc(d.summary)} — <a href="/backups/${encodeURIComponent(d.name)}">download it</a>`;
    load();
  } catch (e) {
    out.textContent = "Backup failed: " + e;
  } finally { btn.disabled = false; }
};

load();
