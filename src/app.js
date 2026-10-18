// Builds the Express app. Kept separate from server.js so tests can create an app
// without opening a network port.

import path from 'node:path';
import express from 'express';
import { ROOT_DIR } from './config.js';
import { apiRoutes } from './routes/api.js';
import { adminRoutes } from './routes/admin.js';
import { calendarRoutes } from './routes/calendar.js';
import { integrationRoutes } from './routes/integrations.js';

const PUBLIC_DIR = path.join(ROOT_DIR, 'public');

export function createApp(ctx) {
  const app = express();
  app.disable('x-powered-by');
  app.set('trust proxy', 1); // most hosts put the app behind one proxy (needed for secure cookies)

  app.use(express.json({ limit: '50kb' }));

  // Health check used by hosting platforms (Render, Azure, Docker) to see the app is alive.
  app.get('/healthz', (req, res) => {
    res.json({ ok: true });
  });

  app.use(integrationRoutes(ctx));
  app.use('/api', apiRoutes(ctx));
  app.use(adminRoutes(ctx));
  app.use(calendarRoutes(ctx));

  // Unknown API paths → JSON 404 (pages get the normal 404).
  app.use('/api', (req, res) => res.status(404).json({ error: 'Not found' }));

  // ---- public pages ----------------------------------------------------------------
  const page = (file) => (req, res) => res.sendFile(path.join(PUBLIC_DIR, file));
  app.get('/program/:id', page('program.html'));
  app.get('/manage/:token', (req, res) => {
    res.set('Referrer-Policy', 'no-referrer'); // don't leak the private link to other sites
    page('manage.html')(req, res);
  });

  // FullCalendar is served from node_modules, so the site works offline at demos (no CDN).
  app.use('/vendor/fullcalendar', express.static(path.join(ROOT_DIR, 'node_modules/fullcalendar')));
  app.use(express.static(PUBLIC_DIR, { index: 'index.html' }));

  // Last-resort error handler: log it, show a friendly message.
  app.use((err, req, res, next) => {
    if (err.type === 'entity.parse.failed') return res.status(400).json({ error: 'Invalid JSON' });
    if (err.type === 'entity.too.large') return res.status(413).json({ error: 'Request too large' });
    console.error(err);
    if (res.headersSent) return next(err);
    res.status(500).json({ error: 'Something went wrong. Please try again.' });
  });

  return app;
}
