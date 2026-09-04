/**
 * Real OpenSCAD render test — no stubs, no API key.
 *
 *   npm run test:render        (from cad-quote-bot/server)
 *
 * Needs OpenSCAD on PATH. This is the suite that covers the text-to-model half
 * of the product: the sanitiser, the headless render, the preview image, and
 * the mesh measurement that ends up in the quote.
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderScad, analyzeStl, sanitizeScad } from '../server/src/openscad.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(here, 'screenshots');
let failures = 0;
const check = (label, ok, detail = '') => {
  if (!ok) failures += 1;
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${label}${!ok && detail ? ` — ${detail}` : ''}`);
};

try {
  execFileSync(process.env.OPENSCAD_BIN || 'openscad', ['--version'], { stdio: 'ignore' });
} catch {
  console.error('OpenSCAD is not on PATH. Install it (brew install --cask openscad / apt install openscad xvfb) or run this inside the container.');
  process.exit(2);
}

// A part of the shape and complexity the bot actually produces: a plate, a
// swept cradle, boolean cuts and countersunk fixings.
const BRACKET = `
$fn = 64;
torch_d = 90; wall = 4; plate_w = 110; plate_h = 60; plate_t = 5; cradle_w = 40;

module plate() { translate([-plate_w/2, 0, 0]) cube([plate_w, plate_t, plate_h]); }
module cradle() {
  translate([0, plate_t + torch_d/2 + wall, plate_h/2]) rotate([90, 0, 0])
    difference() {
      cylinder(h = cradle_w, d = torch_d + 2*wall, center = true);
      cylinder(h = cradle_w + 1, d = torch_d, center = true);
      translate([0, torch_d/2, 0]) cube([torch_d*0.8, torch_d, cradle_w + 1], center = true);
    }
}
difference() {
  union() { plate(); cradle(); }
  for (z = [15, plate_h - 15]) translate([0, -1, z]) rotate([-90, 0, 0]) cylinder(h = plate_t + 2, d = 5.5);
}
`;

const started = Date.now();
const result = await renderScad(BRACKET);
const seconds = ((Date.now() - started) / 1000).toFixed(1);

check('a representative part renders', result.ok, result.error);
if (result.ok) {
  const stats = analyzeStl(result.stl);
  check(`the STL is a real mesh (${stats?.triangles} triangles, ${seconds}s)`, result.stl.length > 10_000 && stats.triangles > 200);
  check(`dimensions match the source (${stats.bboxMm.x} × ${stats.bboxMm.y} × ${stats.bboxMm.z} mm)`,
    Math.abs(stats.bboxMm.x - 110) < 0.5 && Math.abs(stats.bboxMm.z - 82.9) < 1);
  check(`material volume is measured (${stats.volumeCm3} cm³)`, stats.volumeCm3 > 10 && stats.volumeCm3 < 500);
  check('a preview image is produced', Boolean(result.png) && result.png.length > 5_000);

  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'render-real.png'), result.png);
  fs.writeFileSync(path.join(outDir, 'render-real.stl'), result.stl);
  console.log(`\n  Wrote ${path.join(outDir, 'render-real.png')} and .stl`);
}

// Broken geometry has to fail cleanly — that error string is what gets fed back
// to the model for the repair attempt.
const broken = await renderScad('cube([10, 10, ; // deliberate syntax error');
check('a broken model fails with a usable error', !broken.ok && Boolean(broken.error), JSON.stringify(broken.error));

// The sanitiser is the boundary around model-authored code.
for (const [label, source] of [
  ['include<>', 'include <secrets.scad>\ncube(10);'],
  ['use<>', 'use <../../etc/passwd>\ncube(10);'],
  ['import()', 'import("/etc/passwd");'],
  ['surface()', 'surface(file = "/etc/passwd");'],
]) {
  check(`${label} is rejected before OpenSCAD runs`, sanitizeScad(source).errors.length > 0);
}
check('$fn is clamped to a sane facet count', sanitizeScad('$fn = 999;\nsphere(5);').code.includes('$fn = 200'));

const rejected = await renderScad('include <x.scad>\ncube(10);');
check('a rejected model never reaches the renderer', !rejected.ok && /safety check/i.test(rejected.error));

console.log(failures ? `\n${failures} check(s) failed` : '\nAll checks passed');
process.exit(failures ? 1 : 0);
