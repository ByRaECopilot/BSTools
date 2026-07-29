/*
 * Mermaid - Editor grafico  ·  BSTools
 * https://www.byraesoftware.com  ·  CC0 1.0 (dominio publico)
 *
 * Editor de diagramas de flujo: arrastra formas, unelas con flechas y el codigo
 * mermaid se genera en tiempo real. Sin dependencias externas salvo mermaid.js
 * (empaquetado en vendor/), todo funciona en local abriendo el index.html.
 */
'use strict';

// --- catalogo de formas (sintaxis mermaid flowchart) -------------------------
// wrap(id, texto) devuelve el nodo mermaid ya formateado.
const SHAPES = {
  rect:    { name: 'Proceso',   wrap: (i, t) => `${i}["${t}"]` },
  round:   { name: 'Redondeado', wrap: (i, t) => `${i}("${t}")` },
  stadium: { name: 'Terminal',  wrap: (i, t) => `${i}(["${t}"])` },
  subroutine: { name: 'Subproceso', wrap: (i, t) => `${i}[["${t}"]]` },
  cylinder: { name: 'Base datos', wrap: (i, t) => `${i}[("${t}")]` },
  circle:  { name: 'Circulo',   wrap: (i, t) => `${i}(("${t}"))` },
  diamond: { name: 'Decision',  wrap: (i, t) => `${i}{"${t}"}` },
  hexagon: { name: 'Preparar',  wrap: (i, t) => `${i}{{"${t}"}}` },
};
const SHAPE_ORDER = ['rect', 'round', 'stadium', 'subroutine', 'cylinder', 'circle', 'diamond', 'hexagon'];

const EDGE_STYLES = {
  arrow:  { open: '-->', label: (l) => `-->|"${l}"|` },
  open:   { open: '---', label: (l) => `---|"${l}"|` },
  dotted: { open: '-.->', label: (l) => `-.->|"${l}"|` },
  thick:  { open: '==>', label: (l) => `==>|"${l}"|` },
};

const SVGNS = 'http://www.w3.org/2000/svg';
const NODE_H = 52, MIN_W = 96, PAD_X = 26;

// --- estado ------------------------------------------------------------------
let state = { nodes: [], edges: [], dir: 'TD', seq: 0 };
let view = { scale: 1, tx: 0, ty: 0 };
let currentShape = 'rect';
let currentEdgeStyle = 'arrow';
let selection = null;             // {type:'node'|'edge', id}
let undoStack = [], redoStack = [];

const $ = (s) => document.querySelector(s);
const svg = $('#canvas');
const gNodes = $('#nodes'), gEdges = $('#edges');
const tempEdge = $('#tempEdge');
const editor = $('#editor');

// medidor de texto para dimensionar nodos
const meas = document.createElement('canvas').getContext('2d');
function measureLabel(text) {
  meas.font = '600 14px -apple-system, "Segoe UI", Roboto, sans-serif';
  const lines = String(text || '').split('\n');
  const w = Math.max(...lines.map((l) => meas.measureText(l).width), 0);
  return w;
}

// =============================================================================
//  Coordenadas: pantalla <-> mundo
// =============================================================================
function toWorld(clientX, clientY) {
  const r = svg.getBoundingClientRect();
  return {
    x: (clientX - r.left - view.tx) / view.scale,
    y: (clientY - r.top - view.ty) / view.scale,
  };
}
function applyView() {
  $('#world').setAttribute('transform', `translate(${view.tx} ${view.ty}) scale(${view.scale})`);
}

// =============================================================================
//  Modelo
// =============================================================================
function nodeId() { return 'n' + (++state.seq); }

function addNode(shape, x, y, label) {
  const id = nodeId();
  const n = { id, shape, x, y, label: label || SHAPES[shape].name, color: 'default' };
  sizeNode(n);
  state.nodes.push(n);
  return n;
}
function sizeNode(n) {
  const w = Math.max(MIN_W, Math.round(measureLabel(n.label) + PAD_X * 2));
  n.w = (n.shape === 'circle') ? Math.max(w, NODE_H + 16) : w;
  n.h = (n.shape === 'circle') ? n.w : NODE_H;
}
function getNode(id) { return state.nodes.find((n) => n.id === id); }

