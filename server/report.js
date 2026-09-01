/**
 * Builds the teacher's downloadable round report.
 *
 * Two formats from the same data: a self-contained HTML page (opens in any
 * browser, prints to PDF, no assets to lose) and a CSV row per student for a
 * gradebook or spreadsheet.
 */
import { modelLabel } from './models.js';

const escapeHtml = (value) =>
  String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

const stamp = (ms) => (ms ? new Date(ms).toLocaleString() : '—');
const clock = (ms) =>
  ms ? new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
const pct = (value) => (value === null || value === undefined ? '—' : `${value}%`);

/** `2026-09-01_1423` — safe in a filename on any OS. */
export function reportFilename(data, extension) {
  const when = new Date(data.generatedAt || Date.now());
  const pad = (n) => String(n).padStart(2, '0');
  const date = `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`;
  const time = `${pad(when.getHours())}${pad(when.getMinutes())}`;
  return `human-or-not_round-${data.roundNumber}_${date}_${time}.${extension}`;
}

/** One row per student, for a spreadsheet. */
export function buildCsvReport(data) {
  const cell = (value) => {
    const text = String(value ?? '');
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };

  // Joined with " | " rather than newlines: embedded newlines are legal CSV but
  // make each record span several physical lines, which trips up simpler importers.
  const transcriptFor = (code) => {
    const conv = data.transcripts.find((c) => c.members.includes(code));
    if (!conv) return '';
    return conv.messages.map((m) => `${m.sender}: ${m.text}`).join(' | ');
  };

  const header = [
    'student', 'partner_type', 'model', 'partner', 'messages_sent',
    'their_answer', 'correct', 'bot_turns', 'tokens_in', 'tokens_out', 'transcript',
  ];

  const rows = data.students
    .filter((student) => student.inRound)
    .map((student) => {
      const conv = data.transcripts.find((c) => c.members.includes(student.code));
      return [
        student.code,
        student.partnerType === 'ai' ? 'AI' : 'peer',
        student.model || '',
        student.partner || '',
        student.messagesSent,
        student.guess ? (student.guess === 'ai' ? 'AI' : 'peer') : 'no answer',
        student.correct === null ? '' : student.correct ? 'correct' : 'wrong',
        conv?.botTurns ?? '',
        conv?.tokensIn ?? '',
        conv?.tokensOut ?? '',
        transcriptFor(student.code),
      ];
    });

  return [header, ...rows].map((row) => row.map(cell).join(',')).join('\n');
}

function modelTable(data) {
  if (!data.byModel.length) return '<p class="muted">No AI partners in this round.</p>';

  const rows = data.byModel
    .slice()
    .sort((a, b) => (b.foolRate ?? -1) - (a.foolRate ?? -1))
    .map(
      (row) => `<tr>
        <td><strong>${escapeHtml(row.label)}</strong><div class="sub">${escapeHtml(row.id)}</div></td>
        <td>${row.students}</td>
        <td>${row.answered}</td>
        <td>${row.fooled}</td>
        <td>${row.caught}</td>
        <td class="lead">${pct(row.foolRate)}</td>
        <td>${row.botTurns}</td>
        <td>${row.tokensIn.toLocaleString()} / ${row.tokensOut.toLocaleString()}</td>
        <td>$${row.costUsd.toFixed(4)}</td>
      </tr>`
    )
    .join('');

  return `<table>
    <thead><tr>
      <th>Model</th><th>Students</th><th>Answered</th><th>Believed it was human</th>
      <th>Identified as AI</th><th>Fooled&nbsp;rate</th><th>Bot turns</th>
      <th>Tokens in / out</th><th>Est. cost</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>
  <p class="note"><strong>Fooled rate</strong> is the share of students who faced that model and
  believed they were talking to a classmate. Higher means the model was more convincing.</p>`;
}

