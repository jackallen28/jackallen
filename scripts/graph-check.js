// `npm run graph:check` — checks the Microsoft Graph credentials and lists your Microsoft
// Bookings businesses and services, so you can fill in BOOKINGS_BUSINESS_ID and each
// program's bookings_service_id in config/catalog.yaml.

import { loadConfig } from '../src/config.js';
import { loadCatalog } from '../src/catalog/load.js';
import { createGraphAdapter } from '../src/sync/graph.js';

const config = loadConfig();
const catalog = loadCatalog(config.catalogPath);
const graph = createGraphAdapter({ config, catalog });

function fail(message) {
  console.error(`\n✖ ${message}\n`);
  process.exit(1);
}

console.log(`\nMicrosoft Graph: ${config.graph.baseUrl}`);

try {
  await graph.getToken();
  console.log('✔ Signed in to Microsoft Entra ID with the app registration');
} catch (err) {
  fail(`Could not sign in: ${err.message}\n  Check GRAPH_TENANT_ID, GRAPH_CLIENT_ID and GRAPH_CLIENT_SECRET (see docs/M365-BOOKINGS-SETUP.md).`);
}

let businesses;
try {
  businesses = await graph.listBusinesses();
} catch (err) {
  fail(`Signed in, but could not list Bookings businesses: ${err.message}\n  Has an admin granted consent for the Bookings API permissions?`);
}
console.log(`\nBookings businesses this app can see (${businesses.length}):`);
for (const b of businesses) console.log(`  • ${b.displayName}\n      BOOKINGS_BUSINESS_ID=${b.id}`);

if (!config.graph.businessId) {
  fail('BOOKINGS_BUSINESS_ID is not set. Copy one of the ids above into your .env and run this again.');
}

let services;
try {
  services = await graph.listServices();
} catch (err) {
  fail(`Could not list services for ${config.graph.businessId}: ${err.message}`);
}

console.log(`\nServices in ${config.graph.businessId} (${services.length}):`);
for (const s of services) console.log(`  • ${s.displayName}\n      id: ${s.id}`);

console.log('\nHow each program is linked:');
const byName = new Map(services.map((s) => [(s.displayName || '').trim().toLowerCase(), s]));
const byId = new Map(services.map((s) => [s.id, s]));
let unlinked = 0;
for (const p of catalog.programs) {
  if (p.bookings_service_id) {
    const s = byId.get(p.bookings_service_id);
    console.log(`  ${s ? '✔' : '✖'} ${p.name} → ${s ? s.displayName : `service id ${p.bookings_service_id} NOT FOUND`} (by id)`);
    if (!s) unlinked++;
  } else if (byName.has(p.name.trim().toLowerCase())) {
    console.log(`  ✔ ${p.name} → matched a service with the same name`);
  } else {
    console.log(`  – ${p.name} → not linked (bookings for it can't be sent to Bookings)`);
    unlinked++;
  }
}

console.log(
  unlinked
    ? `\n${unlinked} program(s) not linked. Either create a Bookings service with exactly the program's name,\n` +
        'or add the service id to the program in config/catalog.yaml, e.g.\n\n    bookings_service_id: "<id from the list above>"\n'
    : '\n✔ Every program is linked to a Bookings service.\n',
);