function addEdge(from, to) {
  if (from === to) return null;
  const id = 'e' + (++state.seq);
  const e = { id, from, to, label: '', style: currentEdgeStyle };
  state.edges.push(e);
  return e;
}

function deleteSelection() {
  if (!selection) return;
  snapshot();
  if (selection.type === 'node') {
    state.nodes = state.nodes.filter((n) => n.id !== selection.id);
    state.edges = state.edges.filter((e) => e.from !== selection.id && e.to !== selection.id);
  } else {
    state.edges = state.edges.filter((e) => e.id !== selection.id);
  }
  selection = null;
  render();
}

// =============================================================================
//  Undo / redo
// =============================================================================
function snapshot() {
  undoStack.push(JSON.stringify({ nodes: state.nodes, edges: state.edges, dir: state.dir, seq: state.seq }));
  if (undoStack.length > 100) undoStack.shift();
  redoStack = [];
  refreshUndoButtons();
}
function restore(json) {
  const s = JSON.parse(json);
  state.nodes = s.nodes; state.edges = s.edges; state.dir = s.dir; state.seq = s.seq;
  selection = null;
  syncDirButtons();
  render();
}
function undo() {
  if (!undoStack.length) return;
  redoStack.push(JSON.stringify({ nodes: state.nodes, edges: state.edges, dir: state.dir, seq: state.seq }));
  restore(undoStack.pop());
  refreshUndoButtons();
}
function redo() {
  if (!redoStack.length) return;
  undoStack.push(JSON.stringify({ nodes: state.nodes, edges: state.edges, dir: state.dir, seq: state.seq }));
  restore(redoStack.pop());
  refreshUndoButtons();
}
function refreshUndoButtons() {
  $('#undo').disabled = !undoStack.length;
  $('#redo').disabled = !redoStack.length;
}

// =============================================================================
//  Dibujo de formas en el lienzo (SVG)
// =============================================================================
function shapeGeometry(shape, w, h) {
  // Devuelve un elemento SVG (sin posicionar) centrado en (0,0) del grupo del nodo.
  const el = (tag) => document.createElementNS(SVGNS, tag);
  let node;
  switch (shape) {
    case 'round': node = el('rect'); setAttrs(node, { x: 0, y: 0, width: w, height: h, rx: 12 }); break;
    case 'stadium': node = el('rect'); setAttrs(node, { x: 0, y: 0, width: w, height: h, rx: h / 2 }); break;
    case 'circle': { node = el('ellipse'); setAttrs(node, { cx: w / 2, cy: h / 2, rx: w / 2, ry: h / 2 }); break; }
    case 'diamond': {
      node = el('polygon');
      node.setAttribute('points', `${w / 2},0 ${w},${h / 2} ${w / 2},${h} 0,${h / 2}`);
      break;
    }
    case 'hexagon': {
      node = el('polygon'); const c = h * 0.34;
      node.setAttribute('points', `${c},0 ${w - c},0 ${w},${h / 2} ${w - c},${h} ${c},${h} 0,${h / 2}`);
      break;
    }
    case 'subroutine':
    case 'cylinder':
    case 'rect':
    default: node = el('rect'); setAttrs(node, { x: 0, y: 0, width: w, height: h, rx: 4 }); break;
  }
  node.setAttribute('class', 'node-rect');
  return node;
}
function setAttrs(el, obj) { for (const k in obj) el.setAttribute(k, obj[k]); }

const NODE_COLORS = {
  '#3b82f6': ['#3b82f6', '#dbeafe'], '#22c55e': ['#22c55e', '#dcfce7'],
  '#f59e0b': ['#f59e0b', '#fef3c7'], '#ef4444': ['#ef4444', '#fee2e2'],
  '#a855f7': ['#a855f7', '#f3e8ff'],
};

