// Entry point: `npm start` runs this file.

import { loadConfig, configWarnings } from './config.js';
import { createApp } from './app.js';

const config = loadConfig();
for (const warning of configWarnings(config)) console.warn(`⚠  ${warning}`);

const app = createApp();
app.listen(config.port, () => {
  console.log(`Program booking system running at http://localhost:${config.port}`);
});
