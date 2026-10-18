// `npm run users -- <command>` — manage staff accounts for /admin. This is the ONLY way to create,
// change or recover an account: the website has no sign-up or password-reset page.
//
//   npm run users -- add <email> [--name "Full Name"] [--role viewer|manager]
//   npm run users -- list
//   npm run users -- role <email> viewer|manager
//   npm run users -- reset-password <email>
//   npm run users -- reset-2fa <email>          (lost phone / new authenticator app)
//   npm run users -- unlock <email>             (after too many wrong attempts)
//   npm run users -- disable <email>  |  enable <email>
//   npm run users -- logout [<email>]           (end sessions for one person, or everyone)
//   npm run users -- remove <email>
//
// In Docker:  docker compose exec app npm run users -- add you@school.vic.edu.au --role manager

import readline from 'node:readline';
import { loadConfig } from '../src/config.js';
import { openDatabase, databaseFile } from '../src/db/index.js';
import { createStore } from '../src/db/store.js';
import { verifyCode } from '../src/security/totp.js';
import { MIN_PASSWORD_LENGTH } from '../src/security/passwords.js';
import * as users from '../src/security/users.js';

const config = loadConfig();
const store = createStore(openDatabase(databaseFile(config.dataDir)));
const [command, email, ...rest] = process.argv.slice(2);

function option(name) {
  const i = rest.indexOf(`--${name}`);
  return i >= 0 ? rest[i + 1] : undefined;
}

// One shared reader for all questions. Lines are queued, so typed-ahead or piped answers aren't lost.
let rl;
let muted = false;
const queued = [];
const waiting = [];
function ask(question, { hidden = false } = {}) {
  if (!rl) {
    rl = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: Boolean(process.stdin.isTTY) });
    const write = rl._writeToOutput.bind(rl);
    rl._writeToOutput = (text) => {
      if (!muted) write(text); // hide password typing
    };
    rl.setPrompt('');
    rl.on('line', (line) => (waiting.length ? waiting.shift()(line) : queued.push(line)));
    rl.on('close', () => waiting.splice(0).forEach((resolve) => resolve('')));
  }
  process.stdout.write(question);
  muted = hidden;
  return new Promise((resolve) => {
    const done = (line) => {
      muted = false;
      if (hidden || !process.stdin.isTTY) process.stdout.write('\n');
      resolve(line);
    };
    if (queued.length) done(queued.shift());
    else waiting.push(done);
  });
}

async function askNewPassword() {
  for (;;) {
    const first = await ask(`New password (at least ${MIN_PASSWORD_LENGTH} characters, typing is hidden): `, { hidden: true });
    const second = await ask('Type it again: ', { hidden: true });
    if (first !== second) {
      console.log('Those didn’t match — try again.');
      continue;
    }
    return first;
  }
}

async function showAuthenticatorSetup(account, secret, otpauth) {
  const grouped = secret.match(/.{1,4}/g).join(' ');
  console.log(`
Set up the authenticator app for ${account}
  1. Open Microsoft Authenticator (or Google Authenticator, 1Password…) on their phone.
  2. Add account → "Other account" / "Enter code manually" (or "Enter a setup key").
  3. Account name: ${account}
     Key:          ${grouped}
     Type:         Time based
  (Some apps accept this link instead: ${otpauth})
`);
  for (let tries = 0; tries < 3; tries++) {
    const code = await ask('Enter the 6-digit code the app now shows (or press Enter to skip): ');
    if (!code.trim()) {
      console.log('Skipped — test it by logging in.');
      return;
    }
    if (verifyCode(secret, code) !== null) {
      console.log('✔ Code accepted — the authenticator app is set up correctly.');
      return;
    }
    console.log('✖ That code didn’t match. Check the key was typed correctly and the phone’s clock is right.');
  }
}

function need(value, what) {
  if (!value) {
    console.error(`Missing ${what}. Run "npm run users" for help.`);
    process.exit(1);
  }
}

try {
  switch (command) {
    case 'add': {
      need(email, 'email');
      const role = option('role') || 'viewer';
      const name = option('name') || '';
      const password = await askNewPassword();
      const { totpSecret, otpauth, user } = await users.createUser(store, { email, name, role, password });
      console.log(`\n✔ Created ${user.email} (${user.role}).`);
      await showAuthenticatorSetup(user.email, totpSecret, otpauth);
      break;
    }
    case 'list': {
      const list = store.listUsers();
      if (!list.length) console.log('No staff accounts yet. Add one with: npm run users -- add <email> --role manager');
      for (const u of list) {
        const flags = [u.disabled ? 'DISABLED' : '', u.locked_until && Date.parse(u.locked_until) > Date.now() ? 'LOCKED' : ''].filter(Boolean).join(' ');
        console.log(`${u.email.padEnd(36)} ${u.role.padEnd(8)} ${(u.name || '').padEnd(24)} last login: ${u.last_login_at || 'never'} ${flags}`);
      }
      break;
    }
    case 'role':
      need(email, 'email');
      users.setRole(store, email, rest[0]);
      console.log(`✔ ${email} is now a ${rest[0]}.`);
      break;
    case 'reset-password':
      need(email, 'email');
      await users.resetPassword(store, email, await askNewPassword());
      console.log('✔ Password changed and all their sessions ended.');
      break;
    case 'reset-2fa': {
      need(email, 'email');
      const { totpSecret, otpauth } = users.resetTwoFactor(store, email);
      console.log('✔ New authenticator key created; the old one no longer works and all their sessions ended.');
      await showAuthenticatorSetup(email, totpSecret, otpauth);
      break;
    }
    case 'unlock':
      need(email, 'email');
      users.unlockUser(store, email);
      console.log(`✔ ${email} unlocked.`);
      break;
    case 'disable':
    case 'enable':
      need(email, 'email');
      users.setDisabled(store, email, command === 'disable');
      console.log(`✔ ${email} ${command}d.`);
      break;
    case 'logout':
      console.log(`✔ Ended ${users.logoutAll(store, email || null)} session(s).`);
      break;
    case 'remove':
      need(email, 'email');
      users.removeUser(store, email);
      console.log(`✔ ${email} removed.`);
      break;
    default:
      console.log(`Manage staff accounts for /admin.

  npm run users -- add <email> [--name "Full Name"] [--role viewer|manager]
  npm run users -- list
  npm run users -- role <email> viewer|manager
  npm run users -- reset-password <email>
  npm run users -- reset-2fa <email>
  npm run users -- unlock <email>
  npm run users -- disable <email>   |   enable <email>
  npm run users -- logout [<email>]
  npm run users -- remove <email>

Roles: viewer = can see everything; manager = can also cancel bookings, retry sync and reset demo data.`);
  }
} catch (err) {
  console.error(`✖ ${err.message}`);
  process.exitCode = 1;
} finally {
  rl?.close();
}
