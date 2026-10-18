// `npm run catalog:check` — validates config/catalog.yaml and prints every program with its
// requirements and rules, so the owner can check them against the rules document.

import { loadConfig } from '../src/config.js';
import { loadCatalog } from '../src/catalog/load.js';
import {
  describeRequirement,
  describeCombinationRules,
  semesterLabel,
} from '../src/catalog/describe.js';

const config = loadConfig();

let catalog;
try {
  catalog = loadCatalog(config.catalogPath);
} catch (err) {
  console.error(`\n✖ ${err.message}\n`);
  process.exit(1);
}

// --- tiny table printer with word-wrapping ----------------------------------------
function wrap(text, width) {
  const lines = [];
  for (const paragraph of String(text).split('\n')) {
    let line = '';
    for (const word of paragraph.split(' ')) {
      if (line && (line + ' ' + word).length > width) {
        lines.push(line);
        line = word;
      } else {
        line = line ? `${line} ${word}` : word;
      }
    }
    lines.push(line);
  }
  return lines;
}

function printTable(columns, rows) {
  const border = '+' + columns.map((c) => '-'.repeat(c.width + 2)).join('+') + '+';
  const printRow = (cells) => {
    const wrapped = cells.map((cell, i) => wrap(cell, columns[i].width));
    const height = Math.max(...wrapped.map((w) => w.length));
    for (let line = 0; line < height; line++) {
      console.log(
        '| ' + wrapped.map((w, i) => (w[line] || '').padEnd(columns[i].width)).join(' | ') + ' |',
      );
    }
  };
  console.log(border);
  printRow(columns.map((c) => c.title));
  console.log(border.replace(/-/g, '='));
  for (const row of rows) {
    printRow(row);
    console.log(border);
  }
}

const { settings } = catalog;
console.log(`\n✔ ${catalog.file} is valid.\n`);
console.log(`Class size: ${settings.class_size} students`);
console.log(`Staff pool: ${settings.staff_pool.size} ${settings.staff_pool.name}`);
console.log(`Slots: ${settings.slots.map((s) => `${s.label} ${s.start}–${s.end}`).join(', ')}`);
for (const [key, ranges] of Object.entries(settings.semesters)) {
  console.log(`Semester ${key}: ${ranges.map((r) => `${r.from} → ${r.to}`).join(', ')}`);
}
console.log(
  `Blackouts: ${settings.blackouts.length ? settings.blackouts.map((b) => `${b.date} (${b.reason})`).join(', ') : 'none'}`,
);
console.log(`Allowed pairs share rooms: ${settings.allowed_pairs_share_rooms ? 'yes' : 'no'}`);
console.log(
  `Rooms: ${catalog.resources.filter((r) => r.type === 'room').map((r) => r.name).join(', ')}`,
);
console.log(
  `Tracked equipment: ${catalog.resources.filter((r) => r.type === 'equipment').map((r) => r.name).join(', ')}\n`,
);

for (const category of catalog.categories) {
  const programs = catalog.programs.filter((p) => p.category === category.id);
  if (!programs.length) continue;
  console.log(`\n${category.name.toUpperCase()} (${programs.length} programs)`);
  printTable(
    [
      { title: 'Program', width: 26 },
      { title: 'When', width: 10 },
      { title: 'Max', width: 13 },
      { title: 'Staff', width: 5 },
      { title: 'Needs (all of these)', width: 30 },
      { title: 'Combination rules', width: 28 },
    ],
    programs.map((p) => [
      `${p.name}\n(${p.id})${p.active ? '' : '\nINACTIVE'}`,
      semesterLabel(p.semesters),
      `${p.max_classes} class${p.max_classes > 1 ? 'es' : ''}\n(${p.max_classes * settings.class_size} students)`,
      String(p.staff_required),
      p.requires.length ? p.requires.map((alts) => `• ${describeRequirement(catalog, alts)}`).join('\n') : '(nothing)',
      describeCombinationRules(catalog, p).join('\n') || '—',
    ]),
  );
}

const unmapped = catalog.programs.filter((p) => !p.bookings_service_id).length;
console.log(
  `\n${catalog.programs.length} programs in total. ${unmapped} without a Microsoft Bookings service id` +
    ` (only needed for SYNC_MODE=graph — see \`npm run graph:check\`).\n`,
);
