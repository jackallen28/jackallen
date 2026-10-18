// Staff login for /admin.
//
// ADMIN_ACCESS=accounts (default): each staff member has their own account (email + password +
//   6-digit authenticator code). Accounts are created only on the server with `npm run users`;
//   there is no sign-up, password-reset or "master" password on the website.
// ADMIN_ACCESS=off:      the admin website doesn't exist (every /admin URL is a 404).
// ADMIN_ACCESS=password: one shared password — allowed in demo mode only.
//
// Sessions are stored in the database (only a hash of the cookie), expire after 60 minutes of
// inactivity or 10 hours in total, and can be ended from the command line (`npm run users logout`).

import crypto from 'node:crypto';
import { verifyPassword, dummyVerify } from './security/passwords.js';
import { verifyCode } from './security/totp.js';
import { createLimiter } from './security/rate-limit.js';
import { ipMatcher } from './security/headers.js';

const COOKIE = 'admin_session';
const IDLE_MS = 60 * 60 * 1000; // 60 minutes
const ABSOLUTE_MS = 10 * 60 * 60 * 1000; // 10 hours
const MAX_FAILURES = 5; // then the account is locked…
const LOCK_MS = 15 * 60 * 1000; // …for 15 minutes
const GENERIC_ERROR = 'That email, password or code is not right.';

const sha256 = (value) => crypto.createHash('sha256').update(String(value)).digest('hex');

function safeEqual(a, b) {
  return crypto.timingSafeEqual(Buffer.from(sha256(a)), Buffer.from(sha256(b)));
}

function readCookie(req, name) {
  for (const part of (req.headers.cookie || '').split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return decodeURIComponent(v.join('='));
  }
  return null;
}

export function createAuth({ config, store }) {
  // At most 10 login attempts per IP address per 15 minutes (on top of per-account lockout).
  const loginLimiter = createLimiter({ windowMs: 15 * 60 * 1000, max: 10 });
  const ipAllowedByList = config.adminAllowedIps.length ? ipMatcher(config.adminAllowedIps) : () => true;
  const sharedPasswordUser = { id: null, email: 'shared password', name: 'Demo admin', role: 'manager' };

  function startSession(req, res, user) {
    const token = crypto.randomBytes(32).toString('base64url');
    store.insertSession({
      tokenHash: sha256(token),
      userId: user.id,
      expiresAt: new Date(Date.now() + ABSOLUTE_MS).toISOString(),
      ip: req.ip || null,
      userAgent: String(req.get('user-agent') || '').slice(0, 200),
    });
    res.cookie(COOKIE, token, {
      httpOnly: true,
      sameSite: 'strict',
      secure: req.secure,
      maxAge: ABSOLUTE_MS,
      path: '/',
    });
  }

  /** The logged-in staff member for this request, or null. */
  function currentUser(req) {
    const token = readCookie(req, COOKIE);
    if (!token) return null;
    const hash = sha256(token);
    const session = store.getSession(hash);
    if (!session) return null;
    const now = Date.now();
    if (Date.parse(session.expires_at) < now || Date.parse(session.last_seen_at) + IDLE_MS < now) {
      store.deleteSession(hash);
      return null;
    }
    let user;
    if (session.user_id == null) {
      user = config.adminAccess === 'password' ? sharedPasswordUser : null;
    } else {
      const row = store.getUserById(session.user_id);
      user = row && !row.disabled && config.adminAccess === 'accounts' ? row : null;
    }
    if (!user) {
      store.deleteSession(hash);
      return null;
    }
    if (now - Date.parse(session.last_seen_at) > 60 * 1000) store.touchSession(hash);
    return { id: user.id, email: user.email, name: user.name, role: user.role };
  }

  /**
   * Checks a login attempt and starts a session.
   * @returns {Promise<{ ok: boolean, status?: number, error?: string }>}
   */
  async function login(req, res) {
    const { email, password, code } = req.body || {};
    const ip = req.ip || 'unknown';
    const attempt = loginLimiter.hit(ip);
    if (!attempt.allowed) {
      return { ok: false, status: 429, error: `Too many login attempts. Try again in ${Math.ceil(attempt.retryAfterSeconds / 60)} minutes.` };
    }

    if (config.adminAccess === 'password') {
      if (!safeEqual(password ?? '', config.adminPassword)) {
        store.audit('admin.login_failed', null, { ip }, 'shared password');
        return { ok: false, status: 401, error: 'Wrong password' };
      }
      startSession(req, res, sharedPasswordUser);
      store.audit('admin.login', null, { ip }, 'shared password');
      return { ok: true };
    }

    const user = store.getUserByEmail(email);
    if (!user) {
      await dummyVerify(password); // same timing as a real account
      store.audit('admin.login_failed', null, { ip, reason: 'unknown email' }, String(email || '').slice(0, 100));
      return { ok: false, status: 401, error: GENERIC_ERROR };
    }
    if (user.locked_until && Date.parse(user.locked_until) > Date.now()) {
      await dummyVerify(password);
      return { ok: false, status: 401, error: 'Too many wrong attempts — this account is locked for 15 minutes.' };
    }
    const passwordOk = await verifyPassword(password, user.password_hash);
    const counter = passwordOk ? verifyCode(user.totp_secret, code, { lastCounter: user.totp_last_counter }) : null;
    if (!passwordOk || counter === null || user.disabled) {
      const failures = user.failed_attempts + 1;
      const lock = failures >= MAX_FAILURES;
      store.updateUser(user.id, {
        failed_attempts: lock ? 0 : failures,
        locked_until: lock ? new Date(Date.now() + LOCK_MS).toISOString() : user.locked_until,
      });
      store.audit(lock ? 'admin.account_locked' : 'admin.login_failed', null, { ip }, user.email);
      return { ok: false, status: 401, error: lock ? 'Too many wrong attempts — this account is locked for 15 minutes.' : GENERIC_ERROR };
    }

    store.updateUser(user.id, {
      failed_attempts: 0,
      locked_until: null,
      totp_last_counter: counter,
      last_login_at: new Date().toISOString(),
    });
    store.deleteExpiredSessions();
    startSession(req, res, user);
    store.audit('admin.login', null, { ip }, user.email);
    return { ok: true };
  }

  function logout(req, res) {
    const token = readCookie(req, COOKIE);
    if (token) store.deleteSession(sha256(token));
    res.clearCookie(COOKIE, { path: '/' });
  }

  /** IP allow-list check (ADMIN_ALLOWED_IPS). */
  function ipAllowed(req) {
    return ipAllowedByList(req.ip);
  }

  /** Middleware for admin API routes: allowed IP, valid session, JSON for changes. */
  function requireAdmin(req, res, next) {
    if (!ipAllowed(req)) return res.status(404).json({ error: 'Not found' });
    const user = currentUser(req);
    if (!user) return res.status(401).json({ error: 'Please log in' });
    // Changes must be sent as JSON; with the SameSite=Strict cookie this blocks cross-site form posts.
    if (req.method !== 'GET' && req.method !== 'HEAD' && !req.is('application/json')) {
      return res.status(415).json({ error: 'Send requests as JSON' });
    }
    req.admin = user;
    next();
  }

  /** Middleware: only managers may change things (viewers can look, and use the rule tester). */
  function requireManager(req, res, next) {
    if (req.admin?.role !== 'manager') return res.status(403).json({ error: 'Your account can view but not change bookings' });
    next();
  }

  return { login, logout, currentUser, ipAllowed, requireAdmin, requireManager };
}
