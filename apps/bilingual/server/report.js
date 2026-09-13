/**
 * The facilitator's downloadable round report, in either activity language.
 *
 * Three formats from the same data: a self-contained HTML page, plain-text
 * transcripts, and a CSV row per participant. The HTML and the transcripts follow
 * the chosen language; the CSV keeps English column names so that the file stays
 * readable by spreadsheet formulas and scripts whichever language was picked.
 */
import { modelLabel } from './models.js';
import { strings } from './i18n.js';
import { LANGUAGES } from './translate.js';

const escapeHtml = (value) =>
  String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

const stamp = (ms, lang) =>
  ms ? new Date(ms).toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-AU') : '—';
const clock = (ms, lang) =>
  ms ? new Date(ms).toLocaleTimeString(lang === 'zh' ? 'zh-CN' : 'en-AU',
    { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
const pct = (value) => (value === null || value === undefined ? '—' : `${value}%`);
const langLabel = (code) => LANGUAGES[code]?.native || code || '—';

/** `2026-09-13_1423` — safe in a filename on any OS. */
export function reportFilename(data, extension) {
  const when = new Date(data.generatedAt || Date.now());
  const pad = (n) => String(n).padStart(2, '0');
  const date = `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`;
  const time = `${pad(when.getHours())}${pad(when.getMinutes())}`;
  return `human-or-not_round-${data.roundNumber}_${date}_${time}.${extension}`;
}

/** One row per participant. Column names stay English so the file stays machine-readable. */
export function buildCsvReport(data) {
  const cell = (value) => {
    const text = String(value ?? '');
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };

  const transcriptFor = (code) => {
    const conv = data.transcripts.find((c) => c.members.includes(code));
    if (!conv) return '';
    return conv.messages.map((m) => `${m.sender}: ${m.text}`).join(' | ');
  };

  const header = [
    'participant', 'login', 'language', 'partner_type', 'model', 'persona', 'partner',
    'messages_sent', 'their_answer', 'correct', 'bot_turns', 'tokens_in', 'tokens_out',
    'transcript',
  ];

  const rows = data.participants
    .filter((p) => p.inRound)
    .map((p) => {
      const conv = data.transcripts.find((c) => c.members.includes(p.code));
      return [
        p.student || p.code,
        p.code,
        p.lang || '',
        p.partnerType === 'ai' ? 'AI' : 'peer',
        p.model || '',
        p.personaLabel || '',
        p.partner || '',
        p.messagesSent,
        p.guess ? (p.guess === 'ai' ? 'AI' : 'peer') : 'no answer',
        p.correct === null ? '' : p.correct ? 'correct' : 'wrong',
        conv?.botTurns ?? '',
        conv?.tokensIn ?? '',
        conv?.tokensOut ?? '',
        transcriptFor(p.code),
      ];
    });

  return [header, ...rows].map((row) => row.map(cell).join(',')).join('\n');
}

/** Plain-text transcripts, in the chosen language's framing. */
export function buildTranscriptText(data, lang = 'en') {
  const t = strings(lang);
  const lines = [
    `${t('reportTitle')} ${data.roundNumber}`,
    `${t('generated')}: ${stamp(data.generatedAt, lang)}`,
    '',
    t('translatedNote'),
    '',
  ];

  for (const conv of data.transcripts) {
    const names = conv.memberLabels || conv.members;
    const who = conv.type === 'ai'
      ? `${names[0]} ${t('talkedTo')} ${conv.modelLabel || 'AI'}` +
        (conv.personaLabel ? ` (${t('persona')} ${conv.personaLabel})` : '')
      : names.join(` ${t('talkedTo')} `);
    lines.push('='.repeat(70), who, '');
    if (!conv.messages.length) lines.push(`(${t('noMessages')})`);
    for (const message of conv.messages) lines.push(`${message.sender}: ${message.text}`);
    lines.push('');
  }
  return lines.join('\n');
}

function modelTable(data, t) {
  if (!data.byModel.length) return `<p class="muted">${t('noAi')}</p>`;

  const rows = data.byModel
    .slice()
    .sort((a, b) => (b.foolRate ?? -1) - (a.foolRate ?? -1))
    .map((row) => `<tr>
        <td><strong>${escapeHtml(row.label)}</strong><div class="sub">${escapeHtml(row.id)}</div></td>
        <td>${row.students}</td><td>${row.answered}</td><td>${row.fooled}</td><td>${row.caught}</td>
        <td class="lead">${pct(row.foolRate)}</td><td>${row.botTurns}</td>
        <td>${row.tokensIn.toLocaleString()} / ${row.tokensOut.toLocaleString()}</td>
        <td>$${row.costUsd.toFixed(4)}</td>
      </tr>`)
    .join('');

  return `<table>
    <thead><tr>
      <th>${t('colModel')}</th><th>${t('colParticipants')}</th><th>${t('colAnswered')}</th>
      <th>${t('colBelievedHuman')}</th><th>${t('colSpottedAi')}</th><th>${t('colFooledRate')}</th>
      <th>${t('colBotTurns')}</th><th>${t('colTokens')}</th><th>${t('colCost')}</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>
  <p class="note">${t('foolNote')}</p>`;
}

function personaTable(data, t) {
  const rows = data.byPersona || [];
  if (!rows.length) return '';

  const body = rows
    .slice()
    .sort((a, b) => (b.foolRate ?? -1) - (a.foolRate ?? -1))
    .map((row) => `<tr>
        <td><strong>${escapeHtml(row.id)}</strong> ${escapeHtml(row.label)}</td>
        <td>${row.students}</td><td>${row.answered}</td><td>${row.fooled}</td>
        <td>${row.caught}</td><td class="lead">${pct(row.foolRate)}</td>
      </tr>`)
    .join('');

  return `<h2>${t('byPersona')}</h2>
  <table>
    <thead><tr>
      <th>${t('colPersona')}</th><th>${t('colParticipants')}</th><th>${t('colAnswered')}</th>
      <th>${t('colBelievedHuman')}</th><th>${t('colSpottedAi')}</th><th>${t('colFooledRate')}</th>
    </tr></thead>
    <tbody>${body}</tbody>
  </table>`;
}

function participantTable(data, t) {
  const rows = data.participants
    .filter((p) => p.inRound)
    .map((p) => `<tr>
        <td><strong>${escapeHtml(p.student || p.code)}</strong><div class="sub">${escapeHtml(p.code)}</div></td>
        <td>${escapeHtml(langLabel(p.lang))}</td>
        <td>${p.partnerType === 'ai'
          ? `<span class="tag ai">${t('aiBot')}</span> ${escapeHtml(p.modelLabel || '')}`
          : `<span class="tag human">${t('peer')}</span> ${escapeHtml(p.partner || '')}`}</td>
        <td>${escapeHtml(p.personaLabel || '—')}</td>
        <td>${p.messagesSent}</td>
        <td>${p.guess ? (p.guess === 'ai' ? t('answerAi') : t('answerPeer'))
          : `<span class="muted">${t('noAnswer')}</span>`}</td>
        <td>${p.correct === null ? '<span class="muted">—</span>'
          : p.correct ? `<span class="tag good">${t('correct')}</span>`
            : `<span class="tag bad">${t('wrong')}</span>`}</td>
      </tr>`)
    .join('');

  return `<table>
    <thead><tr>
      <th>${t('colParticipant')}</th><th>${t('languageLabel')}</th><th>${t('colPairedWith')}</th>
      <th>${t('colPersona')}</th><th>${t('colMessages')}</th><th>${t('colTheirAnswer')}</th>
      <th>${t('colResult')}</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function transcriptSection(data, t, lang) {
  if (!data.transcripts.length) return `<p class="muted">${t('noConversations')}</p>`;

  return data.transcripts.map((conv) => {
    const names = (conv.memberLabels || conv.members).map(escapeHtml);
    const title = conv.type === 'ai'
      ? `${names[0]} &harr; ${escapeHtml(conv.modelLabel || 'AI')}`
      : names.join(' &harr; ');
    const tag = conv.type === 'ai'
      ? `<span class="tag ai">${t('aiBot')} · ${escapeHtml(conv.modelLabel || '')}</span>` +
        (conv.personaLabel ? ` <span class="tag">${escapeHtml(conv.personaLabel)}</span>` : '')
      : `<span class="tag human">${t('peer')}</span>`;
    const meta = conv.type === 'ai'
      ? `<div class="sub">${conv.botTurns} ${t('botTurns')} · ${conv.tokensIn.toLocaleString()} / ${conv.tokensOut.toLocaleString()} ${t('tokens')}</div>`
      : '';

    const body = conv.messages.length
      ? conv.messages.map((m) => `<div class="line${m.isBot ? ' bot' : ''}">
            <span class="who">${escapeHtml(m.sender)}</span>
            <span class="time">${clock(m.ts, lang)}</span>
            <span class="text">${escapeHtml(m.text)}</span>
          </div>`).join('')
      : `<div class="line muted">${t('noMessages')}</div>`;

    return `<section class="conv"><h3>${title} ${tag}</h3>${meta}<div class="lines">${body}</div></section>`;
  }).join('');
}

/** A standalone HTML page — no external assets, safe to email or print. */
export function buildHtmlReport(data, lang = 'en') {
  const t = strings(lang);
  const s = data.stats;
  const mix = Object.entries(data.modelMix || {})
    .map(([id, weight]) => `${escapeHtml(modelLabel(id))} (${weight})`)
    .join(', ') || '—';
  const totalCost = data.byModel.reduce((sum, row) => sum + row.costUsd, 0);
  const zh = lang === 'zh';

  return `<!doctype html>
<html lang="${zh ? 'zh-CN' : 'en'}"><head><meta charset="utf-8">
<title>${t('reportTitle')} ${data.roundNumber}</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 32px; background: #f6f7f9; color: #14181f;
         font: 15px/1.6 ${zh ? '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", ' : ''}ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  .page { max-width: 1000px; margin: 0 auto; }
  h1 { font-size: 1.65rem; margin: 0 0 4px; }
  h2 { font-size: 1.15rem; margin: 32px 0 12px; padding-bottom: 6px; border-bottom: 2px solid #e3e6ea; }
  h3 { font-size: 1rem; margin: 0 0 2px; }
  .muted { color: #6b7480; }
  .sub { font-size: .8rem; color: #6b7480; }
  .note { font-size: .85rem; color: #6b7480; margin-top: 8px; }
  .meta { display: flex; flex-wrap: wrap; gap: 20px; font-size: .88rem; color: #4a525e; margin-top: 10px; }
  .tiles { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; }
  .tile { flex: 1 1 130px; background: #fff; border: 1px solid #e3e6ea; border-radius: 10px; padding: 14px 16px; }
  .tile .n { font-size: 1.7rem; font-weight: 700; font-variant-numeric: tabular-nums; }
  .tile .k { font-size: .72rem; text-transform: uppercase; letter-spacing: .05em; color: #6b7480; }
  table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e3e6ea;
          border-radius: 10px; overflow: hidden; font-variant-numeric: tabular-nums; }
  th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid #edeff2; font-size: .9rem; vertical-align: top; }
  th { background: #f0f2f5; font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; color: #5a626e; }
  tr:last-child td { border-bottom: none; }
  td.lead { font-weight: 700; }
  .tag { display: inline-block; font-size: .68rem; font-weight: 700; text-transform: uppercase;
         letter-spacing: .04em; padding: 2px 7px; border-radius: 999px; }
  .tag.ai { background: #fdf0d0; color: #7a5602; }
  .tag.human, .tag.good { background: #d8f5e6; color: #12603f; }
  .tag.bad { background: #fbdcdc; color: #8a1f1f; }
  .conv { background: #fff; border: 1px solid #e3e6ea; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; }
  .lines { margin-top: 10px; }
  .line { display: grid; grid-template-columns: 120px 88px 1fr; gap: 8px; padding: 3px 0; font-size: .88rem; }
  .line.bot .who { color: #7a5602; font-weight: 600; }
  .line .who { color: #4a525e; font-weight: 600; overflow-wrap: anywhere; }
  .line .time { color: #99a1ad; font-size: .78rem; white-space: nowrap; }
  .line .text { overflow-wrap: anywhere; }
  @media print { body { background: #fff; padding: 0; } h2 { break-after: avoid; } .conv, .tile, table { break-inside: avoid; } }
</style></head>
<body><div class="page">

  <h1>${t('reportTitle')} ${data.roundNumber}</h1>
  <div class="muted">${t('generated')} ${escapeHtml(stamp(data.generatedAt, lang))}</div>
  <div class="meta">
    <div><strong>${t('started')}</strong> ${escapeHtml(stamp(data.startedAt, lang))}</div>
    <div><strong>${t('length')}</strong> ${Math.round(data.durationSec / 60 * 10) / 10} ${t('minutes')}</div>
    <div><strong>${t('targetAiShare')}</strong> ${Math.round(data.aiRatio * 100)}%</div>
    <div><strong>${t('modelsUsed')}</strong> ${mix}</div>
  </div>
  ${data.usedLiveBot ? '' : `<p class="note"><strong>${t('offlineNote')}</strong></p>`}

  <div class="tiles">
    <div class="tile"><div class="n">${s.paired}</div><div class="k">${t('tileParticipants')}</div></div>
    <div class="tile"><div class="n">${s.withHuman}</div><div class="k">${t('tileWithPeer')}</div></div>
    <div class="tile"><div class="n">${s.withAi}</div><div class="k">${t('tileWithAi')}</div></div>
    <div class="tile"><div class="n">${s.answered}</div><div class="k">${t('tileAnswered')}</div></div>
    <div class="tile"><div class="n">${pct(s.accuracy)}</div><div class="k">${t('tileAccuracy')}</div></div>
    <div class="tile"><div class="n">$${totalCost.toFixed(3)}</div><div class="k">${t('tileCost')}</div></div>
  </div>

  <h2>${t('byModel')}</h2>
  ${modelTable(data, t)}
  ${personaTable(data, t)}

  <h2>${t('byPartnerType')}</h2>
  <table>
    <thead><tr><th>${t('colPartner')}</th><th>${t('colAnswered')}</th><th>${t('colCorrect')}</th></tr></thead>
    <tbody>
      <tr><td>${t('realPerson')}</td><td>${s.withHuman}</td><td class="lead">${pct(s.humanAccuracy)}</td></tr>
      <tr><td>${t('aiBot')}</td><td>${s.withAi}</td><td class="lead">${pct(s.aiAccuracy)}</td></tr>
    </tbody>
  </table>

  <h2>${t('participants')}</h2>
  ${participantTable(data, t)}

  <h2>${t('transcripts')}</h2>
  <p class="note">${t('translatedNote')}</p>
  ${transcriptSection(data, t, lang)}

</div></body></html>`;
}
