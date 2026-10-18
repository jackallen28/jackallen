// Confirmation + manage booking page (/manage/:token). Shows the booking and lets the school cancel it.

import { api, esc, setupPage, longDate, plural, announce } from './common.js';

const token = decodeURIComponent(location.pathname.split('/').filter(Boolean).pop());
const isNew = new URLSearchParams(location.search).get('new') === '1';
const page = document.getElementById('page');
const message = document.getElementById('message');

function render(b) {
  const cancelled = b.status === 'cancelled';
  const manageUrl = `${location.origin}/manage/${encodeURIComponent(token)}`;
  document.title = `${b.reference} – ${b.programName}`;
  page.innerHTML = `
    ${
      isNew && !cancelled
        ? `<div class="notice success"><h1 style="margin:0 0 4px">Booking confirmed</h1>
           <p>Thank you! Your booking reference is <strong>${esc(b.reference)}</strong>.</p></div>`
        : `<h1>Your booking ${esc(b.reference)}</h1>`
    }
    ${cancelled ? '<div class="notice warn"><strong>This booking has been cancelled.</strong></div>' : ''}
    <div class="card">
      <dl class="summary">
        <dt>Program</dt><dd>${esc(b.programName)}</dd>
        <dt>Date</dt><dd>${esc(longDate(b.date))}</dd>
        <dt>Time</dt><dd>${esc(b.slotLabel)}</dd>
        <dt>Group</dt><dd>${plural(b.classes, 'class')} (${b.students} students), ${esc(b.yearLevel)}</dd>
        <dt>School</dt><dd>${esc(b.school)}</dd>
        <dt>Contact</dt><dd>${esc(b.contactName)}<br>${esc(b.email)}<br>${esc(b.phone)}</dd>
        ${b.notes ? `<dt>Notes</dt><dd>${esc(b.notes)}</dd>` : ''}
        <dt>Status</dt><dd><span class="badge ${cancelled ? 'bad' : 'ok'}">${cancelled ? 'Cancelled' : 'Confirmed'}</span></dd>
      </dl>
    </div>
    ${
      cancelled
        ? '<p style="margin-top:20px"><a class="button" href="/">Book another program</a></p>'
        : `
    <div class="card" style="margin-top:16px">
      <h2>Keep this link</h2>
      <p>This private link is how you view or cancel your booking. Bookmark it or copy it somewhere safe.</p>
      <div class="inline-field">
        <label class="visually-hidden" for="manage-link">Manage link</label>
        <input id="manage-link" class="input" readonly value="${esc(manageUrl)}" style="flex:1;min-width:220px">
        <button type="button" class="button secondary" id="copy-link">Copy link</button>
      </div>
      <p style="margin-top:16px;display:flex;gap:10px;flex-wrap:wrap">
        <a class="button" href="/api/manage/${encodeURIComponent(token)}/booking.ics">Add to calendar (.ics)</a>
        <button type="button" class="button danger" id="cancel-booking">Cancel booking</button>
      </p>
    </div>`
    }`;

  document.getElementById('copy-link')?.addEventListener('click', async (e) => {
    const input = document.getElementById('manage-link');
    try {
      await navigator.clipboard.writeText(input.value);
    } catch {
      input.select();
      document.execCommand('copy');
    }
    e.target.textContent = 'Copied ✓';
  });

  document.getElementById('cancel-booking')?.addEventListener('click', async () => {
    if (!confirm(`Cancel ${b.programName} on ${longDate(b.date)}? This can't be undone.`)) return;
    try {
      const result = await api(`/api/manage/${encodeURIComponent(token)}/cancel`, { method: 'POST' });
      announce(message, 'Your booking has been cancelled.', 'success');
      render(result.booking);
    } catch (err) {
      announce(message, `Could not cancel: ${esc(err.message)}`, 'error');
    }
  });
}

try {
  const [catalog, data] = await Promise.all([api('/api/catalog'), api(`/api/manage/${encodeURIComponent(token)}`)]);
  setupPage(catalog);
  render(data.booking);
} catch (err) {
  setupPage();
  page.innerHTML =
    err.status === 404
      ? '<div class="notice error">We couldn’t find that booking. Please check the link you were given.</div>'
      : `<div class="notice error">Something went wrong: ${esc(err.message)}</div>`;
}
