// Admin area. One page script; the view shown depends on the URL (/admin, /admin/bookings, …).

import { api as baseApi, esc, setupPage, longDate, shortDate, addDays, plural, announce } from './common.js';

const view = document.getElementById('view');
const message = document.getElementById('message');
const section = location.pathname.replace(/^\/admin\/?/, '').split('/')[0] || 'board';
let me;

// Admin POSTs must be JSON (see src/auth.js), so always send a body.
const api = (path, opts = {}) =>
  baseApi(path, opts.method && opts.method !== 'GET' ? { ...opts, body: opts.body || {} } : opts).catch((err) => {
    if (err.status === 401) location.reload(); // session expired → back to login
    throw err;
  });

// Each program gets a stable colour on the board.
const colourCache = new Map();
function colourClass(programId, programs) {
  if (!colourCache.has(programId)) {
    const index = programs.findIndex((p) => p.id === programId);
    colourCache.set(programId, `pc-${(index < 0 ? colourCache.size : index) % 8}`);
  }
  return colourCache.get(programId);
}

function syncBadge(status, error) {
  const map = { none: ['', 'Not synced'], pending: ['warn', 'Pending'], synced: ['ok', 'Synced'], failed: ['bad', 'Failed'] };
  const [cls, label] = map[status] || ['', status];
  return `<span class="badge ${cls}" ${error ? `title="${esc(error)}"` : ''}>${label}</span>`;
}

function bookingDetails(b) {
  return `
    <dl class="kv">
      <dt>Reference</dt><dd>${esc(b.reference)} <span class="badge ${b.status === 'cancelled' ? 'bad' : 'ok'}">${esc(b.status)}</span></dd>
      <dt>Program</dt><dd>${esc(b.programName)}</dd>
      <dt>When</dt><dd>${esc(longDate(b.date))}, ${esc(b.slotLabel)}</dd>
      <dt>Group</dt><dd>${plural(b.classes, 'class')} (${b.students} students), ${esc(b.yearLevel)}</dd>
      <dt>Rooms / kit</dt><dd>${esc(b.resources.join(', ') || '—')}</dd>
      <dt>Staff</dt><dd>${b.staffRequired ?? '—'}</dd>
      <dt>School</dt><dd>${esc(b.school)}</dd>
      <dt>Contact</dt><dd>${esc(b.contactName)} · <a href="mailto:${esc(b.email)}">${esc(b.email)}</a> · ${esc(b.phone)}</dd>
      ${b.notes ? `<dt>Notes</dt><dd>${esc(b.notes)}</dd>` : ''}
      <dt>Sync</dt><dd>${syncBadge(b.syncStatus, b.syncError)} ${b.syncError ? `<span class="small muted">${esc(b.syncError)}</span>` : ''}</dd>
      <dt>Created</dt><dd>${esc(new Date(b.createdAt).toLocaleString('en-AU'))} (${esc(b.source)})</dd>
    </dl>
    <p style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
      <a class="button secondary small" href="${esc(b.manageUrl)}" target="_blank" rel="noopener">School's view ↗</a>
      ${b.status === 'confirmed' ? `<button class="button danger small" data-cancel="${b.id}">Cancel booking</button>` : ''}
      ${me.syncMode !== 'none' && ['failed', 'pending'].includes(b.syncStatus) ? `<button class="button secondary small" data-retry="${b.id}">Retry sync</button>` : ''}
    </p>`;
}

async function cancelBooking(id, after) {
  if (!confirm('Cancel this booking? The school can see it has been cancelled via their manage link.')) return;
  try {
    await api(`/admin/api/bookings/${id}/cancel`, { method: 'POST' });
    announce(message, 'Booking cancelled.', 'success');
    after();
  } catch (err) {
    announce(message, esc(err.message), 'error');
  }
}

