import { existsSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const requiredFiles = ['index.html', 'styles.css', 'app.js'];
const requiredIds = [
  'canvas', 'clearCanvas', 'fitCanvas', 'moduleSearch', 'promptForm',
  'promptInput', 'runButton', 'toast', 'zoomIn', 'zoomLevel', 'zoomOut',
];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

for (const file of requiredFiles) {
  assert(existsSync(file), `Missing required asset: ${file}`);
}

const syntaxCheck = spawnSync(process.execPath, ['--check', 'app.js'], {
  encoding: 'utf8',
});
assert(syntaxCheck.status === 0, syntaxCheck.stderr || 'app.js failed its syntax check');

const html = readFileSync('index.html', 'utf8');
const ids = [...html.matchAll(/\bid=["']([^"']+)["']/g)].map((match) => match[1]);
const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
assert(duplicateIds.length === 0, `Duplicate HTML IDs: ${[...new Set(duplicateIds)].join(', ')}`);

for (const id of requiredIds) {
  assert(ids.includes(id), `Missing interactive element: #${id}`);
}

const localAssets = [...html.matchAll(/(?:href|src)=["']([^"']+)["']/g)]
  .map((match) => match[1])
  .filter((path) => !/^(?:https?:|data:|#)/.test(path));
for (const asset of localAssets) {
  assert(existsSync(asset), `HTML references missing local asset: ${asset}`);
}

console.log(`Verified ${requiredFiles.length} assets, ${ids.length} unique IDs, and JavaScript syntax.`);
