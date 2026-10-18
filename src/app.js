// Builds the Express app. Kept separate from server.js so tests can create an app
// without opening a network port.

import express from 'express';
import { apiRoutes } from './routes/api.js';

export function createApp(ctx) {
  const app = express();
  app.disable('x-powered-by');
  app.set('trust proxy', 1); // most hosts put the app behind one proxy (needed for secure cookies)

  app.use(express.json({ limit: '50kb' }));

  // Health check used by hosting platforms (Render, Azure, Docker) to see the app is alive.
  app.get('/healthz', (req, res) => {
    res.json({ ok: true });
  });

  app.use('/api', apiRoutes(ctx));

  // Unknown API paths → JSON 404 (pages get the normal 404).
  app.use('/api', (req, res) => res.status(404).json({ error: 'Not found' }));

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
