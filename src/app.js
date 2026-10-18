// Builds the Express app. Kept separate from server.js so tests can create an app
// without opening a network port.

import express from 'express';

export function createApp() {
  const app = express();
  app.disable('x-powered-by');

  // Health check used by hosting platforms (Render, Azure, Docker) to see the app is alive.
  app.get('/healthz', (req, res) => {
    res.json({ ok: true });
  });

  return app;
}
