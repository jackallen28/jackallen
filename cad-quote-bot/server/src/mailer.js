// Outbound email. Resend if RESEND_API_KEY is set, otherwise SMTP, otherwise
// the message is logged (handy in development — nothing silently disappears).
import { config } from './config.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

async function deliver({ to, subject, html, text, replyTo }) {
  if (!to?.length) {
    console.warn('[mail] no recipient configured, dropping:', subject);
    return { ok: false, reason: 'no-recipient' };
  }

  if (config.mail.resendApiKey) {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${config.mail.resendApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ from: config.mail.from, to, subject, html, text, reply_to: replyTo }),
    });
    if (!res.ok) throw new Error(`Resend responded ${res.status}: ${await res.text()}`);
    return { ok: true, via: 'resend' };
  }

  if (config.mail.smtp.host) {
    const nodemailer = (await import('nodemailer')).default;
    const transport = nodemailer.createTransport({
      host: config.mail.smtp.host,
      port: config.mail.smtp.port,
      secure: config.mail.smtp.secure,
      auth: config.mail.smtp.user ? { user: config.mail.smtp.user, pass: config.mail.smtp.pass } : undefined,
    });
    await transport.sendMail({ from: config.mail.from, to: to.join(', '), subject, html, text, replyTo });
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

export async function sendQuoteEmails(lead) {
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

  const results = [];
  results.push(await deliver({
    to: config.mail.to,
    subject: `Quote request ${ref} · ${spec.title || lead.product} · qty ${lead.quantity}`,
    html: ownerHtml,
    text: ownerText,
    replyTo: lead.email,
  }));

  if (config.mail.sendCustomerCopy) {
    const customerHtml = layout('We’ve got your design request', `
      <p style="font-size:15px;line-height:1.6">Hi ${esc(lead.name.split(' ')[0])}, thanks for using ${esc(config.brand.name)}.
      We're reviewing <strong>${esc(spec.title || lead.product)}</strong> (quantity ${esc(lead.quantity)}) and will come back to you
      with a price and lead time, usually within one business day.</p>
      <p style="font-size:15px">Your reference is <strong>${esc(ref)}</strong>.</p>
      ${files?.png ? `<img src="${esc(files.png)}" alt="" style="width:100%;border:1px solid #eceef1;border-radius:12px;margin:16px 0">` : ''}
      ${files ? `<p><a href="${esc(files.viewer)}" style="display:inline-block;background:${config.brand.accent};color:#fff;text-decoration:none;padding:11px 18px;border-radius:8px;font-size:14px;font-weight:600">View your model</a></p>` : ''}
      <p style="font-size:13px;color:#6b7280">Reply to this email if anything needs changing.</p>
    `);
    results.push(await deliver({
      to: [lead.email],
      subject: `Your design request ${ref} — ${config.brand.name}`,
      html: customerHtml,
      text: `Hi ${lead.name.split(' ')[0]}, thanks — we have your request (ref ${ref}) for ${spec.title || lead.product}, quantity ${lead.quantity}. We'll be in touch within one business day.${files ? `\n\nView your model: ${files.viewer}` : ''}`,
      replyTo: config.mail.replyToOwner || config.mail.to[0],
    }));
  }
  return results;
}
