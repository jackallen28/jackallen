// Turns a submitted quote request into the notification you actually receive.
//
// Three modes (config.notify.mode):
//   preview — nothing is sent; the same page is viewable at /quote/<id>
//   resend  — Resend's HTTP API
//   smtp    — any SMTP provider
//
// The preview page and the email are the same HTML, so what you see while
// testing is exactly what lands in your inbox once you add a mail key.
import { config } from './config.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

async function deliver({ to, subject, html, text, replyTo }) {
  if (!to?.length) {
    console.warn('[mail] no recipient configured, dropping:', subject);
    return { ok: false, reason: 'no-recipient' };
  }

  if (config.notify.resendApiKey) {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${config.notify.resendApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ from: config.notify.from, to, subject, html, text, reply_to: replyTo }),
    });
    if (!res.ok) throw new Error(`Resend responded ${res.status}: ${await res.text()}`);
    return { ok: true, via: 'resend' };
  }

  if (config.notify.smtp.host) {
    const nodemailer = (await import('nodemailer')).default;
    const transport = nodemailer.createTransport({
      host: config.notify.smtp.host,
      port: config.notify.smtp.port,
      secure: config.notify.smtp.secure,
      auth: config.notify.smtp.user ? { user: config.notify.smtp.user, pass: config.notify.smtp.pass } : undefined,
    });
    await transport.sendMail({ from: config.notify.from, to: to.join(', '), subject, html, text, replyTo });
    return { ok: true, via: 'smtp' };
  }

  console.log(`\n[mail:dev] to=${to.join(', ')}\n[mail:dev] subject=${subject}\n${text}\n`);
  return { ok: true, via: 'console' };
}

function layout(title, bodyHtml) {
  const accent = config.brand.accent;
  return `<!doctype html><html><body style="margin:0;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#14161a">
  <div style="max-width:640px;margin:0 auto;padding:32px 24px">
    <div style="height:4px;background:${accent};border-radius:2px;margin-bottom:28px"></div>
    <h1 style="margin:0 0 20px;font-size:22px;font-weight:650;letter-spacing:-.01em">${esc(title)}</h1>
    ${bodyHtml}
    <p style="margin-top:32px;padding-top:16px;border-top:1px solid #eceef1;color:#8b9099;font-size:12px">
      Sent by ${esc(config.brand.name)} · ${esc(config.publicUrl)}
    </p>
  </div></body></html>`;
}

const row = (label, value) => `<tr>
  <td style="padding:8px 16px 8px 0;color:#6b7280;font-size:13px;white-space:nowrap;vertical-align:top">${esc(label)}</td>
  <td style="padding:8px 0;font-size:14px;vertical-align:top">${value}</td></tr>`;

