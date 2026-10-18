// `npm run graph:mock` — runs a pretend Microsoft Bookings (Graph API) on http://localhost:4010,
// so you can try SYNC_MODE=graph before IT has set anything up. In another terminal start the
// app with:
//
//   SYNC_MODE=graph BOOKINGS_BUSINESS_ID=bnts@example.onmicrosoft.com \
//   GRAPH_BASE_URL=http://localhost:4010/v1.0 npm start
//
// The mock has one service per program (same names, so they link automatically).
// Data is kept in memory only — restarting the mock clears it.

import { loadConfig } from '../src/config.js';
import { loadCatalog } from '../src/catalog/load.js';
import { createMockGraph, servicesFromCatalog } from '../src/sync/graph-mock.js';

const port = Number(process.env.MOCK_PORT || 4010);
const catalog = loadCatalog(loadConfig().catalogPath);
const mock = createMockGraph({ services: servicesFromCatalog(catalog) });

// Extra endpoints for playing with the mock (not part of the real Graph API):
//   GET  /mock/appointments                  see everything the app has sent
//   POST /mock/direct  { programId, date, start, end, customerName }
//        pretend someone booked straight into Microsoft Bookings
mock.app.get('/mock/appointments', (req, res) => res.json([...mock.state.appointments.values()]));
mock.app.post('/mock/direct', (req, res) => {
  const { programId, date, start = '09:15', end = '14:45', customerName } = req.body || {};
  const id = mock.addDirectAppointment({ serviceId: `mock-service-${programId}`, date, start, end, customerName });
  res.status(201).json({ id });
});

mock.app.listen(port, () => {
  console.log(`Mock Microsoft Bookings (Graph API) running at http://localhost:${port}/v1.0`);
  console.log(`  BOOKINGS_BUSINESS_ID=${mock.businessId}`);
  console.log(`  GRAPH_BASE_URL=http://localhost:${port}/v1.0`);
  console.log('  (requests need any "Authorization: Bearer …" header, e.g. -H "Authorization: Bearer x")');
});
