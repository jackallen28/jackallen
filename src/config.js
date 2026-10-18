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
  if (!['none', 'email', 'graph', 'webhook'].includes(syncMode)) {
    throw new Error(`SYNC_MODE must be none, email, graph or webhook (got "${env.SYNC_MODE}")`);
  }

  const demoMode = bool(env.DEMO_MODE, true);
  // How staff get into /admin: accounts (individual logins + authenticator code), off (no admin
  // website at all — use the command line), or password (one shared password; demo mode only).
  const adminAccess = (env.ADMIN_ACCESS || 'accounts').toLowerCase();
  if (!['accounts', 'off', 'password'].includes(adminAccess)) {
    throw new Error(`ADMIN_ACCESS must be accounts, off or password (got "${env.ADMIN_ACCESS}")`);
  }
  if (adminAccess === 'password' && !demoMode) {
    throw new Error('ADMIN_ACCESS=password is only allowed with DEMO_MODE=true. Use ADMIN_ACCESS=accounts (see README → Security).');
  }

  return {
    port: Number(env.PORT || 3000),
    dataDir,
    timezone: env.TIMEZONE || 'Australia/Melbourne',
    adminAccess,
    // Optional: only these IPs / IPv4 ranges may reach /admin, e.g. "203.0.113.10, 10.0.0.0/8"
    adminAllowedIps: list(env.ADMIN_ALLOWED_IPS),
    adminPassword: env.ADMIN_PASSWORD || 'change-me', // only used when ADMIN_ACCESS=password
    // Used to sign the admin login cookie. Defaults to a value derived from the admin password,
    // so changing the password logs everyone out.
    sessionSecret: env.SESSION_SECRET || '',
    calendarFeedToken: env.CALENDAR_FEED_TOKEN || '',
    syncMode,
    demoMode,
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
    // Power Automate (or any automation tool) — see docs/POWER-AUTOMATE-SETUP.md
    webhook: {
      // SYNC_MODE=webhook: each booking/cancellation is POSTed here (the flow's "When an HTTP request is received" URL)
      url: env.POWER_AUTOMATE_WEBHOOK_URL || '',
      // Flows that report Microsoft Bookings appointments back to the site must send this secret
      inboundSecret: env.INBOUND_WEBHOOK_SECRET || '',
    },
  };
}

// Friendly warnings shown at startup for settings that are fine for a demo but not for real use.
export function configWarnings(config) {
  const warnings = [];
  if (config.adminAccess === 'password') {
    warnings.push('ADMIN_ACCESS=password (one shared password) is for demos only — use ADMIN_ACCESS=accounts for real use.');
  }
  if (!config.calendarFeedToken || config.calendarFeedToken.startsWith('change-me')) {
    warnings.push('CALENDAR_FEED_TOKEN is not set to a random value — Outlook calendar feeds are disabled until it is.');
  }
  return warnings;
}