export function buildQuoteEmails(lead) {
  const ref = lead.id.slice(2, 10).toUpperCase();
  const spec = lead.spec || {};
  const specRows = (spec.details || []).map((d) => row(d.label, esc(d.value))).join('');
  const files = lead.files;
  const stats = lead.stats;

  const ownerHtml = layout(`Quote request ${ref} — ${spec.title || lead.product}`, `
    ${files?.png ? `<img src="${esc(files.png)}" alt="" style="width:100%;border:1px solid #eceef1;border-radius:12px;margin-bottom:24px">` : ''}
    <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
      ${row('Name', esc(lead.name))}
      ${row('Email', `<a href="mailto:${esc(lead.email)}" style="color:${config.brand.accent}">${esc(lead.email)}</a>`)}
      ${row('Mobile', `<a href="tel:${esc(lead.phone)}" style="color:${config.brand.accent}">${esc(lead.phone)}</a>`)}
      ${row('Post code', esc(lead.postcode))}
      ${row('Quantity', esc(lead.quantity))}
      ${row('Needed', esc(lead.leadtime))}
      ${lead.notes ? row('Notes', esc(lead.notes)) : ''}
    </table>
    <h2 style="font-size:15px;margin:0 0 8px">Specification</h2>
    <p style="margin:0 0 12px;font-size:14px;color:#4b5157">${esc(spec.one_liner || '')}</p>
    <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
      ${specRows}
      ${row('Overall size', esc(spec.dimensions))}
      ${row('Process', esc(spec.process))}
      ${row('Material', esc(spec.material))}
      ${stats ? row('Model volume', `${esc(stats.volumeCm3)} cm³ · bbox ${esc(stats.bboxMm.x)} × ${esc(stats.bboxMm.y)} × ${esc(stats.bboxMm.z)} mm`) : ''}
    </table>
    ${spec.assumptions?.length ? `<p style="font-size:13px;color:#6b7280"><strong>Assumptions:</strong> ${esc(spec.assumptions.join(' · '))}</p>` : ''}
    ${files ? `<p style="margin:24px 0">
      <a href="${esc(files.viewer)}" style="display:inline-block;background:${config.brand.accent};color:#fff;text-decoration:none;padding:11px 18px;border-radius:8px;font-size:14px;font-weight:600">Open 3D viewer</a>
      <a href="${esc(files.stl)}" style="margin-left:8px;font-size:14px;color:#14161a">Download STL</a>
      <a href="${esc(files.scad)}" style="margin-left:8px;font-size:14px;color:#14161a">OpenSCAD source</a>
    </p>` : '<p style="font-size:14px;color:#b45309">No model was generated for this request — it needs manual CAD.</p>'}
    <p style="font-size:13px;color:#6b7280">Original brief: “${esc(lead.brief)}”</p>
  `);

  const ownerText = [
    `Quote request ${ref}`,
    `${lead.name} · ${lead.email} · ${lead.phone} · ${lead.postcode}`,
    `Qty ${lead.quantity} · ${lead.leadtime}`,
    '',
    `Product: ${spec.title || lead.product}`,
    `Brief: ${lead.brief}`,
    ...(spec.details || []).map((d) => `- ${d.label}: ${d.value}`),
    `- Overall: ${spec.dimensions}`,
    `- Process: ${spec.process} in ${spec.material}`,
    stats ? `- Volume: ${stats.volumeCm3} cm3, bbox ${stats.bboxMm.x}x${stats.bboxMm.y}x${stats.bboxMm.z} mm` : '',
    '',
    files ? `Viewer: ${files.viewer}\nSTL: ${files.stl}\nSCAD: ${files.scad}` : 'No model generated.',
    lead.notes ? `\nNotes: ${lead.notes}` : '',
  ].filter(Boolean).join('\n');

  const customerHtml = layout('We’ve got your design request', `
      <p style="font-size:15px;line-height:1.6">Hi ${esc(lead.name.split(' ')[0])}, thanks for using ${esc(config.brand.name)}.
      We're reviewing <strong>${esc(spec.title || lead.product)}</strong> (quantity ${esc(lead.quantity)}) and will come back to you
      with a price and lead time, usually within one business day.</p>
      <p style="font-size:15px">Your reference is <strong>${esc(ref)}</strong>.</p>
      ${files?.png ? `<img src="${esc(files.png)}" alt="" style="width:100%;border:1px solid #eceef1;border-radius:12px;margin:16px 0">` : ''}
      ${files ? `<p><a href="${esc(files.viewer)}" style="display:inline-block;background:${config.brand.accent};color:#fff;text-decoration:none;padding:11px 18px;border-radius:8px;font-size:14px;font-weight:600">View your model</a></p>` : ''}
      <p style="font-size:13px;color:#6b7280">Reply to this email if anything needs changing.</p>
    `);
  const customerText = `Hi ${lead.name.split(' ')[0]}, thanks — we have your request (ref ${ref}) for ${spec.title || lead.product}, quantity ${lead.quantity}. We'll be in touch within one business day.${files ? `\n\nView your model: ${files.viewer}` : ''}`;

  return {
    ref,
    ownerSubject: `Quote request ${ref} · ${spec.title || lead.product} · qty ${lead.quantity}`,
    ownerHtml,
    ownerText,
    customerSubject: `Your design request ${ref} — ${config.brand.name}`,
    customerHtml,
    customerText,
  };
}

/**
 * Deliver a submitted request. In preview mode nothing leaves the server — the
 * customer gets a link to /quote/<id> in the chat instead.
 * @returns {Promise<{mode: string, previewUrl: string}>}
 */
export async function notifyQuote(lead) {
  const mail = buildQuoteEmails(lead);
  const previewUrl = `${config.publicUrl}/quote/${lead.id}`;

  if (config.notify.mode === 'preview') {
    console.log(`[notify] preview mode — quote request ${mail.ref} at ${previewUrl}`);
    return { mode: 'preview', previewUrl };
  }

  await deliver({
    to: config.notify.to,
    subject: mail.ownerSubject,
    html: mail.ownerHtml,
    text: mail.ownerText,
    replyTo: lead.email,
  });

  if (config.notify.sendCustomerCopy) {
    await deliver({
      to: [lead.email],
      subject: mail.customerSubject,
      html: mail.customerHtml,
      text: mail.customerText,
      replyTo: config.notify.replyToOwner || config.notify.to[0],
    });
  }
  return { mode: config.notify.mode, previewUrl };
}

