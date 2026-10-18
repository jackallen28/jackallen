// Reads all settings from environment variables (and from a .env file if one exists).
// Every other module receives the resulting `config` object instead of reading process.env itself,
// which keeps tests simple: they just pass in their own config.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// Load .env from the project folder (Node 22 has this built in, so no extra package is needed).
const envFile = path.join(ROOT_DIR, '.env');
if (fs.existsSync(envFile) && typeof process.loadEnvFile === 'function') {
  process.loadEnvFile(envFile);
}

function bool(value, fallback) {
  if (value === undefined || value === '') return fallback;
  return ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase());
}

function list(value) {
  return String(value || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

export function loadConfig(env = process.env) {
  const dataDir = path.resolve(ROOT_DIR, env.DATA_DIR || './data');
  const syncMode = (env.SYNC_MODE || 'none').toLowerCase();
  if (!['none', 'email', 'graph'].includes(syncMode)) {
    throw new Error(`SYNC_MODE must be none, email or graph (got "${env.SYNC_MODE}")`);
  }

  return {
    port: Number(env.PORT || 3000),
    dataDir,
    timezone: env.TIMEZONE || 'Australia/Melbourne',
    adminPassword: env.ADMIN_PASSWORD || 'change-me',
    // Used to sign the admin login cookie. Defaults to a value derived from the admin password,
    // so changing the password logs everyone out.
    sessionSecret: env.SESSION_SECRET || '',
    calendarFeedToken: env.CALENDAR_FEED_TOKEN || '',
    syncMode,
    demoMode: bool(env.DEMO_MODE, true),
    publicUrl: (env.PUBLIC_URL || '').replace(/\/$/, ''),
    catalogPath: path.resolve(ROOT_DIR, env.CATALOG_PATH || 'config/catalog.yaml'),
    email: {
      host: env.SMTP_HOST || '',
      port: Number(env.SMTP_PORT || 587),
      user: env.SMTP_USER || '',
      pass: env.SMTP_PASS || '',
      from: env.SMTP_FROM || env.SMTP_USER || 'bookings@localhost',
      inviteAddresses: list(env.INVITE_ADDRESSES),
    },
    graph: {
      tenantId: env.GRAPH_TENANT_ID || '',
      clientId: env.GRAPH_CLIENT_ID || '',
      clientSecret: env.GRAPH_CLIENT_SECRET || '',
      businessId: env.BOOKINGS_BUSINESS_ID || '',
      baseUrl: (env.GRAPH_BASE_URL || 'https://graph.microsoft.com/v1.0').replace(/\/$/, ''),
    },
  };
}

// Friendly warnings shown at startup for settings that are fine for a demo but not for real use.
export function configWarnings(config) {
  const warnings = [];
  if (config.adminPassword === 'change-me') {
    warnings.push('ADMIN_PASSWORD is still "change-me" — set a real password before going online.');
  }
  if (!config.calendarFeedToken || config.calendarFeedToken.startsWith('change-me')) {
    warnings.push('CALENDAR_FEED_TOKEN is not set to a random value — Outlook calendar feeds are disabled until it is.');
  }
  return warnings;
}
