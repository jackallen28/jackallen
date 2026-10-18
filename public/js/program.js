// Program page: details, availability calendar, slot picker and booking form.

import { api, esc, setupPage, longDate, shortDate, addDays, plural, announce } from './common.js';

const programId = decodeURIComponent(location.pathname.split('/').filter(Boolean).pop());
const page = document.getElementById('page');

const state = {
  classes: 1,
  date: null,
  slotId: null,
  cache: new Map(), // date → [{ slotId, ok, reasons }]
};

let catalog;
let program;
let calendar;

// ---- data ----------------------------------------------------------------------------
async function fetchAvailability(from, to) {
  const data = await api(
    `/api/programs/${encodeURIComponent(programId)}/availability?from=${from}&to=${to}&classes=${state.classes}`,
  );
  for (const day of data.days) {
    if (!state.cache.has(day.date)) state.cache.set(day.date, []);
    const list = state.cache.get(day.date);
    const i = list.findIndex((s) => s.slotId === day.slotId);
    if (i >= 0) list[i] = day;
    else list.push(day);
  }
  return data.days;
}

function dayStatus(slots) {
  return slots.some((s) => s.ok) ? 'ok' : 'no';
}

function slotInfo(slotId) {
  return catalog.slots.find((s) => s.id === slotId) || { id: slotId, label: slotId, start: '', end: '' };
}

// ---- rendering -------------------------------------------------------------------------
function renderDetails() {
  document.title = program.name;
  document.getElementById('program-name').textContent = program.name;
  const facts = [
    ['Program type', `<span class="badge cat-${esc(program.category)}">${esc(program.categoryName)}</span>`],
    ['When', esc(program.semesterLabel)],
    ['Group size', `Up to ${program.maxStudents} students (${plural(program.maxClasses, 'class')} of ${catalog.classSize})`],
    ['Rooms', esc(program.rooms.join(', '))],
    program.equipment.length ? ['What students use', esc(program.equipment.join(', '))] : null,
    program.software.length ? ['Software', esc(program.software.join(', '))] : null,
    program.rotation === 'fixed-order' ? ['Format', 'Rotations run in a set order'] : null,
  ].filter(Boolean);
  document.getElementById('program-facts').innerHTML = facts
    .map(([label, value]) => `<li><strong>${label}</strong>${value}</li>`)
    .join('');

  const select = document.getElementById('classes');
  const wanted = Number(new URLSearchParams(location.search).get('classes')) || 1;
  state.classes = Math.min(Math.max(wanted, 1), program.maxClasses);
  select.innerHTML = Array.from({ length: program.maxClasses }, (_, i) => i + 1)
    .map((n) => `<option value="${n}" ${n === state.classes ? 'selected' : ''}>${plural(n, 'class')} (${n * catalog.classSize} students)</option>`)
    .join('');
  select.addEventListener('change', () => {
    state.classes = Number(select.value);
    refreshAvailability();
  });
}

function setupCalendar() {
  calendar = new FullCalendar.Calendar(document.getElementById('calendar'), {
    initialView: 'dayGridMonth',
    firstDay: 1,
    weekends: false,
    height: 'auto',
    fixedWeekCount: false,
    showNonCurrentDates: false,
    locale: 'en-au',
    validRange: { start: catalog.today },
    headerToolbar: { left: 'prev,next', center: 'title', right: 'today' },
    buttonText: { today: 'Today' },
    events: async (info, success, failure) => {
      try {
        const from = info.startStr.slice(0, 10) < catalog.today ? catalog.today : info.startStr.slice(0, 10);
        const to = addDays(info.endStr.slice(0, 10), -1);
        if (to < from) return success([]);
        await fetchAvailability(from, to);
        const events = [];
        for (const [date, slots] of state.cache) {
          if (date < from || date > to) continue;
          const ok = dayStatus(slots) === 'ok';
          events.push({
            start: date,
            allDay: true,
            title: ok ? 'Available' : 'Unavailable',
            classNames: [ok ? 'avail-ok' : 'avail-no'],
          });
        }
        success(events);
      } catch (err) {
        failure(err);
        announce(document.getElementById('calendar-message'), `Could not load availability: ${esc(err.message)}`, 'error');
      }
    },
    eventClick: (info) => selectDate(info.event.startStr.slice(0, 10)),
    dateClick: (info) => selectDate(info.dateStr),
    // Full word on wide screens, short word on phones (both read out the full word).
    eventContent: (arg) => {
      const ok = arg.event.classNames.includes('avail-ok');
      return {
        html: `<span class="fc-event-title"><span class="label-long">${arg.event.title}</span><span class="label-short" aria-hidden="true">${ok ? 'Free' : 'Full'}</span></span>`,
      };
    },
    dayCellClassNames: (arg) => (toDateString(arg.date) === state.date ? ['is-selected'] : []),
  });
  calendar.render();
}

