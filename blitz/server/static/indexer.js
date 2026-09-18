// The "Index materials" page: pick a subject, drop files, press Index, watch it
// run, get a folder. Plain DOM, no framework, nothing leaves the machine.

const $ = (sel) => document.querySelector(sel);
const NEW = "__new__";

let subjects = [];
let root = "";

async function loadSubjects() {
  if (!root) {
    try { root = (await (await fetch("/api/root")).json()).root; } catch (_) {}
  }
  const res = await fetch("/api/subjects");
  const data = await res.json();
  subjects = data.subjects || [];
  const sel = $("#subject");
  sel.innerHTML = "";
  for (const s of subjects) {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.name + (s.verified ? "" : " (draft wording)");
    sel.appendChild(opt);
  }
  const opt = document.createElement("option");
  opt.value = NEW;
  opt.textContent = "New subject…";
  sel.appendChild(opt);
  onSubjectChange();
}

function onSubjectChange() {
  const id = $("#subject").value;
  const isNew = id === NEW;
  $("#newsubject").hidden = !isNew;
  const s = subjects.find((x) => x.id === id);
  // Every subject has a folder of its own holding its dot points and the
  // notes on preparing material; say where, because that is what someone
  // hands to whoever is doing the indexing.
  $("#briefing").href = isNew || !s
    ? "#" : `/api/subjects/${encodeURIComponent(s.id)}/briefing`;
  $("#briefing").style.opacity = isNew || !s ? 0.5 : 1;
  $("#folderhint").textContent = (isNew || !root || !s)
    ? ""
    : `You can also drop files straight into ${root}/sources/${s.id}/ — its `
      + `dot points and indexing notes are already in there.`;
  $("#designhint").textContent = isNew
    ? "Required for a new subject."
    : s && s.verified
      ? `${s.name} already has VCAA's wording imported. Leave this empty unless VCAA has published a new design.`
      : "This subject's wording is a draft. Upload VCAA's study design to replace it.";
}

function listFiles() {
  const ul = $("#filelist");
  ul.innerHTML = "";
  for (const f of $("#files").files) {
    const li = document.createElement("li");
    li.textContent = `${f.name} (${(f.size / 1048576).toFixed(1)} MB)`;
    ul.appendChild(li);
  }
}

function setStatus(text) { $("#status").textContent = text; }

async function submit(ev) {
  ev.preventDefault();
  const form = $("#form");
  const fd = new FormData();
  const id = $("#subject").value;
  if (id === NEW) {
    const name = $("#subject_name").value.trim();
    if (!name) { setStatus("Give the new subject a name."); return; }
    if (!$("#design").files.length) { setStatus("A new subject needs its study design."); return; }
    fd.append("subject_name", name);
  } else {
    fd.append("subject_id", id);
  }
  if ($("#design").files.length) fd.append("study_design", $("#design").files[0]);
  if (!$("#files").files.length && !$("#design").files.length
      && !$("#context").files.length) {
    setStatus("Choose at least one file."); return;
  }
  for (const f of $("#files").files) fd.append("files", f);
  for (const f of $("#context").files) fd.append("context", f);

  $("#go").disabled = true;
  $("#result").hidden = true;
  $("#progress").hidden = false;
  $("#log").textContent = "Uploading…";
  setStatus("");
  let res;
  try {
    res = await fetch("/api/index", { method: "POST", body: fd });
  } catch (e) {
    $("#log").textContent = "Upload failed: " + e;
    $("#go").disabled = false;
    return;
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (_) {}
    $("#log").textContent = "Could not start: " + msg;
    $("#go").disabled = false;
    return;
  }
  const { id: jobId } = await res.json();
  poll(jobId);
}

async function poll(jobId) {
  const res = await fetch(`/api/index/${jobId}`);
  if (!res.ok) { $("#log").textContent += "\nLost the job."; $("#go").disabled = false; return; }
  const job = await res.json();
  $("#log").textContent = job.log.join("\n");
  $("#log").scrollTop = $("#log").scrollHeight;
  if (job.status === "running" || job.status === "queued") {
    setTimeout(() => poll(jobId), 1000);
    return;
  }
  $("#go").disabled = false;
  if (job.status === "failed") {
    setStatus("Failed — see the log.");
    return;
  }
  const r = job.result;
  $("#r-q").textContent = r.questions;
  $("#r-p").textContent = r.passages;
  $("#r-f").textContent = r.figures;
  $("#r-folder").textContent = r.folder;
  $("#r-zip").href = r.zip ? `/exports/${r.zip}` : "#";
  $("#r-cov").textContent = r.coverage;
  $("#result").hidden = false;
  setStatus("Done.");
  // A new subject now exists; refresh the list so it can be picked again.
  loadSubjects();
  $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
}

$("#subject").addEventListener("change", onSubjectChange);
$("#files").addEventListener("change", listFiles);
$("#form").addEventListener("submit", submit);
loadSubjects();
