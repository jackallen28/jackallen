// Tiny persistence layer: one JSON file per session, one JSONL append log for
// leads. Deliberately dependency-free so the service runs anywhere a Node
// container runs. Swap the four exported functions for Postgres when volume
// justifies it (see README -> "When to move off the file store").
import fs from 'node:fs/promises';
import fsSync from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { config } from './config.js';

let dataDir = config.storage.dataDir;
let sessionsDir = path.join(dataDir, 'sessions');
let leadsFile = path.join(dataDir, 'leads.jsonl');

export const paths = { get dataDir() { return dataDir; } };

const cache = new Map(); // id -> session (write-through, keeps hot sessions fast)

export async function initStore() {
  try {
    await fs.mkdir(sessionsDir, { recursive: true });
    await fs.mkdir(path.join(dataDir, 'files'), { recursive: true });
    await fs.access(dataDir, fsSync.constants.W_OK);
  } catch (err) {
    // A mounted disk owned by root is the usual cause. Keep running on
    // temporary storage rather than refusing to boot, but be loud about it:
    // anything written here disappears on the next restart.
    const fallback = path.join(os.tmpdir(), 'cad-quote-bot-data');
    console.error(`[store] ${dataDir} is not writable (${err.code || err.message}). Falling back to ${fallback} — DATA WILL NOT SURVIVE A RESTART.`);
    dataDir = fallback;
    sessionsDir = path.join(dataDir, 'sessions');
    leadsFile = path.join(dataDir, 'leads.jsonl');
    await fs.mkdir(sessionsDir, { recursive: true });
    await fs.mkdir(path.join(dataDir, 'files'), { recursive: true });
  }
}

export function newId(prefix) {
  return `${prefix}_${crypto.randomBytes(12).toString('hex')}`;
}

export async function createSession(meta = {}) {
  const now = Date.now();
  const session = {
    id: newId('s'),
    createdAt: now,
    updatedAt: now,
    state: 'brief',
    brief: '',
    product: '',
    questions: [],
    answers: {},
    qIndex: 0,
    spec: null,
    generations: 0,
    job: null,
    lead: null,
    messages: [],
    meta,
  };
  await saveSession(session);
  return session;
}

export async function getSession(id) {
  if (!/^s_[a-f0-9]{24}$/.test(String(id || ''))) return null;
  if (cache.has(id)) return cache.get(id);
  try {
    const raw = await fs.readFile(path.join(sessionsDir, `${id}.json`), 'utf8');
    const session = JSON.parse(raw);
    cache.set(id, session);
    return session;
  } catch {
    return null;
  }
}

export async function saveSession(session) {
  session.updatedAt = Date.now();
  cache.set(session.id, session);
  const file = path.join(sessionsDir, `${session.id}.json`);
  const tmp = `${file}.${process.pid}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(session, null, 2));
  await fs.rename(tmp, file);
  return session;
}

export async function appendLead(lead) {
  await fs.appendFile(leadsFile, `${JSON.stringify(lead)}\n`);
}

async function readLeads() {
  try {
    return (await fs.readFile(leadsFile, 'utf8'))
      .split('\n').filter(Boolean)
      .map((line) => { try { return JSON.parse(line); } catch { return null; } })
      .filter(Boolean);
  } catch {
    return [];
  }
}

export async function getLead(id) {
  if (!/^q_[a-f0-9]{24}$/.test(String(id || ''))) return null;
  const leads = await readLeads();
  return leads.find((l) => l.id === id) || null;
}

/** Newest first, for the /requests list. */
export async function listLeads(limit = 100) {
  return (await readLeads()).reverse().slice(0, limit);
}

// Housekeeping: drop sessions (and their generated files) past the TTL.
export async function pruneSessions() {
  const cutoff = Date.now() - config.limits.sessionTtlMs;
  let removed = 0;
  let names = [];
  try {
    names = await fs.readdir(sessionsDir);
  } catch {
    return 0;
  }
  for (const name of names) {
    if (!name.endsWith('.json')) continue;
    const file = path.join(sessionsDir, name);
    try {
      const stat = await fs.stat(file);
      if (stat.mtimeMs < cutoff) {
        await fs.rm(file, { force: true });
        cache.delete(name.replace(/\.json$/, ''));
        removed += 1;
      }
    } catch { /* raced with another prune — fine */ }
  }
  return removed;
}
