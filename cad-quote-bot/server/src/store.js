// Tiny persistence layer: one JSON file per session, one JSONL append log for
// leads. Deliberately dependency-free so the service runs anywhere a Node
// container runs. Swap the four exported functions for Postgres when volume
// justifies it (see README -> "When to move off the file store").
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { config } from './config.js';

const sessionsDir = path.join(config.storage.dataDir, 'sessions');
const leadsFile = path.join(config.storage.dataDir, 'leads.jsonl');

const cache = new Map(); // id -> session (write-through, keeps hot sessions fast)

export async function initStore() {
  await fs.mkdir(sessionsDir, { recursive: true });
  await fs.mkdir(path.join(config.storage.dataDir, 'files'), { recursive: true });
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
