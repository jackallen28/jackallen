// Students: the list, one student's sheets and questions, and the workbooks.

const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function loadList() {
  const data = await (await fetch("/api/students")).json();
  $("#where").textContent = `Workbooks are rewritten after every Blitz, in ${data.folder}`;
  if (!data.students.length) {
    $("#list").innerHTML = '<p class="hint">No students or classes yet. Add one here, or name one when you make a Blitz.</p>';
    return;
  }
  $("#list").innerHTML = `<table style="width:100%;border-collapse:collapse;font-size:14px">
    <tr style="text-align:left"><th>Name</th><th>Sheets</th><th>Questions</th><th>Last sheet</th></tr>
    ${data.students.map((s) => `<tr style="border-top:1px solid var(--line)">
      <td><a href="#" data-id="${esc(s.id)}">${esc(s.name)}</a></td>
      <td>${s.sheets}</td><td>${s.questions}</td><td>${esc((s.last || "").slice(0, 10))}</td></tr>`).join("")}
  </table>`;
  for (const a of document.querySelectorAll("#list a[data-id]")) {
    a.onclick = (e) => { e.preventDefault(); show(a.dataset.id); };
  }
  const params = new URLSearchParams(location.search);
  if (params.get("id")) show(params.get("id"));
}

async function show(id) {
  const res = await fetch(`/api/students/${encodeURIComponent(id)}`);
  if (!res.ok) return;
  const s = await res.json();
  history.replaceState(null, "", "?id=" + encodeURIComponent(id));
  $("#detail").hidden = false;
  $("#detail-name").textContent = s.name;
  $("#wb").href = `/students/files/${encodeURIComponent(s.workbook)}`;
  $("#make").href = `/blitz?student=${encodeURIComponent(s.id)}`;
  if (!s.sheets.length) {
    $("#sheets").innerHTML = '<p class="hint">No sheets yet.</p>';
    return;
  }
  $("#sheets").innerHTML = s.sheets.map((sh) => `
    <details open style="margin-top:10px">
      <summary><b>${esc(sh.title)}</b> · ${esc(sh.created_at.slice(0, 16).replace("T", " "))} · ${sh.questions.length} questions
        ${sh.url ? ` · <a href="${sh.url}" target="_blank" rel="noopener">open PDF</a>` : ""}</summary>
      <ol style="font-size:13.5px">
        ${sh.questions.map((q) => `<li><a href="/questions?subject=${esc(sh.subject_id)}&q=${esc(q.serial)}">${esc(q.serial)}</a>
          · ${esc(q.citation)} · ${q.kk.map(esc).join("; ")}</li>`).join("")}
      </ol>
    </details>`).join("");
}

$("#add").onclick = async () => {
  const name = $("#newname").value.trim();
  if (!name) return;
  const res = await fetch("/api/students", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) { alert("Could not add."); return; }
  $("#newname").value = "";
  loadList();
};

loadList();
