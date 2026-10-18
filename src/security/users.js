// Staff account management. These functions are ONLY called from the command line
// (`npm run users …`) — the website has no page that can create, recover or change accounts.

import { hashPassword, passwordProblem } from './passwords.js';
import { generateSecret, otpauthUri } from './totp.js';

export const ROLES = ['viewer', 'manager'];
export const ISSUER = 'BNTS Program Bookings';

function requireUser(store, email) {
  const user = store.getUserByEmail(email);
  if (!user) throw new Error(`No staff account for ${email}`);
  return user;
}

export async function createUser(store, { email, name = '', role = 'viewer', password }) {
  const cleanEmail = String(email || '').trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) throw new Error('Enter a valid email address');
  if (!ROLES.includes(role)) throw new Error(`Role must be ${ROLES.join(' or ')}`);
  if (store.getUserByEmail(cleanEmail)) throw new Error(`${cleanEmail} already has an account`);
  const problem = passwordProblem(password);
  if (problem) throw new Error(problem);
  const totpSecret = generateSecret();
  const user = store.insertUser({ email: cleanEmail, name, role, passwordHash: await hashPassword(password), totpSecret });
  store.audit('user.created', null, { email: cleanEmail, role }, 'command line');
  return { user, totpSecret, otpauth: otpauthUri({ issuer: ISSUER, account: cleanEmail, secret: totpSecret }) };
}

export async function resetPassword(store, email, password) {
  const user = requireUser(store, email);
  const problem = passwordProblem(password);
  if (problem) throw new Error(problem);
  store.updateUser(user.id, { password_hash: await hashPassword(password), failed_attempts: 0, locked_until: null });
  store.deleteSessionsForUser(user.id);
  store.audit('user.password_reset', null, { email: user.email }, 'command line');
}

/** New authenticator secret (e.g. lost phone). Logs the person out everywhere. */
export function resetTwoFactor(store, email) {
  const user = requireUser(store, email);
  const totpSecret = generateSecret();
  store.updateUser(user.id, { totp_secret: totpSecret, totp_last_counter: -1 });
  store.deleteSessionsForUser(user.id);
  store.audit('user.2fa_reset', null, { email: user.email }, 'command line');
  return { totpSecret, otpauth: otpauthUri({ issuer: ISSUER, account: user.email, secret: totpSecret }) };
}

export function setRole(store, email, role) {
  if (!ROLES.includes(role)) throw new Error(`Role must be ${ROLES.join(' or ')}`);
  const user = requireUser(store, email);
  store.updateUser(user.id, { role });
  store.audit('user.role_changed', null, { email: user.email, role }, 'command line');
}

export function setDisabled(store, email, disabled) {
  const user = requireUser(store, email);
  store.updateUser(user.id, { disabled: disabled ? 1 : 0 });
  if (disabled) store.deleteSessionsForUser(user.id);
  store.audit(disabled ? 'user.disabled' : 'user.enabled', null, { email: user.email }, 'command line');
}

export function unlockUser(store, email) {
  const user = requireUser(store, email);
  store.updateUser(user.id, { failed_attempts: 0, locked_until: null });
  store.audit('user.unlocked', null, { email: user.email }, 'command line');
}

export function removeUser(store, email) {
  const user = requireUser(store, email);
  store.deleteSessionsForUser(user.id);
  store.deleteUser(user.id);
  store.audit('user.removed', null, { email: user.email }, 'command line');
}

/** Logs out one person (email given) or everyone. Returns the number of sessions ended. */
export function logoutAll(store, email = null) {
  const count = email ? store.deleteSessionsForUser(requireUser(store, email).id) : store.deleteAllSessions();
  store.audit('sessions.revoked', null, { email: email || 'everyone', count }, 'command line');
  return count;
}