function drawNode(n) {
  const g = document.createElementNS(SVGNS, 'g');
  g.setAttribute('class', 'node' + (selection && selection.type === 'node' && selection.id === n.id ? ' sel' : ''));
  g.setAttribute('transform', `translate(${n.x - n.w / 2} ${n.y - n.h / 2})`);
  g.dataset.id = n.id;

  const shape = shapeGeometry(n.shape, n.w, n.h);
  if (n.color !== 'default' && NODE_COLORS[n.color]) {
    const [stroke, fill] = NODE_COLORS[n.color];
    shape.style.fill = fill; shape.style.stroke = stroke;
  }
  g.appendChild(shape);

  // detalle extra de subproceso / cilindro
  if (n.shape === 'subroutine') {
    for (const gx of [8, n.w - 8]) {
      const l = document.createElementNS(SVGNS, 'line');
      setAttrs(l, { x1: gx, y1: 0, x2: gx, y2: n.h, stroke: 'var(--node-stroke)', 'stroke-width': 1.4 });
      g.appendChild(l);
    }
  }
  if (n.shape === 'cylinder') {
    const cap = document.createElementNS(SVGNS, 'path');
    cap.setAttribute('d', `M0,9 A ${n.w / 2} 9 0 0 0 ${n.w},9`);
    setAttrs(cap, { fill: 'none', stroke: 'var(--node-stroke)', 'stroke-width': 1.4 });
    g.appendChild(cap);
  }

  const lines = String(n.label).split('\n');
  const t = document.createElementNS(SVGNS, 'text');
  t.setAttribute('class', 'node-label');
  setAttrs(t, { x: n.w / 2, y: n.h / 2 });
  lines.forEach((ln, i) => {
    const ts = document.createElementNS(SVGNS, 'tspan');
    setAttrs(ts, { x: n.w / 2, dy: i === 0 ? -(lines.length - 1) * 8 : 16 });
    ts.textContent = ln;
    t.appendChild(ts);
  });
  g.appendChild(t);

  // puertos de conexion (4 lados)
  const ports = [[n.w / 2, 0], [n.w, n.h / 2], [n.w / 2, n.h], [0, n.h / 2]];
  for (const [px, py] of ports) {
    const p = document.createElementNS(SVGNS, 'circle');
    setAttrs(p, { cx: px, cy: py, r: 5.5 });
    p.setAttribute('class', 'port');
    p.addEventListener('pointerdown', (ev) => startLink(ev, n));
    g.appendChild(p);
  }

  g.addEventListener('pointerdown', (ev) => startNodeDrag(ev, n));
  g.addEventListener('dblclick', (ev) => { ev.stopPropagation(); editLabel(n); });
  gNodes.appendChild(g);
}

// interseccion de la recta centro-a-centro con el borde del nodo (rect aprox.)
function borderPoint(n, tx, ty) {
  const dx = tx - n.x, dy = ty - n.y;
  if (dx === 0 && dy === 0) return { x: n.x, y: n.y };
  const hw = n.w / 2 + 2, hh = n.h / 2 + 2;
  const scale = 1 / Math.max(Math.abs(dx) / hw, Math.abs(dy) / hh);
  return { x: n.x + dx * scale, y: n.y + dy * scale };
}