/**
 * The /quote/<id> page: the notification you would have received, wrapped in a
 * thin bar that says it was not actually sent and switches between the copy
 * addressed to you and the one addressed to the customer.
 */
export function renderQuotePreview(lead, view = 'owner') {
  const mail = buildQuoteEmails(lead);
  const customer = view === 'customer';
  const html = customer ? mail.customerHtml : mail.ownerHtml;
  const to = customer ? lead.email : (config.notify.to.join(', ') || 'your inbox');
  const subject = customer ? mail.customerSubject : mail.ownerSubject;
  const tab = (label, href, active) => `<a href="${esc(href)}" style="text-decoration:none;padding:5px 12px;border-radius:999px;font-size:12.5px;font-weight:600;${
    active
      ? `background:${config.brand.accent};color:#fff`
      : 'background:#fff;color:#6b7280;border:1px solid #eceef1'
  }">${esc(label)}</a>`;

  const bar = `<div style="border-bottom:1px solid #eceef1;background:#fff;padding:14px 24px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif">
    <div style="max-width:640px;margin:0 auto">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px">
        <span style="background:${config.brand.accent};color:#fff;font-size:11px;font-weight:700;letter-spacing:.06em;padding:3px 8px;border-radius:4px">PREVIEW</span>
        <span style="font-size:12.5px;color:#6b7280">Not sent — add a mail key to deliver these for real.</span>
        <span style="flex:1"></span>
        ${tab('To you', `?view=owner`, !customer)}
        ${tab('To the customer', `?view=customer`, customer)}
      </div>
      <div style="font-size:12.5px;color:#6b7280">
        <strong style="color:#14161a;font-weight:600">To</strong> ${esc(to)} &nbsp;·&nbsp;
        <strong style="color:#14161a;font-weight:600">Subject</strong> ${esc(subject)}
      </div>
    </div>
  </div>`;

  return html.replace('<div style="max-width:640px', `${bar}<div style="max-width:640px`);
}

/** The /requests list — every quote request submitted, newest first. */
export function renderRequestList(leads, key) {
  const accent = config.brand.accent;
  const q = key ? `?key=${encodeURIComponent(key)}` : '';
  const rows = leads.map((lead) => {
    const when = new Date(lead.receivedAt);
    return `<tr style="border-top:1px solid #eceef1">
      <td style="padding:12px 14px 12px 0;font-size:13px;color:#6b7280;white-space:nowrap">${esc(when.toLocaleString('en-AU'))}</td>
      <td style="padding:12px 14px 12px 0;font-size:13px;font-weight:600">${esc(lead.id.slice(2, 10).toUpperCase())}</td>
      <td style="padding:12px 14px 12px 0;font-size:14px">${esc(lead.spec?.title || lead.product)}</td>
      <td style="padding:12px 14px 12px 0;font-size:14px">${esc(lead.name)}<div style="font-size:12px;color:#6b7280">${esc(lead.email)} · ${esc(lead.postcode)}</div></td>
      <td style="padding:12px 14px 12px 0;font-size:14px;white-space:nowrap">${esc(lead.quantity)} off<div style="font-size:12px;color:#6b7280">${esc(lead.leadtime)}</div></td>
      <td style="padding:12px 0;white-space:nowrap">
        <a href="/quote/${esc(lead.id)}${q}" style="color:${accent};font-size:13px;font-weight:600;text-decoration:none">Request</a>
        ${lead.files ? ` · <a href="${esc(lead.files.viewer)}" style="color:#14161a;font-size:13px;text-decoration:none">3D</a>` : ''}
        ${lead.files ? ` · <a href="${esc(lead.files.stl)}" style="color:#14161a;font-size:13px;text-decoration:none">STL</a>` : ''}
      </td>
    </tr>`;
  }).join('');

  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex"><title>Quote requests · ${esc(config.brand.name)}</title></head>
  <body style="margin:0;background:#fff;color:#14161a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif">
    <div style="max-width:1000px;margin:0 auto;padding:40px 24px 80px">
      <div style="height:3px;width:44px;background:${accent};border-radius:2px;margin-bottom:22px"></div>
      <h1 style="font-size:22px;font-weight:650;letter-spacing:-.01em;margin:0 0 4px">Quote requests</h1>
      <p style="color:#6b7280;font-size:14px;margin:0 0 28px">${leads.length} received · newest first</p>
      ${leads.length ? `<table style="width:100%;border-collapse:collapse">${rows}</table>`
        : '<p style="color:#6b7280;font-size:14px">Nothing yet — run a conversation through the widget.</p>'}
    </div>
  </body></html>`;
}
