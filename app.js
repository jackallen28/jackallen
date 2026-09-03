const canvas = document.querySelector('#canvas');
const moduleCards = document.querySelectorAll('.module-card');
const toast = document.querySelector('#toast');
let draggedModule = null;
let zoom = 100;

moduleCards.forEach(card => {
  card.addEventListener('dragstart', () => {
    draggedModule = { name: card.dataset.module, color: card.dataset.color, icon: card.dataset.icon, type: card.dataset.type };
    card.style.opacity = '.55';
  });
  card.addEventListener('dragend', () => { card.style.opacity = '1'; });
});

canvas.addEventListener('dragover', event => { event.preventDefault(); canvas.classList.add('dragging'); });
canvas.addEventListener('dragleave', () => canvas.classList.remove('dragging'));
canvas.addEventListener('drop', event => {
  event.preventDefault();
  canvas.classList.remove('dragging');
  if (!draggedModule) return;
  const bounds = canvas.getBoundingClientRect();
  const node = document.createElement('div');
  node.className = 'flow-card';
  node.dataset.node = '';
  node.style.left = `${Math.max(12, event.clientX - bounds.left - 90)}px`;
  node.style.top = `${Math.max(45, event.clientY - bounds.top - 35)}px`;
  node.innerHTML = `<div class="node-top"><span class="node-icon" style="background:${draggedModule.color}">${draggedModule.icon}</span><div><small>${draggedModule.type.toUpperCase()} · NEW</small><h3>${draggedModule.name}</h3></div><button>•••</button></div><div class="node-footer"><span class="live-dot"></span> Ready to configure <span>Setup ›</span></div>`;
  canvas.appendChild(node);
  draggedModule = null;
});

document.querySelectorAll('.chip').forEach(chip => chip.addEventListener('click', () => {
  document.querySelectorAll('.chip').forEach(item => item.classList.remove('active'));
  chip.classList.add('active');
  moduleCards.forEach(card => card.classList.toggle('hidden', chip.dataset.filter !== 'all' && card.dataset.type !== chip.dataset.filter));
}));

document.querySelector('#moduleSearch').addEventListener('input', event => {
  const query = event.target.value.toLowerCase();
  moduleCards.forEach(card => card.classList.toggle('hidden', !card.dataset.module.toLowerCase().includes(query)));
});

document.querySelectorAll('.view-tabs button').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.view-tabs button').forEach(item => item.classList.remove('active'));
  tab.classList.add('active');
  if (tab.dataset.view !== 'canvas') {
    toast.querySelector('strong').textContent = `${tab.textContent} view is ready`;
    toast.querySelector('small').textContent = 'Your prototype stays in sync automatically.';
    toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 2200);
  }
}));

function setZoom(next) { zoom = Math.min(125, Math.max(75, next)); document.querySelector('#zoomLevel').textContent = `${zoom}%`; canvas.style.backgroundSize = `${18 * zoom / 100}px ${18 * zoom / 100}px`; }
document.querySelector('#zoomIn').onclick = () => setZoom(zoom + 10);
document.querySelector('#zoomOut').onclick = () => setZoom(zoom - 10);
document.querySelector('#fitCanvas').onclick = () => setZoom(100);
document.querySelector('#clearCanvas').onclick = () => { if (confirm('Clear all modules from the canvas?')) document.querySelectorAll('[data-node]').forEach(node => node.remove()); };

document.querySelector('#runButton').addEventListener('click', () => {
  toast.querySelector('strong').textContent = 'Prototype running';
  toast.querySelector('small').textContent = 'Uploaded to Arduino Uno successfully.';
  toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 3000);
});

document.querySelector('#promptForm').addEventListener('submit', event => {
  event.preventDefault();
  const input = document.querySelector('#promptInput');
  if (!input.value.trim()) return;
  const user = document.createElement('div'); user.className = 'message user-message'; user.textContent = input.value.trim();
  const ai = document.createElement('div'); ai.className = 'message ai-message'; ai.innerHTML = '<div class="mini-spark">✦</div><div><p>Got it — I’m mapping that behavior to your connected modules now.</p><button class="change-button">✦ Building prototype... <span>Working</span></button></div>';
  document.querySelector('#chat').append(user, ai); input.value = ''; user.scrollIntoView({behavior:'smooth'});
  setTimeout(() => { ai.querySelector('p').textContent = 'Done — I updated the prototype and kept your existing safety rules in place.'; ai.querySelector('button').innerHTML = '✓ Changes applied <span>View on canvas</span>'; }, 1100);
});