function drawEdge(e) {
  const a = getNode(e.from), b = getNode(e.to);
  if (!a || !b) return;
  const p1 = borderPoint(a, b.x, b.y);
  const p2 = borderPoint(b, a.x, a.y);
  const isSel = selection && selection.type === 'edge' && selection.id === e.id;

  const g = document.createElementNS(SVGNS, 'g');
  g.setAttribute('class', 'edge' + (isSel ? ' sel' : ''));
  g.dataset.id = e.id;

  const d = `M ${p1.x} ${p1.y} L ${p2.x} ${p2.y}`;
  const path = document.createElementNS(SVGNS, 'path');
  path.setAttribute('class', 'edge-path');
  path.setAttribute('d', d);
  if (e.style === 'dotted') path.setAttribute('stroke-dasharray', '5 5');
  if (e.style === 'thick') path.setAttribute('stroke-width', '3.5');
  if (e.style !== 'open') path.setAttribute('marker-end', isSel ? 'url(#arrowSel)' : 'url(#arrow)');

  const hit = document.createElementNS(SVGNS, 'path');
  hit.setAttribute('class', 'edge-hit');
  hit.setAttribute('d', d);
  hit.addEventListener('pointerdown', (ev) => { ev.stopPropagation(); select('edge', e.id); });
  hit.addEventListener('dblclick', (ev) => { ev.stopPropagation(); editEdgeLabel(e); });

  g.appendChild(hit);
  g.appendChild(path);

  if (e.label) {
    const mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2;
    const bg = document.createElementNS(SVGNS, 'rect');
    const tw = measureLabel(e.label) + 12;
    setAttrs(bg, { x: mx - tw / 2, y: my - 11, width: tw, height: 22, rx: 5 });
    bg.setAttribute('class', 'edge-label-bg');
    const t = document.createElementNS(SVGNS, 'text');
    setAttrs(t, { x: mx, y: my });
    t.setAttribute('class', 'edge-label');
    t.textContent = e.label;
    t.addEventListener('dblclick', (ev) => { ev.stopPropagation(); editEdgeLabel(e); });
    g.appendChild(bg); g.appendChild(t);
  }
  gEdges.appendChild(g);
}

// =============================================================================
//  Render completo
// =============================================================================
let renderScheduled = false;
function render() {
  gNodes.textContent = '';
  gEdges.textContent = '';
  state.edges.forEach(drawEdge);
  state.nodes.forEach(drawNode);
  $('#hint').style.display = state.nodes.length ? 'none' : '';
  positionFloatbar();
  generateCode();
  save();
}

