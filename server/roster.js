/**
 * The class login list.
 *
 * A login is four letters then four digits (WXYZ1234). The teacher uploads a CSV
 * pairing each login with a student number and hands the logins out beforehand,
 * so the room can be identified for the report without anyone typing a name into
 * the activity.
 */

export const LOGIN_PATTERN = /^[A-Z]{4}[0-9]{4}$/;

/** Upper-case and strip the separators people add when reading a code aloud. */
export function normaliseLogin(value) {
  return String(value ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '');
}

export function isValidLogin(value) {
  return LOGIN_PATTERN.test(normaliseLogin(value));
}

/** One CSV line into cells, honouring quotes and escaped quotes. */
function splitCsvLine(line) {
  const cells = [];
  let cell = '';
  let quoted = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (quoted) {
      if (char === '"') {
        if (line[i + 1] === '"') {
          cell += '"';
          i++;
        } else {
          quoted = false;
        }
      } else {
        cell += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ',' || char === ';' || char === '\t') {
      cells.push(cell.trim());
      cell = '';
    } else {
      cell += char;
    }
  }
  cells.push(cell.trim());
  return cells;
}

/**
 * Parse an uploaded roster.
 *
 * Deliberately forgiving about shape: the login is whichever cell in a row looks
 * like a login, so `login,student` and `student,login` both work, with or without
 * a header row. A teacher fighting column order before a lesson is a bad outcome.
 *
 * @returns {{entries: Array<{login: string, student: string}>, errors: string[], duplicates: string[]}}
 */
export function parseRoster(text) {
  const entries = [];
  const errors = [];
  const duplicates = [];
  const seen = new Set();

  const lines = String(text ?? '')
    .replace(/^﻿/, '')
    .split(/\r?\n/);

  let firstRow = true;
  for (const [index, raw] of lines.entries()) {
    const line = raw.trim();
    if (!line) continue;

    const cells = splitCsvLine(line);
    const loginCell = cells.find((cell) => isValidLogin(cell));
    const wasFirst = firstRow;
    firstRow = false;

    if (!loginCell) {
      // Only the first row may be a header. Any later row without a login is a
      // real problem — usually a typo — and silently dropping it would leave a
      // student unable to log in with no clue why.
      const isHeader = wasFirst && /login|code|student|id|number|name/i.test(line);
      if (!isHeader) errors.push(`Line ${index + 1}: no valid login — "${line.slice(0, 40)}"`);
      continue;
    }

    const login = normaliseLogin(loginCell);
    if (seen.has(login)) {
      duplicates.push(login);
      continue;
    }
    seen.add(login);

    const student = cells.find((cell) => cell && normaliseLogin(cell) !== login) || login;
    entries.push({ login, student: student.slice(0, 40) });
  }

  return { entries, errors, duplicates };
}
