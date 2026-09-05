// Runs OpenSCAD headlessly to turn generated .scad source into an STL plus a
// preview PNG, and measures the resulting mesh so the quote email carries real
// numbers (bounding box, volume, triangle count).
import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { config } from './config.js';

// Anything that reads from disk or the network is rejected: model-authored code
// is untrusted input, and OpenSCAD will happily include() a file if asked.
const BANNED_PATTERNS = [
  { re: /\binclude\s*</i, why: 'include<> is not allowed' },
  { re: /\buse\s*</i, why: 'use<> is not allowed' },
  { re: /\bimport\s*\(/i, why: 'import() is not allowed' },
  { re: /\bimport_(stl|dxf|off)\b/i, why: 'import_* is not allowed' },
  { re: /\bsurface\s*\(/i, why: 'surface() is not allowed' },
  { re: /\bdxf_(cross|dim)\s*\(/i, why: 'dxf_* is not allowed' },
];

const MAX_SCAD_CHARS = 40_000;
const MAX_FN = 200; // keeps render time and triangle counts sane

export function sanitizeScad(src) {
  const errors = [];
  let code = String(src || '').replace(/\r\n/g, '\n');
  if (!code.trim()) errors.push('empty source');
  if (code.length > MAX_SCAD_CHARS) errors.push(`source too long (${code.length} chars)`);
  for (const { re, why } of BANNED_PATTERNS) if (re.test(code)) errors.push(why);
  // Clamp facet counts rather than failing: models routinely ask for $fn=360.
  code = code.replace(/\$fn\s*=\s*(\d+)/g, (m, n) => `$fn = ${Math.min(Number(n), MAX_FN)}`);
  return { code, errors };
}

function run(cmd, args) {
  return new Promise((resolve) => {
    execFile(cmd, args, {
      timeout: config.openscad.timeoutMs,
      maxBuffer: 8 * 1024 * 1024,
      killSignal: 'SIGKILL',
      env: { ...process.env, HOME: os.tmpdir() },
    }, (error, stdout, stderr) => {
      resolve({
        ok: !error,
        timedOut: Boolean(error?.killed),
        stdout: String(stdout || ''),
        stderr: String(stderr || ''),
      });
    });
  });
}

/**
 * STL export is pure CGAL — no display needed, so it runs the binary directly
 * and cannot be broken by anything X-related. Only the preview image needs a
 * virtual display, and that one is optional.
 */
function openscad(args, { needsDisplay = false } = {}) {
  return needsDisplay && config.openscad.useXvfb
    ? run('xvfb-run', ['-a', config.openscad.bin, ...args])
    : run(config.openscad.bin, args);
}

/**
 * Render .scad source to STL + PNG.
 * @returns {Promise<{ok: boolean, stl?: Buffer, png?: Buffer, log: string, error?: string}>}
 */
export async function renderScad(scadSource) {
  const { code, errors } = sanitizeScad(scadSource);
  if (errors.length) return { ok: false, log: '', error: `Rejected by safety check: ${errors.join('; ')}` };

  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'scad-'));
  const inFile = path.join(dir, 'model.scad');
  const stlFile = path.join(dir, 'model.stl');
  const pngFile = path.join(dir, 'model.png');

  try {
    await fs.writeFile(inFile, code);

    const stlRun = await openscad(['--export-format', 'binstl', '-o', stlFile, inFile]);
    let stl = null;
    try { stl = await fs.readFile(stlFile); } catch { /* handled below */ }
    if (!stl || stl.length < 100) {
      return {
        ok: false,
        log: stlRun.stderr,
        error: stlRun.timedOut
          ? `OpenSCAD timed out after ${Math.round(config.openscad.timeoutMs / 1000)}s`
          : (firstError(stlRun.stderr) || 'OpenSCAD produced no geometry'),
      };
    }

    // Preview render. A failure here is not fatal — the STL is the deliverable.
    const previewArgs = (scheme) => [
      '-o', pngFile,
      `--imgsize=${config.openscad.imgSize}`,
      `--colorscheme=${scheme}`,
      '--projection=p',
      '--camera=0,0,0,60,0,315,0',
      '--viewall', '--autocenter',
      inFile,
    ];
    let pngRun = await openscad(previewArgs(config.openscad.colorScheme), { needsDisplay: true });
    let png = null;
    try { png = await fs.readFile(pngFile); } catch { /* handled below */ }
    if (!png && config.openscad.colorScheme !== config.openscad.fallbackColorScheme) {
      // An unknown colour scheme is fatal to OpenSCAD, and the branded one only
      // exists inside our image — outside it, fall back to a built-in.
      pngRun = await openscad(previewArgs(config.openscad.fallbackColorScheme), { needsDisplay: true });
      try { png = await fs.readFile(pngFile); } catch { /* preview is optional */ }
    }

    return { ok: true, stl, png, log: [stlRun.stderr, pngRun.stderr].filter(Boolean).join('\n') };
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
}

// OpenSCAD is chatty; surface the first real ERROR/WARNING line for the repair prompt.
function firstError(stderr) {
  const line = String(stderr || '').split('\n').find((l) => /ERROR|WARNING/i.test(l));
  return line ? line.trim().slice(0, 400) : '';
}

/**
 * Can this box actually produce a model? Renders a real 10 mm cube rather than
 * asking the binaries whether they exist: `xvfb-run --help` succeeds on a box
 * with no xauth installed, where every real render fails.
 */
export async function checkOpenscad() {
  const probe = await run(config.openscad.bin, ['--version']);
  const version = `${probe.stderr} ${probe.stdout}`.match(/OpenSCAD version ([\w.-]+)/)?.[1];
  if (!version) {
    return {
      ok: false,
      bin: config.openscad.bin,
      error: probe.stderr.trim().slice(0, 300) || `could not run ${config.openscad.bin}`,
    };
  }

  const result = await renderScad('cube([10, 10, 10]);');
  return {
    ok: result.ok,
    version,
    bin: config.openscad.bin,
    stl: result.ok ? `${result.stl.length} bytes` : `FAILED — ${result.error}`,
    // A missing preview is survivable: the customer gets the model without a
    // thumbnail. A missing STL is not.
    preview: result.png ? `${result.png.length} bytes` : 'FAILED — no preview image (check xvfb and xauth)',
    xvfb: config.openscad.useXvfb ? 'enabled for preview images only' : 'disabled',
    colorScheme: config.openscad.colorScheme,
  };
}

/**
 * Bounding box, volume and triangle count from a binary STL. Volume uses the
 * signed-tetrahedron sum, which is exact for a closed mesh and close enough to
 * be useful for a material estimate on an almost-closed one.
 */
export function analyzeStl(buffer) {
  if (!buffer || buffer.length < 84) return null;
  const triangles = buffer.readUInt32LE(80);
  if (buffer.length < 84 + triangles * 50) return null;

  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  let volume2 = 0;

  for (let i = 0; i < triangles; i += 1) {
    const base = 84 + i * 50 + 12; // skip the per-facet normal
    const v = [];
    for (let p = 0; p < 3; p += 1) {
      const o = base + p * 12;
      const point = [buffer.readFloatLE(o), buffer.readFloatLE(o + 4), buffer.readFloatLE(o + 8)];
      v.push(point);
      for (let a = 0; a < 3; a += 1) {
        if (point[a] < min[a]) min[a] = point[a];
        if (point[a] > max[a]) max[a] = point[a];
      }
    }
    const [a, b, c] = v;
    volume2 += (
      a[0] * (b[1] * c[2] - b[2] * c[1])
      - a[1] * (b[0] * c[2] - b[2] * c[0])
      + a[2] * (b[0] * c[1] - b[1] * c[0])
    );
  }

  const round = (n) => Math.round(n * 100) / 100;
  return {
    triangles,
    bboxMm: { x: round(max[0] - min[0]), y: round(max[1] - min[1]), z: round(max[2] - min[2]) },
    volumeCm3: round(Math.abs(volume2) / 6 / 1000),
  };
}
