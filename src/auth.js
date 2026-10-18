// Admin login: one shared password (ADMIN_PASSWORD) and a signed cookie.
// The cookie holds an expiry time plus an HMAC signature, so it can't be forged or extended.

import crypto from 'node:crypto';

const COOKIE = 'admin_session';
const LIFETIME_MS = 12 * 60 * 60 * 1000; // 12 hours

function secretFor(config) {
  return config.sessionSecret || crypto.createHash('sha256').update(`session:${config.adminPassword}`).digest('hex');
}

function sign(config, value) {
  return crypto.createHmac('sha256', secretFor(config)).update(value).digest('base64url');
}

function safeEqual(a, b) {
  const ha = crypto.createHash('sha256').update(String(a)).digest();
  const hb = crypto.createHash('sha256').update(String(b)).digest();
  return crypto.timingSafeEqual(ha, hb);
}

export function checkPassword(config, password) {
  return safeEqual(password ?? '', config.adminPassword);
}

function readCookie(req, name) {
  const header = req.headers.cookie || '';
  for (const part of header.split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return decodeURIComponent(v.join('='));
  }
  return null;
}

export function isLoggedIn(config, req) {
  const value = readCookie(req, COOKIE);
  if (!value) return false;
  const [expires, signature] = value.split('.');
  if (!expires || !signature || !safeEqual(signature, sign(config, expires))) return false;
  return Number(expires) > Date.now();
}

export function setLoginCookie(config, req, res) {
  const expires = String(Date.now() + LIFETIME_MS);
  res.cookie(COOKIE, `${expires}.${sign(config, expires)}`, {
    httpOnly: true,
    sameSite: 'lax',
    secure: req.secure,
    maxAge: LIFETIME_MS,
    path: '/',
  });
}

export function clearLoginCookie(res) {
  res.clearCookie(COOKIE, { path: '/' });
}

/** Express middleware for admin API routes. */
export function requireAdmin(config) {
  return (req, res, next) => {
    if (!isLoggedIn(config, req)) return res.status(401).json({ error: 'Please log in' });
    // Changes must be sent as JSON; together with the SameSite cookie this blocks cross-site form posts.
    if (req.method !== 'GET' && req.method !== 'HEAD' && !req.is('application/json')) {
      return res.status(415).json({ error: 'Send requests as JSON' });
    }
    next();
  };
}
