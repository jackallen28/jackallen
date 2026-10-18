// Programs page: cards grouped by category, with filter chips.

import { api, esc, setupPage, plural } from './common.js';

const state = { category: 'all', semester: 'any', classes: 'any' };
let catalog;

function chip(group, value, label) {
  const pressed = state[group] === value;
  return `<button type="button" class="chip" data-group="${group}" data-value="${esc(value)}" aria-pressed="${pressed}">${esc(label)}</button>`;
}

function renderFilters() {
  const semesters = Object.keys(catalog.semesters);
  const maxClasses = Math.max(...catalog.programs.map((p) => p.maxClasses));
  const legend = (id) => document.querySelector(`#${id} legend`).outerHTML;

  document.getElementById('filter-category').innerHTML =
    legend('filter-category') +
    chip('category', 'all', 'All') +
    catalog.categories.map((c) => chip('category', c.id, c.name)).join('');

  document.getElementById('filter-semester').innerHTML =
    legend('filter-semester') +
    chip('semester', 'any', 'Any') +
    semesters.map((s) => chip('semester', s, s.replace(/^S(\d)$/, 'Semester $1'))).join('');

  const sizes = [];
  for (let n = 1; n <= maxClasses; n++) sizes.push(n);
  document.getElementById('filter-classes').innerHTML =
    legend('filter-classes') +
    chip('classes', 'any', 'Any') +
    sizes.map((n) => chip('classes', String(n), `${plural(n, 'class')} (${n * catalog.classSize})`)).join('');
}

function matches(p) {
  if (state.category !== 'all' && p.category !== state.category) return false;
  if (state.semester !== 'any' && !p.semesters.includes(state.semester)) return false;
  if (state.classes !== 'any' && p.maxClasses < Number(state.classes)) return false;
  return true;
}

function card(p) {
  return `
    <a class="card program-card" href="/program/${encodeURIComponent(p.id)}">
      <div class="meta">
        <span class="badge cat-${esc(p.category)}">${esc(p.categoryName)}</span>
        <span class="badge">${esc(p.semesterLabel)}</span>
      </div>
      <h3>${esc(p.name)}</h3>
      <ul class="facts">
        <li><span class="visually-hidden">Group size: </span>Up to ${p.maxStudents} students (${plural(p.maxClasses, 'class')})</li>
        <li><span class="visually-hidden">Rooms: </span>${esc(p.rooms.join(' · '))}</li>
      </ul>
      <span class="cta" aria-hidden="true">See dates →</span>
    </a>`;
}

function renderPrograms() {
  const visible = catalog.programs.filter(matches);
  const container = document.getElementById('programs');
  document.getElementById('result-count').textContent = `Showing ${visible.length} of ${catalog.programs.length} programs`;
  if (!visible.length) {
    container.innerHTML = '<div class="card empty">No programs match those filters.</div>';
    return;
  }
  container.innerHTML = catalog.categories
    .map((c) => {
      const programs = visible.filter((p) => p.category === c.id);
      if (!programs.length) return '';
      return `
        <section aria-labelledby="cat-${esc(c.id)}">
          <h2 class="section-title" id="cat-${esc(c.id)}">${esc(c.name)} <span class="count">${programs.length}</span></h2>
          <div class="program-grid">${programs.map(card).join('')}</div>
        </section>`;
    })
    .join('');
}

document.addEventListener('click', (e) => {
  const button = e.target.closest('.chip');
  if (!button) return;
  state[button.dataset.group] = button.dataset.value;
  renderFilters();
  renderPrograms();
  // keep keyboard focus on the chip that was pressed
  document.querySelector(`.chip[data-group="${button.dataset.group}"][data-value="${button.dataset.value}"]`)?.focus();
});

try {
  catalog = await api('/api/catalog');
  setupPage(catalog);
  renderFilters();
  renderPrograms();
} catch (err) {
  setupPage();
  document.getElementById('programs').innerHTML = `<div class="notice error">Could not load programs: ${esc(err.message)}</div>`;
}
