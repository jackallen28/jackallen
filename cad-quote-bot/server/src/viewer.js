// Standalone STL viewer, opened in a new tab from the chat. Self-contained
// except for three.js from a CDN: the STL parser and the orbit controls are
// inline so there is nothing else to break.
import { config } from './config.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

export function renderViewerPage({ title, stlUrl, stats }) {
  const accent = config.brand.accent;
  const chips = stats ? [
    `${stats.bboxMm.x} × ${stats.bboxMm.y} × ${stats.bboxMm.z} mm`,
    `${stats.volumeCm3} cm³`,
    `${stats.triangles.toLocaleString('en')} triangles`,
  ] : [];

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<title>${esc(title)} · 3D preview</title>
<style>
  :root { --accent: ${accent}; --ink: #14161a; --muted: #6b7280; --line: #eceef1; }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: #fff; color: var(--ink); display: flex; flex-direction: column;
    font: 400 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  header {
    display: flex; align-items: center; gap: 16px; padding: 14px 20px;
    border-bottom: 1px solid var(--line); flex-wrap: wrap;
  }
  .mark { width: 10px; height: 22px; background: var(--accent); border-radius: 2px; flex: none; }
  h1 { font-size: 15px; font-weight: 650; margin: 0; letter-spacing: -.01em; }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip { font-size: 12px; color: var(--muted); border: 1px solid var(--line); border-radius: 999px; padding: 3px 10px; }
  .spacer { flex: 1 1 auto; }
  .actions { display: flex; gap: 8px; }
  button, a.btn {
    font: inherit; font-size: 14px; font-weight: 600; border-radius: 8px; padding: 9px 16px;
    border: 1px solid var(--line); background: #fff; color: var(--ink); cursor: pointer;
    text-decoration: none; display: inline-block; transition: background .15s, border-color .15s;
  }
  button:hover, a.btn:hover { border-color: #d9dce1; background: #fafbfc; }
  .primary { background: var(--accent); border-color: var(--accent); color: #fff; }
  .primary:hover { background: #e85f14; border-color: #e85f14; }
  main { flex: 1 1 auto; position: relative; min-height: 0; }
  canvas { display: block; width: 100%; height: 100%; }
  .hint {
    position: absolute; left: 20px; bottom: 18px; font-size: 12px; color: var(--muted);
    background: rgba(255,255,255,.9); padding: 6px 10px; border-radius: 8px; border: 1px solid var(--line);
  }
  .status {
    position: absolute; inset: 0; display: grid; place-items: center; color: var(--muted); font-size: 14px;
  }
  .status.hidden { display: none; }
  .bar { width: 120px; height: 3px; background: var(--line); border-radius: 2px; overflow: hidden; margin-top: 10px; }
  .bar i { display: block; height: 100%; width: 40%; background: var(--accent); animation: slide 1.1s ease-in-out infinite; }
  @keyframes slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(320%); } }
  @media (max-width: 640px) { .chips { display: none; } header { padding: 12px 14px; } }
</style>
</head>
<body>
<header>
  <span class="mark"></span>
  <h1>${esc(title)}</h1>
  <div class="chips">${chips.map((c) => `<span class="chip">${esc(c)}</span>`).join('')}</div>
  <span class="spacer"></span>
  <div class="actions">
    <a class="btn" href="${esc(stlUrl)}" download>Download STL</a>
    <button class="primary" id="back">Return to chat</button>
  </div>
</header>
<main>
  <canvas id="c"></canvas>
  <div class="status" id="status"><div style="text-align:center">Loading model<div class="bar"><i></i></div></div></div>
  <div class="hint">Drag to rotate · scroll to zoom · right-drag or two fingers to pan</div>
</main>

<script src="/vendor/three.min.js"></script>
<script>
(function () {
  var STL_URL = ${JSON.stringify(stlUrl)};
  var ACCENT = ${JSON.stringify(accent)};

  function fail(message) {
    document.getElementById('status').innerHTML =
      '<div style="text-align:center">' + message +
      '<br><a href="' + STL_URL + '" style="color:' + ACCENT + '">Download the STL instead</a></div>';
  }
  if (typeof THREE === 'undefined') { fail('The 3D viewer could not start.'); return; }

  document.getElementById('back').addEventListener('click', function () {
    try { if (window.opener && !window.opener.closed) window.opener.postMessage({ type: 'cadbot:viewer-return' }, '*'); } catch (e) {}
    window.close();
    // If the browser refuses to close a tab it did not open, say so rather than doing nothing.
    setTimeout(function () {
      document.getElementById('back').textContent = 'Close this tab to return';
    }, 350);
  });

  // --- minimal STL parser (binary and ASCII) ------------------------------
  function parseSTL(buffer) {
    var view = new DataView(buffer);
    var isBinary = true;
    if (buffer.byteLength > 84) {
      var faces = view.getUint32(80, true);
      if (84 + faces * 50 !== buffer.byteLength) isBinary = false;
    } else { isBinary = false; }

    var positions = [];
    if (isBinary) {
      var n = view.getUint32(80, true);
      for (var i = 0; i < n; i++) {
        var o = 84 + i * 50 + 12;
        for (var v = 0; v < 3; v++) {
          positions.push(view.getFloat32(o + v * 12, true), view.getFloat32(o + v * 12 + 4, true), view.getFloat32(o + v * 12 + 8, true));
        }
      }
    } else {
      var text = new TextDecoder().decode(buffer);
      var re = /vertex\\s+([-\\d.eE+]+)\\s+([-\\d.eE+]+)\\s+([-\\d.eE+]+)/g, m;
      while ((m = re.exec(text)) !== null) positions.push(parseFloat(m[1]), parseFloat(m[2]), parseFloat(m[3]));
    }
    var geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
    geom.computeVertexNormals();
    return geom;
  }

  // --- scene ---------------------------------------------------------------
  var canvas = document.getElementById('c');
  var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0xffffff);
  var camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100000);

  scene.add(new THREE.HemisphereLight(0xffffff, 0x8e949c, 0.55));
  var key = new THREE.DirectionalLight(0xffffff, 0.95); key.position.set(1, 1.6, 0.9); scene.add(key);
  var fill = new THREE.DirectionalLight(0xffffff, 0.45); fill.position.set(-1.2, 0.3, -0.9); scene.add(fill);
  var rim = new THREE.DirectionalLight(0xffffff, 0.3); rim.position.set(0.2, -1, 0.4); scene.add(rim);

  var target = new THREE.Vector3(), radius = 100;
  var spherical = { theta: Math.PI * 0.25, phi: Math.PI * 0.35, dist: 300 };
  var mesh = null, grid = null;

  function applyCamera() {
    var sinP = Math.sin(spherical.phi);
    camera.position.set(
      target.x + spherical.dist * sinP * Math.sin(spherical.theta),
      target.y + spherical.dist * Math.cos(spherical.phi),
      target.z + spherical.dist * sinP * Math.cos(spherical.theta)
    );
    camera.lookAt(target);
  }

  function resize() {
    var w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  function frame() { requestAnimationFrame(frame); resize(); renderer.render(scene, camera); }

  // --- interaction ---------------------------------------------------------
  var dragging = null, last = { x: 0, y: 0 };
  canvas.addEventListener('pointerdown', function (e) {
    dragging = (e.button === 2 || e.shiftKey) ? 'pan' : 'rotate';
    last = { x: e.clientX, y: e.clientY };
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', function (e) {
    if (!dragging) return;
    var dx = e.clientX - last.x, dy = e.clientY - last.y;
    last = { x: e.clientX, y: e.clientY };
    if (dragging === 'rotate') {
      spherical.theta -= dx * 0.008;
      spherical.phi = Math.max(0.05, Math.min(Math.PI - 0.05, spherical.phi - dy * 0.008));
    } else {
      var scale = spherical.dist * 0.0018;
      var right = new THREE.Vector3().crossVectors(camera.up, camera.getWorldDirection(new THREE.Vector3())).normalize();
      target.addScaledVector(right, dx * scale);
      target.y += dy * scale;
    }
    applyCamera();
  });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (ev) {
    canvas.addEventListener(ev, function () { dragging = null; });
  });
  canvas.addEventListener('contextmenu', function (e) { e.preventDefault(); });
  canvas.addEventListener('wheel', function (e) {
    e.preventDefault();
    spherical.dist = Math.max(radius * 0.4, Math.min(radius * 12, spherical.dist * (1 + Math.sign(e.deltaY) * 0.12)));
    applyCamera();
  }, { passive: false });

  var pinch = null;
  canvas.addEventListener('touchmove', function (e) {
    if (e.touches.length !== 2) { pinch = null; return; }
    e.preventDefault();
    var d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
    if (pinch) {
      spherical.dist = Math.max(radius * 0.4, Math.min(radius * 12, spherical.dist * (pinch / d)));
      applyCamera();
    }
    pinch = d;
  }, { passive: false });
  canvas.addEventListener('touchend', function () { pinch = null; });

  // --- load ----------------------------------------------------------------
  fetch(STL_URL)
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.arrayBuffer(); })
    .then(function (buf) {
      var geom = parseSTL(buf);
      geom.computeBoundingBox();
      geom.computeBoundingSphere();
      var box = geom.boundingBox;
      var centre = box.getCenter(new THREE.Vector3());
      radius = Math.max(geom.boundingSphere.radius, 1);

      // Mid grey with a soft highlight: dark enough to read as a solid object
      // against the white page, neutral enough not to fight the accent colour.
      mesh = new THREE.Mesh(geom, new THREE.MeshPhongMaterial({
        color: 0xb9bfc7, specular: 0x3a3f46, shininess: 26,
        // Generated meshes occasionally carry inconsistent winding; drawing both
        // sides means a flipped facet shows as a surface rather than a hole.
        side: THREE.DoubleSide
      }));
      // Stand the part on the ground plane and centre it in X/Y.
      mesh.position.set(-centre.x, -box.min.y, -centre.z);
      scene.add(mesh);

      var edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(geom, 32),
        new THREE.LineBasicMaterial({ color: new THREE.Color(ACCENT), transparent: true, opacity: 0.55 })
      );
      edges.position.copy(mesh.position);
      scene.add(edges);

      grid = new THREE.GridHelper(radius * 6, 24, 0xc7cbd1, 0xe4e7ea);
      grid.position.y = 0;
      scene.add(grid);

      target.set(0, (box.max.y - box.min.y) / 2, 0);
      spherical.dist = radius * 3.2;
      applyCamera();
      document.getElementById('status').classList.add('hidden');
      frame();
    })
    .catch(function (err) {
      fail('Could not load the model.');
      console.error(err);
    });
})();
</script>
</body>
</html>`;
}