async function retrySync(id, after) {
  try {
    const { booking } = await api(`/admin/api/bookings/${id}/retry-sync`, { method: 'POST' });
    announce(message, `Sync: ${esc(booking.syncStatus)}${booking.syncError ? ` — ${esc(booking.syncError)}` : ''}`, booking.syncStatus === 'synced' ? 'success' : 'warn');
    after();
  } catch (err) {
    announce(message, esc(err.message), 'error');
  }
}

// =========================================================================== day board
async function renderBoard() {
  const params = new URLSearchParams(location.search);
  const state = { date: params.get('date') || me.today, view: params.get('view') || 'day' };

  async function load() {
    history.replaceState(null, '', `/admin?date=${state.date}&view=${state.view}`);
    const data = await api(`/admin/api/board?date=${state.date}&view=${state.view}`);
    const byId = new Map(data.bookings.map((b) => [b.id, b]));
    const busyById = new Map(data.busy.map((x) => [x.id, x]));
    const blackout = new Map(data.blackouts.map((b) => [b.date, b.reason]));
    const step = state.view === 'week' ? 7 : 1;

    const header = data.columns
      .map((c) => {
        const full = c.staffUsed >= c.staffPool;
        return `<th scope="col">${esc(state.view === 'week' ? shortDate(c.date) : longDate(c.date))}<br>
          <span class="muted small">${esc(c.slotLabel)}</span><br>
          <span class="staff-meter ${full ? 'full' : 'ok'}">${c.staffUsed}/${c.staffPool} ${esc(data.staffPoolName.replace(/unicators$/, 's'))}</span>
          ${blackout.has(c.date) ? `<br><span class="closed-note">Closed: ${esc(blackout.get(c.date))}</span>` : ''}</th>`;
      })
      .join('');

    const rowsFor = (type) =>
      data.resources
        .filter((r) => r.type === type)
        .map((r) => {
          const cells = data.columns
            .map((c) => {
              const blocks = c.bookingIds
                .map((id) => byId.get(id))
                .filter((b) => b.assignedResources.includes(r.id))
                .map(
                  (b) => `<button class="block ${colourClass(b.programId, data.programs)}" data-booking="${b.id}">
                    <strong>${esc(b.programName)}</strong><small>${esc(b.school)} · ${plural(b.classes, 'class')}</small></button>`,
                );
              const ext = c.busyIds
                .map((id) => busyById.get(id))
                .filter((x) => x.resourceIds.includes(r.id))
                .map((x) => `<div class="block external"><strong>${esc(x.programName || x.label || 'Busy')}</strong><small>From Microsoft Bookings · ${esc(x.start)}–${esc(x.end)}</small></div>`);
              return `<td>${[...blocks, ...ext].join('')}</td>`;
            })
            .join('');
          return `<tr><th scope="row">${esc(r.name)}</th>${cells}</tr>`;
        })
        .join('');

    const colspan = data.columns.length + 1;
    const unplaced = data.busy.filter((x) => !x.resourceIds.length);
    view.innerHTML = `
      <div class="toolbar">
        <div><h1 style="margin:0">Day board</h1><span class="muted">Rooms and shared kit, with staff in use for each slot.</span></div>
        <span class="spacer"></span>
        <button class="button secondary small" id="prev" aria-label="Previous ${state.view}">← Prev</button>
        <div class="field"><label for="board-date" class="visually-hidden">Date</label><input type="date" id="board-date" value="${state.date}"></div>
        <button class="button secondary small" id="next" aria-label="Next ${state.view}">Next →</button>
        <button class="button secondary small" id="today">Today</button>
        <div class="segmented" role="group" aria-label="View">
          <button type="button" data-view="day" aria-pressed="${state.view === 'day'}">Day</button>
          <button type="button" data-view="week" aria-pressed="${state.view === 'week'}">Week</button>
        </div>
        ${me.demoMode ? '<button class="button danger small" id="reset-demo">Reset demo data</button>' : ''}
      </div>
      <div class="board-wrap">
        <table class="board">
          <thead><tr><th scope="col">Room / equipment</th>${header}</tr></thead>
          <tbody>
            <tr class="group"><th colspan="${colspan}">Rooms</th></tr>${rowsFor('room')}
            <tr class="group"><th colspan="${colspan}">Shared equipment</th></tr>${rowsFor('equipment')}
          </tbody>
        </table>
      </div>
      ${unplaced.length ? `<p class="small muted">Also in Microsoft Bookings (not linked to a program, blocks nothing): ${unplaced.map((x) => `${esc(x.date)} ${esc(x.start)} ${esc(x.label)}`).join(' · ')}</p>` : ''}
      <p class="small muted">${data.bookings.length ? 'Click a booking for details.' : 'No bookings in this period.'} Allowed pairs (e.g. Creative TechStyles + Medical Emergency) can appear in the same room.</p>
      <div id="detail" class="card detail-panel" hidden></div>`;

    view.querySelector('#prev').onclick = () => ((state.date = addDays(state.date, -step)), load());
    view.querySelector('#next').onclick = () => ((state.date = addDays(state.date, step)), load());
    view.querySelector('#reset-demo')?.addEventListener('click', () => resetDemo().then(load));
    view.querySelector('#today').onclick = () => ((state.date = me.today), load());
    view.querySelector('#board-date').onchange = (e) => e.target.value && ((state.date = e.target.value), load());
    view.querySelectorAll('[data-view]').forEach((b) => (b.onclick = () => ((state.view = b.dataset.view), load())));
    view.querySelectorAll('[data-booking]').forEach(
      (b) =>
        (b.onclick = () => {
          const detail = view.querySelector('#detail');
          detail.hidden = false;
          detail.innerHTML = `<h2>${esc(byId.get(Number(b.dataset.booking)).programName)}</h2>` + bookingDetails(byId.get(Number(b.dataset.booking)));
          detail.querySelector('[data-cancel]')?.addEventListener('click', (e) => cancelBooking(e.target.dataset.cancel, load));
          detail.querySelector('[data-retry]')?.addEventListener('click', (e) => retrySync(e.target.dataset.retry, load));
          detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }),
    );
  }
  await load();
}