// =============================================================================
//  Generacion del codigo mermaid
// =============================================================================
function esc(s) { return String(s).replace(/"/g, '#quot;').replace(/\n/g, '<br>'); }

function buildCode() {
  const lines = [`flowchart ${state.dir}`];
  for (const n of state.nodes) {
    lines.push('    ' + SHAPES[n.shape].wrap(n.id, esc(n.label)));
  }
  for (const e of state.edges) {
    const st = EDGE_STYLES[e.style];
    const conn = e.label ? st.label(esc(e.label)) : st.open;
    lines.push(`    ${e.from} ${conn} ${e.to}`);
  }
  const styled = state.nodes.filter((n) => n.color !== 'default' && NODE_COLORS[n.color]);
  if (styled.length) lines.push('');
  for (const n of styled) {
    const [stroke, fill] = NODE_COLORS[n.color];
    lines.push(`    style ${n.id} fill:${fill},stroke:${stroke},stroke-width:2px,color:#111`);
  }
  return lines.join('\n');
}

function generateCode() {
  const code = buildCode();
  $('#code').innerHTML = highlight(code);
  if ($('#previewView').classList.contains('show')) schedulePreview();
}

function highlight(code) {
  return code.split('\n').map((line) => {
    let h = line
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    h = h.replace(/^(\s*)(flowchart|style)\b/, (m, sp, kw) => `${sp}<span class="tok-kw">${kw}</span>`);
    h = h.replace(/(--&gt;|---|-\.-&gt;|==&gt;)/g, '<span class="tok-arr">$1</span>');
    h = h.replace(/&quot;([^&]*)&quot;|#quot;/g, (m) => `<span class="tok-str">${m}</span>`);
    return h;
  }).join('\n');
}

// =============================================================================
//  Interaccion: arrastrar nodos, conectar, panear
// =============================================================================
let drag = null;

function startNodeDrag(ev, n) {
  if (ev.target.classList.contains('port')) return;
  ev.stopPropagation();
  select('node', n.id);
  const start = toWorld(ev.clientX, ev.clientY);
  drag = { type: 'node', node: n, dx: start.x - n.x, dy: start.y - n.y, moved: false, snap: false };
  svg.setPointerCapture(ev.pointerId);
}

function startLink(ev, n) {
  ev.stopPropagation();
  svg.classList.add('linking');
  drag = { type: 'link', from: n };
  svg.setPointerCapture(ev.pointerId);
}

function startPan(ev) {
  if (ev.target.closest('.node') || ev.target.closest('.edge')) return;
  select(null);
  drag = { type: 'pan', sx: ev.clientX, sy: ev.clientY, tx: view.tx, ty: view.ty };
  svg.classList.add('panning');
  svg.setPointerCapture(ev.pointerId);
}

svg.addEventListener('pointerdown', startPan);

svg.addEventListener('pointermove', (ev) => {
  if (!drag) return;
  const w = toWorld(ev.clientX, ev.clientY);
  if (drag.type === 'node') {
    if (!drag.snap) { snapshot(); drag.snap = true; }
    drag.moved = true;
    drag.node.x = Math.round((w.x - drag.dx) / 10) * 10;
    drag.node.y = Math.round((w.y - drag.dy) / 10) * 10;
    render();
  } else if (drag.type === 'link') {
    const p = borderPoint(drag.from, w.x, w.y);
    tempEdge.style.display = '';
    tempEdge.setAttribute('d', `M ${p.x} ${p.y} L ${w.x} ${w.y}`);
    drag.overNode = nodeAt(ev.clientX, ev.clientY, drag.from.id);
  } else if (drag.type === 'pan') {
    view.tx = drag.tx + (ev.clientX - drag.sx);
    view.ty = drag.ty + (ev.clientY - drag.sy);
    applyView();
  }
});

svg.addEventListener('pointerup', (ev) => {
  if (!drag) return;
  if (drag.type === 'link') {
    tempEdge.style.display = 'none';
    svg.classList.remove('linking');
    const target = nodeAt(ev.clientX, ev.clientY, drag.from.id);
    if (target) {
      snapshot();
      const e = addEdge(drag.from.id, target.id);
      render();
      if (e) select('edge', e.id);
    }
  } else if (drag.type === 'pan') {
    svg.classList.remove('panning');
  } else if (drag.type === 'node' && !drag.moved) {
    // clic simple: solo seleccionar (ya hecho)
  }
  drag = null;
});

function nodeAt(clientX, clientY, exceptId) {
  const w = toWorld(clientX, clientY);
  // recorrer de arriba a abajo (ultimos dibujados primero)
  for (let i = state.nodes.length - 1; i >= 0; i--) {
    const n = state.nodes[i];
    if (n.id === exceptId) continue;
    if (Math.abs(w.x - n.x) <= n.w / 2 && Math.abs(w.y - n.y) <= n.h / 2) return n;
  }
  return null;
}

// =============================================================================
//  Seleccion + barra flotante
// =============================================================================
function select(type, id) {
  selection = type ? { type, id } : null;
  render();
}
function positionFloatbar() {
  const fb = $('#floatbar');
  if (!selection) { fb.style.display = 'none'; return; }
  let cx, top;
  if (selection.type === 'node') {
    const n = getNode(selection.id);
    if (!n) { fb.style.display = 'none'; return; }
    cx = view.tx + n.x * view.scale;
    top = view.ty + (n.y - n.h / 2) * view.scale - 52;
  } else {
    const e = state.edges.find((x) => x.id === selection.id);
    const a = getNode(e.from), b = getNode(e.to);
    if (!a || !b) { fb.style.display = 'none'; return; }
    cx = view.tx + ((a.x + b.x) / 2) * view.scale;
    top = view.ty + ((a.y + b.y) / 2) * view.scale - 52;
  }
  fb.style.display = 'flex';
  // el fondo tiene un padre relativo (.canvas-wrap); las coords son relativas a el
  fb.style.left = Math.max(8, cx - fb.offsetWidth / 2) + 'px';
  fb.style.top = Math.max(8, top) + 'px';
  // los swatches de color solo tienen sentido en nodos
  fb.querySelectorAll('.swatch, .sep').forEach((el) => {
    el.style.display = selection.type === 'node' ? '' : 'none';
  });
}

// =============================================================================
//  Edicion de etiquetas (input flotante)
// =============================================================================
let editing = null;
function showEditor(cx, cy, w, value, onCommit) {
  editing = onCommit;
  editor.style.display = 'block';
  editor.style.width = Math.max(90, w) + 'px';
  editor.style.left = (cx - Math.max(90, w) / 2) + 'px';
  editor.style.top = (cy - 18) + 'px';
  editor.value = value;
  editor.focus();
  editor.select();
}
function commitEditor() {
  if (!editing) return;
  const cb = editing; editing = null;
  editor.style.display = 'none';
  cb(editor.value);
}
editor.addEventListener('blur', commitEditor);
editor.addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); commitEditor(); }
  if (ev.key === 'Escape') { editing = null; editor.style.display = 'none'; }
});

