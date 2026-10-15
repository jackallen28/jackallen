// Render a GLB with three.js in headless Chromium (SwiftShader WebGL).
//   node render3d.mjs <in.glb> <out.png> <view.json>
// view.json: {"width":1600,"height":1200,"dir":[x,y,z],"up":[0,0,1],"fill":0.82,"flip":false,
//             "ground":true,"background":"#f4f4f2"}
// Needs: npm install three@0.169.0 playwright-core@1.55.0  (in hardware/generator)
// Browser: $CHROMIUM_PATH, default /opt/pw-browsers/chromium
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");                       // hardware/generator
const [glb, out, viewFile] = process.argv.slice(2);
const view = JSON.parse(fs.readFileSync(viewFile, "utf8"));

const page_html = `<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:${view.background || "#f4f4f2"}}</style>
<script type="importmap">{"imports":{"three":"/three/build/three.module.js","three/addons/":"/three/examples/jsm/"}}</script>
</head><body><script>window.addEventListener("error", e => { window.__error = String(e.message || e); });
window.addEventListener("unhandledrejection", e => { window.__error = String(e.reason); });</script>
<script type="module">
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
const V = ${JSON.stringify(view)};
const W = V.width || 1600, H = V.height || 1200;
const renderer = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true, alpha: !!V.transparent});
renderer.setPixelRatio(1); renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = V.exposure || 1.05;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
if (!V.transparent) scene.background = new THREE.Color(V.background || "#f4f4f2");
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = V.env || 0.55;
const gltf = await new GLTFLoader().loadAsync("/model.glb");
const model = gltf.scene;
model.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true;
  const m = o.material; if (m.map) { m.map.anisotropy = 8; m.map.colorSpace = THREE.SRGBColorSpace; } } });
if (V.flip) model.rotateY(Math.PI);           // turned over by hand: underside up, text readable
scene.add(model);
model.updateMatrixWorld(true);
const box = new THREE.Box3().setFromObject(model);
const size = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
const up = new THREE.Vector3(...(V.up || [0, 0, 1]));
const dir = new THREE.Vector3(...(V.dir || [0.35, -0.75, 0.85])).normalize();
const cam = new THREE.PerspectiveCamera(V.fov || 22, W / H, 0.1, 5000);
cam.up.copy(up);
// fit: back off until the projected box fills the frame
// fit on the actual geometry (box corners are mostly empty space)
const corners = [];
model.updateMatrixWorld(true);
model.traverse(o => { if (!o.isMesh) return;
  const pos = o.geometry.attributes.position, step = Math.max(1, Math.floor(pos.count / 4000));
  for (let i = 0; i < pos.count; i += step) corners.push(new THREE.Vector3().fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld)); });
let dist = size.length() * 3;
const target = c.clone();
const place = () => { cam.position.copy(target).addScaledVector(dir, dist); cam.lookAt(target);
  cam.updateMatrixWorld(); cam.updateProjectionMatrix(); };
for (let i = 0; i < 40; i++) {             // zoom to fit and pan to centre the projected model
  place();
  let x0 = 9, x1 = -9, y0 = 9, y1 = -9;
  for (const p of corners) { const q = p.clone().project(cam);
    x0 = Math.min(x0, q.x); x1 = Math.max(x1, q.x); y0 = Math.min(y0, q.y); y1 = Math.max(y1, q.y); }
  const hh = dist * Math.tan(cam.fov * Math.PI / 360), hw = hh * cam.aspect;
  target.addScaledVector(new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0), (x0 + x1) / 2 * hw)
        .addScaledVector(new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1), (y0 + y1) / 2 * hh);
  dist *= Math.max(x1 - x0, y1 - y0) / 2 / (V.fill || 0.82);
}
place();
cam.near = dist / 50; cam.far = dist * 10; cam.updateProjectionMatrix();
const key = new THREE.DirectionalLight(0xffffff, V.key || 2.2);
key.position.copy(c).add(new THREE.Vector3(-0.5, -0.8, 1.6).multiplyScalar(size.length()));
key.target.position.copy(c); key.castShadow = true;
const s = size.length() * 0.8; Object.assign(key.shadow.camera, {left: -s, right: s, top: s, bottom: -s, near: 0.1, far: size.length() * 6});
key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02;
scene.add(key, key.target);
const fillL = new THREE.DirectionalLight(0xdfe8ff, 0.6); fillL.position.copy(c).add(new THREE.Vector3(1, 0.6, 0.6).multiplyScalar(size.length()));
scene.add(fillL, new THREE.HemisphereLight(0xffffff, 0x444444, 0.35));
if (V.ground !== false) {
  const g = new THREE.Mesh(new THREE.PlaneGeometry(size.length() * 8, size.length() * 8), new THREE.ShadowMaterial({opacity: 0.18}));
  g.position.set(c.x, c.y, box.min.z - 0.01); g.receiveShadow = true; scene.add(g);
}
renderer.render(scene, cam);
window.__done = true;
</script></body></html>`;

const mime = {".js": "text/javascript", ".glb": "model/gltf-binary", ".html": "text/html"};
const server = http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split("?")[0]);
  let file = null;
  if (url === "/favicon.ico") { res.writeHead(204); return res.end(); }
  if (url === "/" || url === "/index.html") { res.writeHead(200, {"content-type": "text/html"}); return res.end(page_html); }
  if (url === "/model.glb") file = path.resolve(glb);
  else if (url.startsWith("/three/")) file = path.join(root, "node_modules", url);
  if (!file || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, {"content-type": mime[path.extname(file)] || "application/octet-stream"});
  fs.createReadStream(file).pipe(res);
});
await new Promise(r => server.listen(0, "127.0.0.1", r));
const port = server.address().port;
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || "/opt/pw-browsers/chromium",
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const page = await browser.newPage({viewport: {width: view.width || 1600, height: view.height || 1200}});
const errors = [];
page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", e => errors.push(String(e)));
await page.goto(`http://127.0.0.1:${port}/`);
try { await page.waitForFunction(() => window.__done === true || window.__error, null, {timeout: 300000}); }
catch (e) { console.error(errors.join("\n")); await browser.close(); server.close(); throw e; }
const failed = await page.evaluate(() => window.__error);
if (failed) { console.error("render failed:", failed, errors.join("\n")); await browser.close(); server.close(); process.exit(1); }
await (await page.$("canvas")).screenshot({path: out, omitBackground: !!view.transparent});
await browser.close(); server.close();
if (errors.length) console.error(errors.join("\n"));