// ======================================================================== bookings list
async function renderBookings() {
  const catalog = await api('/admin/api/catalog');
  const filters = Object.fromEntries(new URLSearchParams(location.search));
  view.innerHTML = `
    <h1>Bookings</h1>
    <form class="toolbar" id="filters">
      <div class="field"><label for="q">Search</label><input id="q" name="q" type="search" placeholder="School, contact, program, PB-…" value="${esc(filters.q || '')}"></div>
      <div class="field"><label for="programId">Program</label><select id="programId" name="programId"><option value="">All programs</option>
        ${catalog.programs.map((p) => `<option value="${esc(p.id)}" ${filters.programId === p.id ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select></div>
      <div class="field"><label for="status">Status</label><select id="status" name="status">
        ${[['', 'Any'], ['confirmed', 'Confirmed'], ['cancelled', 'Cancelled']].map(([v, l]) => `<option value="${v}" ${filters.status === v ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      <div class="field"><label for="syncStatus">Sync</label><select id="syncStatus" name="syncStatus">
        ${[['', 'Any'], ['synced', 'Synced'], ['pending', 'Pending'], ['failed', 'Failed'], ['none', 'Not synced']].map(([v, l]) => `<option value="${v}" ${filters.syncStatus === v ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      <div class="field"><label for="from">From</label><input id="from" name="from" type="date" value="${esc(filters.from || '')}"></div>
      <div class="field"><label for="to">To</label><input id="to" name="to" type="date" value="${esc(filters.to || '')}"></div>
      <button class="button small" type="submit">Filter</button>
      <span class="spacer"></span>
      <a class="button secondary small" id="csv" href="#">Export CSV</a>
    </form>
    <div id="results"></div>
    <div id="detail" class="card detail-panel" hidden></div>`;

  const form = view.querySelector('#filters');
  async function load() {
    const query = new URLSearchParams([...new FormData(form)].filter(([, v]) => v)).toString();
    history.replaceState(null, '', `/admin/bookings${query ? `?${query}` : ''}`);
    view.querySelector('#csv').href = `/admin/api/bookings.csv${query ? `?${query}` : ''}`;
    const { bookings } = await api(`/admin/api/bookings${query ? `?${query}` : ''}`);
    view.querySelector('#results').innerHTML = bookings.length
      ? `<p class="muted small">${bookings.length} booking${bookings.length === 1 ? '' : 's'}</p>
        <div class="table-wrap"><table class="data">
          <thead><tr><th>Ref</th><th>Date</th><th>Program</th><th>School</th><th>Classes</th><th>Rooms / kit</th><th>Status</th><th>Sync</th><th><span class="visually-hidden">Actions</span></th></tr></thead>
          <tbody>${bookings
            .map(
              (b) => `<tr class="${b.status}">
                <td class="nowrap">${esc(b.reference)}</td>
                <td class="nowrap">${esc(shortDate(b.date))} ${esc(b.date.slice(0, 4))}</td>
                <td>${esc(b.programName)}</td>
                <td>${esc(b.school)}<br><span class="small muted">${esc(b.contactName)}</span></td>
                <td>${b.classes}</td>
                <td class="small">${esc(b.resources.join(', '))}</td>
                <td><span class="badge ${b.status === 'cancelled' ? 'bad' : 'ok'}">${esc(b.status)}</span></td>
                <td>${syncBadge(b.syncStatus, b.syncError)}</td>
                <td class="actions"><button class="button secondary small" data-view-booking="${b.id}">View</button></td>
              </tr>`,
            )
            .join('')}</tbody></table></div>`
      : '<div class="card empty">No bookings match.</div>';
    view.querySelectorAll('[data-view-booking]').forEach(
      (btn) =>
        (btn.onclick = () => {
          const b = bookings.find((x) => x.id === Number(btn.dataset.viewBooking));
          const detail = view.querySelector('#detail');
          detail.hidden = false;
          detail.innerHTML = `<h2>${esc(b.programName)} — ${esc(b.school)}</h2>${bookingDetails(b)}`;
          detail.querySelector('[data-cancel]')?.addEventListener('click', (e) => cancelBooking(e.target.dataset.cancel, load));
          detail.querySelector('[data-retry]')?.addEventListener('click', (e) => retrySync(e.target.dataset.retry, load));
          detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }),
    );
  }
  form.addEventListener('submit', (e) => (e.preventDefault(), load()));
  form.addEventListener('change', load);
  await load();
}

// =========================================================================== rule tester
async function renderRules() {
  const catalog = await api('/admin/api/catalog');
  const params = new URLSearchParams(location.search);
  view.innerHTML = `
    <h1>Rule tester</h1>
    <p class="muted">Pick a program, date and number of classes to see exactly what the booking engine decides — and why.</p>
    <form class="toolbar card" id="rule-form">
      <div class="field"><label for="rt-program">Program</label><select id="rt-program" name="programId">
        ${catalog.categories.map((c) => `<optgroup label="${esc(c.name)}">${catalog.programs.filter((p) => p.category === c.id).map((p) => `<option value="${esc(p.id)}" ${params.get('programId') === p.id ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</optgroup>`).join('')}
      </select></div>
      <div class="field"><label for="rt-date">Date</label><input id="rt-date" name="date" type="date" required value="${esc(params.get('date') || me.today)}"></div>
      <div class="field"><label for="rt-classes">Classes</label><input id="rt-classes" name="classes" type="number" min="1" max="9" value="${esc(params.get('classes') || '1')}"></div>
      ${catalog.settings.slots.length > 1 ? `<div class="field"><label for="rt-slot">Slot</label><select id="rt-slot" name="slotId">${catalog.settings.slots.map((s) => `<option value="${esc(s.id)}">${esc(s.label)}</option>`).join('')}</select></div>` : ''}
      <button class="button" type="submit">Check</button>
    </form>
    <div id="rt-result" aria-live="polite"></div>`;

  const form = view.querySelector('#rule-form');
  async function run(e) {
    e?.preventDefault();
    const body = Object.fromEntries(new FormData(form));
    history.replaceState(null, '', `/admin/rules?${new URLSearchParams(body)}`);
    const out = view.querySelector('#rt-result');
    try {
      const r = await api('/admin/api/rule-test', { method: 'POST', body });
      const program = catalog.programs.find((p) => p.id === body.programId);
      out.innerHTML = `
        <div class="two-col" style="margin-top:16px">
          <div class="card">
            <h2>${r.ok ? '✅ Can be booked' : '⛔ Blocked'}</h2>
            <p>${esc(program.name)} · ${esc(longDate(body.date))} · ${plural(Number(body.classes), 'class')}</p>
            ${r.ok ? `<p><strong>Rooms/kit it would get:</strong> ${esc(r.assignedResourceNames.join(', ') || '—')}</p>` : `<ul class="reason-list">${r.reasons.map((x) => `<li><span class="type">${esc(x.type)}</span>${esc(x.message)}<br><span class="small muted">Public site shows: “${esc(x.public)}”</span></li>`).join('')}</ul>`}
            ${r.staff ? `<p style="margin-top:12px"><strong>Staff:</strong> ${r.staff.used} of ${r.staff.pool} ${esc(r.staff.name)} already booked; this needs ${r.staff.needed}.</p>` : ''}
          </div>
          <div class="card">
            <h2>Program rules</h2>
            <p><strong>Needs:</strong></p><ul>${program.requirementsText.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>
            <p><strong>Combination rules:</strong> ${esc(program.rulesText.join('; ') || 'none')}</p>
            <p><strong>Max:</strong> ${plural(program.max_classes, 'class')} · <strong>Staff:</strong> ${program.staff_required} · <strong>When:</strong> ${esc(program.semesterLabel)}</p>
            <h3 style="margin-top:16px">Already booked that day</h3>
            ${r.sameDay.length || r.externalBusy.length ? `<ul>${r.sameDay.map((b) => `<li>${esc(b.programName)} — ${esc(b.school)} <span class="small muted">(${esc(b.resources.join(', '))})</span></li>`).join('')}${r.externalBusy.map((x) => `<li>Microsoft Bookings: ${esc(x.label)} ${esc(x.start)}–${esc(x.end)}</li>`).join('')}</ul>` : '<p class="muted">Nothing.</p>'}
          </div>
        </div>`;
    } catch (err) {
      out.innerHTML = `<div class="notice error">${esc(err.message)}</div>`;
    }
  }
  form.addEventListener('submit', run);
  form.addEventListener('change', run);
  await run();
}

// ============================================================================ catalog view
async function renderCatalog() {
  const c = await api('/admin/api/catalog');
  const s = c.settings;
  view.innerHTML = `
    <h1>Catalog</h1>
    <p class="muted">Read-only view of <span class="code">${esc(c.file)}</span>. To change a rule, edit that file and restart (run <span class="code">npm run catalog:check</span> first).</p>
    <div class="two-col">
      <div class="card"><h2>Settings</h2><dl class="kv">
        <dt>Class size</dt><dd>${s.class_size} students</dd>
        <dt>Staff pool</dt><dd>${s.staff_pool.size} ${esc(s.staff_pool.name)}</dd>
        <dt>Slots</dt><dd>${s.slots.map((x) => `${esc(x.label)} ${esc(x.start)}–${esc(x.end)}`).join('<br>')}</dd>
        <dt>Semesters</dt><dd>${Object.entries(s.semesters).map(([k, r]) => `${esc(k)}: ${r.map((x) => `${esc(x.from)} → ${esc(x.to)}`).join(', ')}`).join('<br>')}</dd>
        <dt>Blackouts</dt><dd>${s.blackouts.map((b) => `${esc(b.date)} ${esc(b.reason)}`).join('<br>') || 'none'}</dd>
        <dt>Allowed pairs share rooms</dt><dd>${s.allowed_pairs_share_rooms ? 'Yes' : 'No'}</dd>
      </dl></div>
      <div class="card"><h2>Rooms &amp; tracked equipment</h2><dl class="kv">
        <dt>Rooms</dt><dd>${c.resources.filter((r) => r.type === 'room').map((r) => esc(r.name)).join(', ')}</dd>
        <dt>Equipment</dt><dd>${c.resources.filter((r) => r.type === 'equipment').map((r) => esc(r.name)).join(', ')}</dd>
      </dl></div>
    </div>
    ${c.categories
      .map(
        (cat) => `<h2 class="section-title">${esc(cat.name)}</h2>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>Program</th><th>When</th><th>Max</th><th>Staff</th><th>Needs (all of)</th><th>Combination rules</th><th>Staff notes</th><th>Bookings service</th></tr></thead>
        <tbody>${c.programs
          .filter((p) => p.category === cat.id)
          .map(
            (p) => `<tr><td><strong>${esc(p.name)}</strong><br><span class="code">${esc(p.id)}</span>${p.active ? '' : ' <span class="badge bad">inactive</span>'}</td>
              <td>${esc(p.semesterLabel)}</td><td class="nowrap">${plural(p.max_classes, 'class')}</td><td>${p.staff_required}</td>
              <td>${p.requirementsText.map((t) => `• ${esc(t)}`).join('<br>')}</td>
              <td>${esc(p.rulesText.join('; ') || '—')}</td>
              <td class="small">${p.notes.map(esc).join('<br>') || '—'}</td>
              <td class="small">${p.bookings_service_id ? `<span class="code">${esc(p.bookings_service_id)}</span>` : '<span class="muted">not linked</span>'}</td></tr>`,
          )
          .join('')}</tbody></table></div>`,
      )
      .join('')}`;
}

// ========================================================================= calendar & sync
async function renderSync() {
  const d = await api('/admin/api/sync');
  const st = d.status || {};
  const modeText = {
    none: 'Off — bookings stay in this system. Outlook calendar feeds (below) still work.',
    email: 'Email invites — each booking is sent as a calendar invite to the addresses below.',
    graph: 'Microsoft Bookings (Graph API) — bookings are created as Bookings appointments, and appointments made in Bookings are imported.',
    webhook: 'Power Automate — each booking and cancellation is sent to your flow, which updates the Outlook / Bookings calendars.',
  }[d.mode];
  const pa = d.powerAutomate;
  const last = pa.lastInbound;
  view.innerHTML = `
    <h1>Calendar &amp; Microsoft 365 sync</h1>
    <div class="two-col">
      <div class="card">
        <h2>Sync mode: <span class="code">${esc(d.mode)}</span></h2>
        <p>${esc(modeText)}</p>
        ${d.mode === 'email' ? `<p><strong>Invites go to:</strong> ${esc(d.email.inviteAddresses.join(', ') || '(none set — INVITE_ADDRESSES)')}<br><strong>Delivery:</strong> ${d.email.smtp ? 'SMTP' : 'written to data/outbox/*.eml (no SMTP_HOST set)'}</p>` : ''}
        ${d.mode === 'graph' ? `<p><strong>Bookings business:</strong> <span class="code">${esc(d.graph.businessId || '(BOOKINGS_BUSINESS_ID not set)')}</span><br>
          <strong>Programs without a <span class="code">bookings_service_id</span>:</strong> ${d.unmappedPrograms.length}<br><span class="small muted">These link to a Bookings service with exactly the same name, if one exists. Run <span class="code">npm run graph:check</span> to see how every program is linked.</span></p>` : ''}
        ${d.mode !== 'none' ? `<dl class="kv">
          <dt>Last sync run</dt><dd>${esc(st.lastRunAt ? new Date(st.lastRunAt).toLocaleString('en-AU') : 'not yet')}</dd>
          ${d.mode === 'graph' ? `<dt>Last import</dt><dd>${esc(st.lastImportAt ? new Date(st.lastImportAt).toLocaleString('en-AU') : 'not yet')} ${st.lastImportCount != null ? `(${st.lastImportCount} appointments)` : ''}</dd>` : ''}
          ${st.lastError ? `<dt>Last error</dt><dd class="small">${esc(st.lastError)}</dd>` : ''}
          <dt>Automatic retry</dt><dd>every ${st.intervalMinutes || 15} minutes</dd>
        </dl>
        <p style="margin-top:12px"><button class="button small" id="run-sync">Sync now</button></p>` : '<p class="small muted">Set <span class="code">SYNC_MODE=email</span> or <span class="code">SYNC_MODE=graph</span> to turn on sync — see the README.</p>'}
      </div>
      <div class="card">
        <h2>Outlook calendar feeds</h2>
        ${
          d.feeds
            ? `<p>In Outlook: <em>Add calendar → Subscribe from web</em>, then paste a link. Outlook refreshes it every few hours. Keep these links private.</p>
               <p><strong>All bookings</strong><br><span class="code">${esc(d.feeds.all)}</span></p>
               <details><summary>One calendar per room / kit</summary><ul>${d.feeds.rooms.map((r) => `<li>${esc(r.name)}<br><span class="code">${esc(r.url)}</span></li>`).join('')}</ul></details>`
            : '<p class="notice warn">Feeds are off until <span class="code">CALENDAR_FEED_TOKEN</span> is set to a long random value.</p>'
        }
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <h2>Power Automate</h2>
      <div class="two-col">
        <div>
          <h3>Website → Microsoft 365</h3>
          <p>${pa.outboundUrlSet ? '✔ Flow URL is set.' : '✖ <span class="code">POWER_AUTOMATE_WEBHOOK_URL</span> is not set.'}
            ${d.mode === 'webhook' ? 'Bookings are sent automatically.' : 'Set <span class="code">SYNC_MODE=webhook</span> to send every booking.'}</p>
          <p style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="button secondary small" id="test-webhook" ${pa.outboundUrlSet ? '' : 'disabled'}>Send test to flow</button>
            <a class="button secondary small" href="/admin/api/sync/sample-payload" target="_blank" rel="noopener">Sample JSON ↗</a>
          </p>
        </div>
        <div>
          <h3>Microsoft Bookings → website</h3>
          ${pa.inboundEnabled
            ? `<p>Flows POST to:<br><span class="code">${esc(pa.inboundUrl)}</span><br><span class="small muted">with header <span class="code">Authorization: Bearer &lt;INBOUND_WEBHOOK_SECRET&gt;</span></span></p>
               <p><strong>Appointments held from Bookings:</strong> ${pa.importedCount}<br>
               <strong>Last received:</strong> ${last ? `${esc(new Date(last.at).toLocaleString('en-AU'))} — ${esc(last.action)} <details><summary class="small">what the flow sent</summary><pre class="code" style="white-space:pre-wrap">${esc(JSON.stringify(last.body, null, 2))}</pre></details>` : 'nothing yet'}</p>`
            : '<p>Off — set <span class="code">INBOUND_WEBHOOK_SECRET</span> to a long random value to turn it on.</p>'}
        </div>
      </div>
      <p class="small muted">Setup steps: <span class="code">docs/POWER-AUTOMATE-SETUP.md</span></p>
    </div>
    ${me.demoMode ? `<div class="card" style="margin-top:16px"><h2>Demo controls</h2><p>Delete all bookings and load the example bookings for the next four weeks. ${d.mode !== 'none' ? '<strong>Bookings already sent to Outlook/Microsoft Bookings are not removed there.</strong>' : ''}</p><button class="button danger small" id="reset-demo">Reset demo data</button></div>` : ''}
    <h2 class="section-title">Needing sync <span class="count">${d.needingSync.length}</span></h2>
    ${d.needingSync.length ? `<div class="table-wrap"><table class="data"><thead><tr><th>Ref</th><th>Date</th><th>Program</th><th>Status</th><th>Sync</th><th>Error</th><th></th></tr></thead><tbody>
      ${d.needingSync.map((b) => `<tr><td>${esc(b.reference)}</td><td>${esc(b.date)}</td><td>${esc(b.programName)}</td><td>${esc(b.status)}</td><td>${syncBadge(b.syncStatus)}</td><td class="small">${esc(b.syncError || '')}</td><td><button class="button secondary small" data-retry="${b.id}">Retry</button></td></tr>`).join('')}
    </tbody></table></div>` : '<p class="muted">Nothing waiting.</p>'}
    <h2 class="section-title">Recent activity</h2>
    <div class="table-wrap"><table class="data"><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Booking</th><th>Detail</th></tr></thead><tbody>
      ${d.audit.map((a) => `<tr><td class="nowrap small">${esc(new Date(a.at).toLocaleString('en-AU'))}</td><td class="small">${esc(a.actor || '')}</td><td>${esc(a.action)}</td><td>${a.booking_id ?? ''}</td><td class="small">${esc(a.detail || '')}</td></tr>`).join('')}
    </tbody></table></div>`;

  view.querySelector('#run-sync')?.addEventListener('click', async (e) => {
    e.target.disabled = true;
    try {
      const r = await api('/admin/api/sync/run', { method: 'POST' });
      announce(message, `Sync finished: ${r.synced} synced, ${r.failed} failed${r.imported != null ? `, ${r.imported} imported from Bookings` : ''}.`, r.failed ? 'warn' : 'success');
    } catch (err) {
      announce(message, esc(err.message), 'error');
    }
    renderSync();
  });
  view.querySelectorAll('[data-retry]').forEach((b) => b.addEventListener('click', () => retrySync(b.dataset.retry, renderSync)));
  view.querySelector('#test-webhook')?.addEventListener('click', async () => {
    try {
      await api('/admin/api/sync/test-webhook', { method: 'POST' });
      announce(message, 'Test sent — check the flow’s run history in Power Automate.', 'success');
    } catch (err) {
      announce(message, esc(err.message), 'error');
    }
  });
  view.querySelector('#reset-demo')?.addEventListener('click', resetDemo);
}

async function resetDemo() {
  if (!confirm('Delete ALL bookings and reload the demo bookings?')) return;
  try {
    const r = await api('/admin/api/demo/reset', { method: 'POST' });
    announce(message, `Demo data reset: ${r.created} example bookings loaded.${r.skipped.length ? ` Skipped: ${esc(r.skipped.join('; '))}` : ''}`, 'success');
    if (section === 'sync') renderSync();
  } catch (err) {
    announce(message, esc(err.message), 'error');
  }
}

// ================================================================================ start
document.getElementById('logout').addEventListener('click', async () => {
  await baseApi('/admin/api/logout', { method: 'POST', body: {} }).catch(() => {});
  location.href = '/admin';
});

try {
  me = await api('/admin/api/me');
  document.getElementById('who').textContent = me.user?.name || me.user?.email || '';
  // Viewers can look but not change: hide every change button (the server enforces this too).
  if (me.user?.role !== 'manager') document.body.classList.add('viewer');
  setupPage({ demoMode: me.demoMode });
  const navHref = section === 'board' ? '/admin' : `/admin/${section}`;
  document.querySelector(`.site-nav a[href="${navHref}"]`)?.setAttribute('aria-current', 'page');
  const titles = { board: 'Day board', bookings: 'Bookings', rules: 'Rule tester', catalog: 'Catalog', sync: 'Calendar & sync' };
  document.title = `${titles[section] || 'Admin'} · Admin`;
  setupPage({ demoMode: false });
  await ({ board: renderBoard, bookings: renderBookings, rules: renderRules, catalog: renderCatalog, sync: renderSync }[section] || renderBoard)();
} catch (err) {
  view.innerHTML = `<div class="notice error">Something went wrong: ${esc(err.message)}</div>`;
}