function editLabel(n) {
  const cx = view.tx + n.x * view.scale;
  const cy = view.ty + n.y * view.scale;
  showEditor(cx, cy, n.w * view.scale, n.label, (val) => {
    snapshot();
    n.label = val.trim() || n.label;
    sizeNode(n);
    render();
  });
}
function editEdgeLabel(e) {
  const a = getNode(e.from), b = getNode(e.to);
  const cx = view.tx + ((a.x + b.x) / 2) * view.scale;
  const cy = view.ty + ((a.y + b.y) / 2) * view.scale;
  showEditor(cx, cy, 120, e.label, (val) => {
    snapshot();
    e.label = val.trim();
    render();
  });
}

// =============================================================================
//  Zoom / ajuste
// =============================================================================
svg.addEventListener('wheel', (ev) => {
  ev.preventDefault();
  const factor = ev.deltaY < 0 ? 1.12 : 1 / 1.12;
  const before = toWorld(ev.clientX, ev.clientY);
  view.scale = Math.min(3, Math.max(0.2, view.scale * factor));
  const r = svg.getBoundingClientRect();
  view.tx = ev.clientX - r.left - before.x * view.scale;
  view.ty = ev.clientY - r.top - before.y * view.scale;
  applyView(); positionFloatbar();
}, { passive: false });

function zoomBy(f) {
  const r = svg.getBoundingClientRect();
  const cx = r.width / 2, cy = r.height / 2;
  const before = toWorld(r.left + cx, r.top + cy);
  view.scale = Math.min(3, Math.max(0.2, view.scale * f));
  view.tx = cx - before.x * view.scale;
  view.ty = cy - before.y * view.scale;
  applyView(); positionFloatbar();
}
function fitView() {
  if (!state.nodes.length) { view = { scale: 1, tx: 0, ty: 0 }; applyView(); return; }
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of state.nodes) {
    minX = Math.min(minX, n.x - n.w / 2); maxX = Math.max(maxX, n.x + n.w / 2);
    minY = Math.min(minY, n.y - n.h / 2); maxY = Math.max(maxY, n.y + n.h / 2);
  }
  const r = svg.getBoundingClientRect();
  const pad = 60;
  const sx = (r.width - pad * 2) / (maxX - minX || 1);
  const sy = (r.height - pad * 2) / (maxY - minY || 1);
  view.scale = Math.min(3, Math.max(0.2, Math.min(sx, sy, 1.4)));
  view.tx = (r.width - (maxX + minX) * view.scale) / 2;
  view.ty = (r.height - (maxY + minY) * view.scale) / 2;
  applyView(); positionFloatbar();
}

// =============================================================================
//  Vista previa con mermaid
// =============================================================================
let previewTimer = null, previewSeq = 0;
function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(renderPreview, 220);
}
async function renderPreview() {
  const host = $('#previewHost'), err = $('#previewErr');
  err.textContent = '';
  if (!state.nodes.length) { host.innerHTML = '<div class="empty">Sin nodos todavia.</div>'; return; }
  const my = ++previewSeq;
  try {
    const { svg: out } = await mermaid.render('prev' + my, buildCode());
    if (my !== previewSeq) return;
    host.innerHTML = out;
  } catch (e) {
    if (my !== previewSeq) return;
    err.textContent = 'No se pudo renderizar:\n' + (e && e.message ? e.message : e);
  }
}

