// Plain date helpers. Dates are always strings "YYYY-MM-DD" and times "HH:MM" (local time),
// so there are no timezone surprises inside the clash engine.

export function isValidDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const d = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === value;
}

/** 0 = Sunday … 6 = Saturday */
export function weekday(date) {
  return new Date(`${date}T00:00:00Z`).getUTCDay();
}

export function isWeekend(date) {
  const day = weekday(date);
  return day === 0 || day === 6;
}

export function addDays(date, days) {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Every date from `from` to `to` inclusive. */
export function eachDate(from, to) {
  const dates = [];
  for (let d = from; d <= to; d = addDays(d, 1)) dates.push(d);
  return dates;
}

/** "09:15" → 555 (minutes after midnight) */
export function toMinutes(time) {
  const [h, m] = time.split(':').map(Number);
  return h * 60 + m;
}

export function overlaps(a, b) {
  return a.start < b.end && b.start < a.end;
}

/** Which semesters (e.g. ["S2"]) contain this date. */
export function semestersOn(catalog, date) {
  return Object.entries(catalog.settings.semesters)
    .filter(([, ranges]) => ranges.some((r) => date >= r.from && date <= r.to))
    .map(([key]) => key);
}

export function blackoutOn(catalog, date) {
  return catalog.settings.blackouts.find((b) => b.date === date) || null;
}

/** Start/end minutes of a slot. Unknown slots (e.g. removed from the catalog) count as all day. */
export function slotWindow(catalog, slotId) {
  const slot = catalog.index.slots[slotId];
  return slot
    ? { start: toMinutes(slot.start), end: toMinutes(slot.end) }
    : { start: 0, end: 24 * 60 };
}
