/**
 * Boots a stand-in Anthropic endpoint plus the bilingual server, then runs the
 * suite against them. The stand-in lets the translation path actually execute
 * without real credentials. Run with `npm run test:bilingual`.
 */
import http from 'node:http';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');

// Stand-in for the Messages API. Translator and chat bot are told apart by the
// system prompt, so each gets an answer the suite can recognise.
const api = http.createServer((req, res) => {
  let body = '';
  req.on('data', (chunk) => { body += chunk; });
  req.on('end', () => {
    let parsed = {};
    try { parsed = JSON.parse(body); } catch { /* ignore */ }
    const system = JSON.stringify(parsed.system || '');
    const isTranslator = system.includes('You translate short instant-messenger messages');
    const lastUser = parsed.messages?.[parsed.messages.length - 1]?.content || '';
    const text = isTranslator
      ? `TRANSLATED(${String(lastUser).split('\n').pop()})`
      : 'idk';

    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({
      id: 'msg_test', type: 'message', role: 'assistant', model: parsed.model,
      content: [{ type: 'text', text }],
      stop_reason: 'end_turn', stop_sequence: null,
      usage: { input_tokens: 10, output_tokens: 4 },
    }));
  });
});
await new Promise((resolve) => api.listen(3301, resolve));

const env = {
  ...process.env,
  PORT: '3299',
  TEACHER_PASSCODE: 'test',
  ANTHROPIC_BASE_URL: 'http://localhost:3301',
  ANTHROPIC_API_KEY: 'sk-ant-test',
  // Human pacing is asserted in the main app's suite; here it would just add 30s
  // to every round.
  BOT_THINK_MS: '150',
  BOT_REPLY_CAP_MS: '600',
  BOT_WPM_MIN: '400',
  BOT_WPM_MAX: '600',
};

const server = spawn('node', [path.join(root, 'server', 'index.js')], { env, stdio: ['ignore', 'pipe', 'pipe'] });
server.stdout.on('data', (d) => process.stdout.write(`[server] ${d}`));
server.stderr.on('data', (d) => process.stderr.write(`[server] ${d}`));

await new Promise((resolve) => setTimeout(resolve, 1400));

const suite = spawn('node', [path.join(here, 'bilingual.mjs')], { stdio: 'inherit' });
suite.on('exit', (code) => {
  server.kill();
  api.close();
  process.exit(code ?? 1);
});