// =============================================================================
//  Exportar
// =============================================================================
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 1600);
}
function download(name, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function ensurePreviewSvg() {
  const { svg: out } = await mermaid.render('exp' + Date.now(), buildCode());
  return out;
}

$('#copy').onclick = async () => {
  try { await navigator.clipboard.writeText(buildCode()); toast('Codigo copiado'); }
  catch { toast('No se pudo copiar'); }
};
$('#dlMmd').onclick = () => download('diagrama.mmd', new Blob([buildCode()], { type: 'text/plain' }));
$('#dlSvg').onclick = async () => {
  if (!state.nodes.length) return toast('Nada que exportar');
  try { download('diagrama.svg', new Blob([await ensurePreviewSvg()], { type: 'image/svg+xml' })); toast('SVG exportado'); }
  catch { toast('Error al exportar'); }
};
$('#dlPng').onclick = async () => {
  if (!state.nodes.length) return toast('Nada que exportar');
  try {
    const svgText = await ensurePreviewSvg();
    const img = new Image();
    const blob = new Blob([svgText], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    img.onload = () => {
      const scale = 2;
      const cv = document.createElement('canvas');
      cv.width = img.width * scale; cv.height = img.height * scale;
      const ctx = cv.getContext('2d');
      ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--panel');
      ctx.fillRect(0, 0, cv.width, cv.height);
      ctx.drawImage(img, 0, 0, cv.width, cv.height);
      cv.toBlob((b) => { download('diagrama.png', b); toast('PNG exportado'); });
      URL.revokeObjectURL(url);
    };
    img.onerror = () => toast('Error al exportar PNG');
    img.src = url;
  } catch { toast('Error al exportar'); }
};

// =============================================================================
//  Persistencia local
// =============================================================================
const STORE = 'bstools.mermaid.v1';
function save() {
  try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (_) {}
}
function load() {
  try {
    const raw = localStorage.getItem(STORE);
    if (!raw) return false;
    const s = JSON.parse(raw);
    if (!s.nodes) return false;
    state = Object.assign({ seq: 0 }, s);
    return state.nodes.length > 0;
  } catch { return false; }
}

// =============================================================================
//  Paleta de formas + arrastre desde la barra lateral
// =============================================================================
function shapeThumb(shape) {
  const w = 46, h = 30, m = 4;
  const geo = shapeGeometry(shape, w - m * 2, h - m * 2);
  geo.setAttribute('class', 'sh-fill');
  geo.setAttribute('transform', `translate(${m} ${m})`);
  const s = `<svg viewBox="0 0 ${w} ${h}">${geo.outerHTML}</svg>`;
  return s;
}
function buildPalette() {
  const pal = $('#palette');
  pal.innerHTML = '';
  for (const shape of SHAPE_ORDER) {
    const b = document.createElement('div');
    b.className = 'shape-btn';
    b.draggable = true;
    b.innerHTML = shapeThumb(shape) + `<span>${SHAPES[shape].name}</span>`;
    b.addEventListener('click', () => {
      snapshot();
      const r = svg.getBoundingClientRect();
      const c = toWorld(r.left + r.width / 2 + (Math.random() * 60 - 30), r.top + r.height / 2 + (Math.random() * 60 - 30));
      const n = addNode(shape, Math.round(c.x / 10) * 10, Math.round(c.y / 10) * 10);
      render(); select('node', n.id);
    });
    b.addEventListener('dragstart', (ev) => { ev.dataTransfer.setData('shape', shape); currentShape = shape; });
    pal.appendChild(b);
  }
}
svg.addEventListener('dragover', (ev) => ev.preventDefault());
svg.addEventListener('drop', (ev) => {
  ev.preventDefault();
  const shape = ev.dataTransfer.getData('shape') || currentShape;
  snapshot();
  const c = toWorld(ev.clientX, ev.clientY);
  const n = addNode(shape, Math.round(c.x / 10) * 10, Math.round(c.y / 10) * 10);
  render(); select('node', n.id);
});

// =============================================================================
//  Controles de la interfaz
// =============================================================================
$('#dir').addEventListener('click', (ev) => {
  const b = ev.target.closest('button'); if (!b) return;
  snapshot();
  state.dir = b.dataset.dir;
  syncDirButtons();
  render();
});
function syncDirButtons() {
  $('#dir').querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.dir === state.dir));
}
$('#edgeStyle').addEventListener('click', (ev) => {
  const b = ev.target.closest('button'); if (!b) return;
  currentEdgeStyle = b.dataset.es;
  $('#edgeStyle').querySelectorAll('button').forEach((x) => x.classList.toggle('active', x === b));
  if (selection && selection.type === 'edge') {
    snapshot();
    state.edges.find((e) => e.id === selection.id).style = currentEdgeStyle;
    render();
  }
});