function studentTable(data) {
  const rows = data.students
    .filter((student) => student.inRound)
    .map(
      (student) => `<tr>
        <td><strong>${escapeHtml(student.code)}</strong></td>
        <td>${student.partnerType === 'ai'
          ? `<span class="tag ai">AI</span> ${escapeHtml(student.modelLabel || '')}`
          : `<span class="tag human">Peer</span> ${escapeHtml(student.partner || '')}`}</td>
        <td>${student.messagesSent}</td>
        <td>${student.guess ? (student.guess === 'ai' ? 'AI bot' : 'Classmate') : '<span class="muted">no answer</span>'}</td>
        <td>${student.correct === null
          ? '<span class="muted">—</span>'
          : student.correct
            ? '<span class="tag good">Correct</span>'
            : '<span class="tag bad">Wrong</span>'}</td>
      </tr>`
    )
    .join('');

  return `<table>
    <thead><tr><th>Student</th><th>Paired with</th><th>Messages</th><th>Their answer</th><th>Result</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function transcriptSection(data) {
  if (!data.transcripts.length) return '<p class="muted">No conversations recorded.</p>';

  return data.transcripts
    .map((conv) => {
      const title =
        conv.type === 'ai'
          ? `${escapeHtml(conv.members[0])} &harr; ${escapeHtml(conv.modelLabel || 'AI')}`
          : conv.members.map(escapeHtml).join(' &harr; ');
      const tag =
        conv.type === 'ai'
          ? `<span class="tag ai">AI · ${escapeHtml(conv.modelLabel || '')}</span>`
          : '<span class="tag human">Peer pair</span>';

      const meta =
        conv.type === 'ai'
          ? `<div class="sub">${conv.botTurns} bot turns · ${conv.tokensIn.toLocaleString()} in / ${conv.tokensOut.toLocaleString()} out tokens</div>`
          : '';

      const lines = conv.messages.length
        ? conv.messages
            .map(
              (m) => `<div class="line${m.isBot ? ' bot' : ''}">
                <span class="who">${escapeHtml(m.sender)}</span>
                <span class="time">${clock(m.ts)}</span>
                <span class="text">${escapeHtml(m.text)}</span>
              </div>`
            )
            .join('')
        : '<div class="line muted">No messages were sent.</div>';

      return `<section class="conv">
        <h3>${title} ${tag}</h3>${meta}
        <div class="lines">${lines}</div>
      </section>`;
    })
    .join('');
}

/** A standalone HTML page — no external assets, safe to email or print. */
export function buildHtmlReport(data) {
  const s = data.stats;
  const mix = Object.entries(data.modelMix || {})
    .map(([id, weight]) => `${escapeHtml(modelLabel(id))} (${weight})`)
    .join(', ') || '—';

  const totalCost = data.byModel.reduce((sum, row) => sum + row.costUsd, 0);

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Human or Not? — round ${data.roundNumber} report</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 32px; background: #f6f7f9; color: #14181f;
         font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  .page { max-width: 1000px; margin: 0 auto; }
  h1 { font-size: 1.65rem; margin: 0 0 4px; }
  h2 { font-size: 1.15rem; margin: 32px 0 12px; padding-bottom: 6px; border-bottom: 2px solid #e3e6ea; }
  h3 { font-size: 1rem; margin: 0 0 2px; }
  .muted { color: #6b7480; }
  .sub { font-size: .8rem; color: #6b7480; }
  .note { font-size: .85rem; color: #6b7480; margin-top: 8px; }
  .card { background: #fff; border: 1px solid #e3e6ea; border-radius: 10px; padding: 18px; }
  .meta { display: flex; flex-wrap: wrap; gap: 20px; font-size: .88rem; color: #4a525e; margin-top: 10px; }
  .tiles { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0 0; }
  .tile { flex: 1 1 130px; background: #fff; border: 1px solid #e3e6ea; border-radius: 10px; padding: 14px 16px; }
  .tile .n { font-size: 1.7rem; font-weight: 700; font-variant-numeric: tabular-nums; }
  .tile .k { font-size: .72rem; text-transform: uppercase; letter-spacing: .05em; color: #6b7480; }
  table { width: 100%; border-collapse: collapse; background: #fff;
          border: 1px solid #e3e6ea; border-radius: 10px; overflow: hidden; font-variant-numeric: tabular-nums; }
  th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid #edeff2; font-size: .9rem; vertical-align: top; }
  th { background: #f0f2f5; font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; color: #5a626e; }
  tr:last-child td { border-bottom: none; }
  td.lead { font-weight: 700; }
  .tag { display: inline-block; font-size: .68rem; font-weight: 700; text-transform: uppercase;
         letter-spacing: .04em; padding: 2px 7px; border-radius: 999px; }
  .tag.ai { background: #fdf0d0; color: #7a5602; }
  .tag.human { background: #d8f5e6; color: #12603f; }
  .tag.good { background: #d8f5e6; color: #12603f; }
  .tag.bad { background: #fbdcdc; color: #8a1f1f; }
  .conv { background: #fff; border: 1px solid #e3e6ea; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; }
  .lines { margin-top: 10px; }
  .line { display: grid; grid-template-columns: 104px 88px 1fr; gap: 8px; padding: 3px 0; font-size: .88rem; }
  .line.bot .who { color: #7a5602; font-weight: 600; }
  .line .who { color: #4a525e; font-weight: 600; overflow-wrap: anywhere; }
  .line .time { color: #99a1ad; font-size: .78rem; white-space: nowrap; }
  .line .text { overflow-wrap: anywhere; }
  @media print {
    body { background: #fff; padding: 0; }
    h2 { break-after: avoid; }
    .conv, .tile, table { break-inside: avoid; }
  }
</style></head>
<body><div class="page">

  <h1>Human or Not? — round ${data.roundNumber}</h1>
  <div class="muted">Class report generated ${escapeHtml(stamp(data.generatedAt))}</div>
  <div class="meta">
    <div><strong>Started</strong> ${escapeHtml(stamp(data.startedAt))}</div>
    <div><strong>Length</strong> ${Math.round(data.durationSec / 60 * 10) / 10} min</div>
    <div><strong>Target AI share</strong> ${Math.round(data.aiRatio * 100)}%</div>
    <div><strong>Models used</strong> ${mix}</div>
  </div>
  ${data.usedLiveBot ? '' :
    '<p class="note"><strong>Note:</strong> no live API responses were recorded this round — the AI partners used the offline scripted fallback, so results are not representative of the models.</p>'}

  <div class="tiles">
    <div class="tile"><div class="n">${s.paired}</div><div class="k">Students</div></div>
    <div class="tile"><div class="n">${s.withHuman}</div><div class="k">With a peer</div></div>
    <div class="tile"><div class="n">${s.withAi}</div><div class="k">With AI</div></div>
    <div class="tile"><div class="n">${s.answered}</div><div class="k">Answered</div></div>
    <div class="tile"><div class="n">${pct(s.accuracy)}</div><div class="k">Class accuracy</div></div>
    <div class="tile"><div class="n">$${totalCost.toFixed(3)}</div><div class="k">Est. API cost</div></div>
  </div>

  <h2>By model</h2>
  ${modelTable(data)}

  <h2>Accuracy by partner type</h2>
  <table>
    <thead><tr><th>Partner</th><th>Students who answered</th><th>Correct</th></tr></thead>
    <tbody>
      <tr><td>Real classmate</td><td>${s.withHuman}</td><td class="lead">${pct(s.humanAccuracy)}</td></tr>
      <tr><td>AI bot</td><td>${s.withAi}</td><td class="lead">${pct(s.aiAccuracy)}</td></tr>
    </tbody>
  </table>

  <h2>Students</h2>
  ${studentTable(data)}

  <h2>Transcripts</h2>
  ${transcriptSection(data)}

</div></body></html>`;
}