function toDateString(d) {
  // FullCalendar gives local-midnight Date objects for day cells.
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

async function renderNextDates() {
  const box = document.getElementById('next-dates');
  box.innerHTML = '<span class="muted small">Loading…</span>';
  try {
    const days = await fetchAvailability(catalog.today, addDays(catalog.today, 120));
    const dates = [...new Set(days.filter((d) => d.ok).map((d) => d.date))].slice(0, 8);
    box.innerHTML = dates.length
      ? dates.map((d) => `<button type="button" class="button secondary small" data-date="${d}">${shortDate(d)}</button>`).join('')
      : '<span class="muted small">No available dates in the next four months for this number of classes.</span>';
  } catch (err) {
    box.innerHTML = `<span class="muted small">Could not load dates (${esc(err.message)}).</span>`;
  }
}

async function selectDate(date) {
  if (date < catalog.today) return;
  state.date = date;
  state.slotId = null;
  calendar.render(); // refresh the "selected" outline
  if (!state.cache.has(date)) await fetchAvailability(date, date);
  const slots = state.cache.get(date) || [];

  const section = document.getElementById('slot-section');
  section.hidden = false;
  document.getElementById('slot-heading').textContent = longDate(date);
  document.getElementById('slots').innerHTML = slots
    .map((s) => {
      const info = slotInfo(s.slotId);
      const time = `<strong>${esc(info.label)}</strong> <span class="muted">${esc(info.start)}–${esc(info.end)}</span>`;
      if (s.ok) {
        return `<li class="slot ok"><span>${time}<br><span class="why">Available for ${plural(state.classes, 'class')}</span></span>
          <button type="button" class="button small" data-slot="${esc(s.slotId)}">Choose this time</button></li>`;
      }
      const why = s.reasons.map((r) => esc(r.message)).join('<br>');
      return `<li class="slot no"><span>${time}<br><span class="why">${why || 'Unavailable'}</span></span></li>`;
    })
    .join('');

  const available = slots.filter((s) => s.ok);
  document.getElementById('form-section').hidden = true;
  if (available.length === 1 && slots.length === 1) {
    chooseSlot(available[0].slotId, { focus: false });
  }
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function chooseSlot(slotId, { focus = true } = {}) {
  state.slotId = slotId;
  const info = slotInfo(slotId);
  document.querySelectorAll('#slots [data-slot]').forEach((b) => {
    const selected = b.dataset.slot === slotId;
    b.textContent = selected ? 'Selected ✓' : 'Choose this time';
    b.setAttribute('aria-pressed', String(selected));
  });
  document.getElementById('booking-summary').innerHTML =
    `<strong>${esc(program.name)}</strong><br>${esc(longDate(state.date))}, ${esc(info.label)} (${esc(info.start)}–${esc(info.end)})<br>` +
    `${plural(state.classes, 'class')} · ${state.classes * catalog.classSize} students`;
  announce(document.getElementById('form-message'), '');
  const section = document.getElementById('form-section');
  section.hidden = false;
  if (focus) {
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    document.getElementById('school').focus({ preventScroll: true });
  }
}

async function refreshAvailability() {
  state.cache.clear();
  document.getElementById('form-section').hidden = true;
  document.getElementById('slot-section').hidden = true;
  state.slotId = null;
  calendar.refetchEvents();
  await renderNextDates();
  if (state.date) await selectDate(state.date);
}

// ---- booking form -----------------------------------------------------------------------
function showFieldErrors(fields = {}) {
  const form = document.getElementById('booking-form');
  let first = null;
  for (const input of form.querySelectorAll('input, textarea, select')) {
    const errorEl = document.getElementById(`${input.name}-error`);
    const message = fields[input.name];
    if (errorEl) errorEl.textContent = message || '';
    if (message) {
      input.setAttribute('aria-invalid', 'true');
      first ??= input;
    } else {
      input.removeAttribute('aria-invalid');
    }
  }
  first?.focus();
}

async function submitBooking(e) {
  e.preventDefault();
  const form = e.target;
  const button = document.getElementById('submit-button');
  const message = document.getElementById('form-message');
  const body = Object.fromEntries(new FormData(form));
  Object.assign(body, { programId, date: state.date, slotId: state.slotId, classes: state.classes });

  button.disabled = true;
  button.textContent = 'Booking…';
  showFieldErrors({});
  announce(message, '');
  try {
    const result = await api('/api/bookings', { method: 'POST', body });
    location.href = `/manage/${encodeURIComponent(result.manageToken)}?new=1`;
  } catch (err) {
    if (err.status === 400) {
      announce(message, 'Please check the highlighted fields.', 'error');
      showFieldErrors(err.data?.fields);
    } else if (err.status === 409) {
      // Someone else got there first (or the rules changed). Show the calendar again.
      const reasons = (err.data?.reasons || []).map((r) => `<li>${esc(r.message)}</li>`).join('');
      announce(
        document.getElementById('calendar-message'),
        `<strong>${esc(err.message)}</strong>${reasons ? `<ul>${reasons}</ul>` : ''} Your details are still filled in.`,
        'warn',
      );
      await refreshAvailability();
      document.getElementById('step2').scrollIntoView({ behavior: 'smooth' });
    } else {
      announce(message, esc(err.message), 'error');
    }
  } finally {
    button.disabled = false;
    button.textContent = 'Confirm booking';
  }
}

// ---- start ---------------------------------------------------------------------------------
try {
  [catalog, program] = await Promise.all([api('/api/catalog'), api(`/api/programs/${encodeURIComponent(programId)}`)]);
  setupPage(catalog);
  page.innerHTML = '';
  page.append(document.getElementById('program-template').content.cloneNode(true));
  renderDetails();
  setupCalendar();
  renderNextDates();

  document.getElementById('next-dates').addEventListener('click', (e) => {
    const b = e.target.closest('[data-date]');
    if (!b) return;
    calendar.gotoDate(b.dataset.date);
    selectDate(b.dataset.date);
  });
  document.getElementById('slots').addEventListener('click', (e) => {
    const b = e.target.closest('[data-slot]');
    if (b) chooseSlot(b.dataset.slot);
  });
  document.getElementById('booking-form').addEventListener('submit', submitBooking);
} catch (err) {
  setupPage();
  page.innerHTML =
    err.status === 404
      ? '<div class="notice error">Sorry, we couldn’t find that program. <a href="/">See all programs</a>.</div>'
      : `<div class="notice error">Something went wrong: ${esc(err.message)}</div>`;
}