$('#floatbar').addEventListener('click', (ev) => {
  const sw = ev.target.closest('.swatch');
  if (sw && selection && selection.type === 'node') {
    snapshot();
    getNode(selection.id).color = sw.dataset.color;
    render();
  }
});
$('#fbDel').onclick = deleteSelection;
$('#fbEdit').onclick = () => {
  if (!selection) return;
  if (selection.type === 'node') editLabel(getNode(selection.id));
  else editEdgeLabel(state.edges.find((e) => e.id === selection.id));
};

$('#undo').onclick = undo;
$('#redo').onclick = redo;
$('#zoomIn').onclick = () => zoomBy(1.2);
$('#zoomOut').onclick = () => zoomBy(1 / 1.2);
$('#zoomFit').onclick = fitView;
$('#clear').onclick = () => {
  if (!state.nodes.length && !state.edges.length) return;
  if (!confirm('Vaciar el lienzo? Se perdera el diagrama actual.')) return;
  snapshot();
  state.nodes = []; state.edges = []; selection = null;
  render();
};

// tabs codigo / preview
$('#tabCode').onclick = () => {
  $('#tabCode').classList.add('active'); $('#tabPreview').classList.remove('active');
  $('#codeView').classList.remove('hide'); $('#previewView').classList.remove('show');
};
$('#tabPreview').onclick = () => {
  $('#tabPreview').classList.add('active'); $('#tabCode').classList.remove('active');
  $('#codeView').classList.add('hide'); $('#previewView').classList.add('show');
  renderPreview();
};

// tema
$('#theme').onclick = () => {
  const light = document.documentElement.classList.toggle('light');
  localStorage.setItem('bstools.mermaid.theme', light ? 'light' : 'dark');
  mermaid.initialize({ startOnLoad: false, theme: light ? 'default' : 'dark', securityLevel: 'loose' });
  if ($('#previewView').classList.contains('show')) renderPreview();
};

// teclado
window.addEventListener('keydown', (ev) => {
  if (editing) return;
  if (ev.key === 'Delete' || ev.key === 'Backspace') {
    if (document.activeElement === editor) return;
    if (selection) { ev.preventDefault(); deleteSelection(); }
  } else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'z') {
    ev.preventDefault(); ev.shiftKey ? redo() : undo();
  } else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'y') {
    ev.preventDefault(); redo();
  } else if (ev.key === 'Escape') {
    select(null);
  }
});
window.addEventListener('resize', positionFloatbar);

// =============================================================================
//  Arranque
// =============================================================================
function seedExample() {
  const a = addNode('stadium', 0, -120, 'Inicio');
  const b = addNode('rect', 0, 0, 'Procesar datos');
  const c = addNode('diamond', 0, 130, 'Correcto?');
  const d = addNode('rect', 220, 130, 'Reintentar');
  const e = addNode('stadium', 0, 270, 'Fin');
  currentEdgeStyle = 'arrow';
  addEdge(a.id, b.id); addEdge(b.id, c.id);
  const e1 = addEdge(c.id, e.id); e1.label = 'Si';
  const e2 = addEdge(c.id, d.id); e2.label = 'No';
  addEdge(d.id, b.id);
}

(function init() {
  const savedTheme = localStorage.getItem('bstools.mermaid.theme');
  const light = savedTheme === 'light';
  if (light) document.documentElement.classList.add('light');
  mermaid.initialize({ startOnLoad: false, theme: light ? 'default' : 'dark', securityLevel: 'loose' });

  buildPalette();
  if (!load()) seedExample();
  syncDirButtons();
  render();
  fitView();
})();
