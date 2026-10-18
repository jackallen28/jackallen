// Timezone helpers (local school time ⇄ UTC) using only the built-in Intl API.

/** Today's date "YYYY-MM-DD" in the given timezone. */
export function todayIn(timezone, now = new Date()) {
  return localParts(now, timezone).date;
}

/** Splits a JS Date into local { date: "YYYY-MM-DD", time: "HH:MM" } for a timezone. */
export function localParts(instant, timezone) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(instant)
      .map((p) => [p.type, p.value]),
  );
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
}

/** Local date + time in `timezone` → the matching JS Date (an exact instant). */
export function zonedToUtc(date, time, timezone) {
  const [y, mo, d] = date.split('-').map(Number);
  const [h, mi] = time.split(':').map(Number);
  const wanted = Date.UTC(y, mo - 1, d, h, mi);
  // Guess, see what local time that guess shows, and correct by the difference.
  // Two rounds handle daylight-saving changes.
  let guess = wanted;
  for (let i = 0; i < 2; i++) {
    const shown = localParts(new Date(guess), timezone);
    const [sy, smo, sd] = shown.date.split('-').map(Number);
    const [sh, smi] = shown.time.split(':').map(Number);
    guess += wanted - Date.UTC(sy, smo - 1, sd, sh, smi);
  }
  return new Date(guess);
}

// Microsoft Graph wants Windows timezone names. These cover Australia; anything else is
// sent to Graph in UTC instead.
const WINDOWS_ZONES = {
  'Australia/Melbourne': 'AUS Eastern Standard Time',
  'Australia/Sydney': 'AUS Eastern Standard Time',
  'Australia/Canberra': 'AUS Eastern Standard Time',
  'Australia/Hobart': 'Tasmania Standard Time',
  'Australia/Brisbane': 'E. Australia Standard Time',
  'Australia/Adelaide': 'Cen. Australia Standard Time',
  'Australia/Darwin': 'AUS Central Standard Time',
  'Australia/Perth': 'W. Australia Standard Time',
  UTC: 'UTC',
};

export function windowsZone(timezone) {
  return WINDOWS_ZONES[timezone] || null;
}
