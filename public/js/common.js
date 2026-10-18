// Helpers shared by every page.

/** Escapes text before putting it into HTML. */
export function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** fetch() wrapper: sends/receives JSON and throws an Error with a readable message on failure. */
export async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'same-origin',
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* not JSON */
  }
  if (!res.ok) {
    const err = new Error(data?.error || `Request failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

/** "2027-03-02" → "Tuesday 2 March 2027" */
export function longDate(date) {
  return new Intl.DateTimeFormat('en-AU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${date}T00:00:00Z`));
}

/** "2027-03-02" → "Tue 2 Mar" */
export function shortDate(date) {
  return new Intl.DateTimeFormat('en-AU', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(
    new Date(`${date}T00:00:00Z`),
  );
}

export function addDays(date, days) {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function plural(n, word, pluralWord = `${word}es`) {
  return `${n} ${n === 1 ? word : pluralWord}`;
}

/** Applies the site name from theme.css and shows the demo banner if needed. */
export function setupPage({ demoMode } = {}) {
  const name = getComputedStyle(document.documentElement)
    .getPropertyValue('--site-name')
    .trim()
    .replace(/^["']|["']$/g, '');
  if (name) {
    document.querySelectorAll('[data-site-name]').forEach((el) => (el.textContent = name));
    if (!document.title.includes(name)) document.title = document.title ? `${document.title} · ${name}` : name;
  }
  if (demoMode && !document.querySelector('.demo-banner')) {
    const banner = document.createElement('div');
    banner.className = 'demo-banner';
    banner.setAttribute('role', 'note');
    banner.textContent = 'Demo site — the bookings shown are examples, and no real bookings are made.';
    document.body.prepend(banner);
  }
}

/** Announces a message to screen readers (and shows it if the element is visible). */
export function announce(el, html, kind = '') {
  el.className = kind ? `notice ${kind}` : '';
  el.innerHTML = html;
  el.hidden = !html;
}
