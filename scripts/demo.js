// `npm run demo` — deletes ALL bookings and loads the example bookings for the next four weeks.

import { loadConfig } from '../src/config.js';
import { createContext } from '../src/context.js';
import { seedDemo } from '../src/seed.js';

const ctx = createContext(loadConfig());
const { created, skipped } = seedDemo(ctx);
console.log(`Demo data loaded: ${created.length} bookings.`);
for (const b of created) {
  console.log(`  ${b.date}  ${ctx.catalog.index.programs[b.programId].name} — ${b.school}`);
}
if (skipped.length) console.log(`Skipped:\n  ${skipped.join('\n  ')}`);
ctx.close();
