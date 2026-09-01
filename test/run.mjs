/**
 * Boots the server on a scratch port and runs the end-to-end classroom
 * simulation against it. Run with `npm test`.
 */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');

const env = { ...process.env, PORT: '3199', TEACHER_PASSCODE: 'test' };
// The suite asserts on the scripted fallback bot, so keep real API creds out.
delete env.ANTHROPIC_API_KEY;
delete env.ANTHROPIC_AUTH_TOKEN;

const server = spawn('node', [path.join(root, 'server', 'index.js')], {
  env,
  stdio: ['ignore', 'pipe', 'pipe'],
});
server.stdout.on('data', (d) => process.stdout.write(`[server] ${d}`));
server.stderr.on('data', (d) => process.stderr.write(`[server] ${d}`));

await new Promise((resolve) => setTimeout(resolve, 1200));

const suite = spawn('node', [path.join(here, 'e2e.mjs')], { stdio: 'inherit' });
suite.on('exit', (code) => {
  server.kill();
  process.exit(code ?? 1);
});
