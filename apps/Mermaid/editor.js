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

// conectores mermaid <-> nuestro estilo de flecha
const CONN_STYLE = { '-->': 'arrow', '---': 'open', '-.->': 'dotted', '==>': 'thick' };

const SVGNS = 'http://www.w3.org/2000/svg';
const NODE_H = 52, MIN_W = 96, PAD_X = 26;
const PAD_G = 24, HEAD_G = 26;   // margen y cabecera de la caja de un grupo

// --- estado ------------------------------------------------------------------
// nodes:  { id, shape, x, y, label, w, h, parent?, colors?, styleExtra? }
// edges:  { id, from, to, label, style }
// groups: { id, label, parent?, dir?, anchor?, colors?, styleExtra? }
//   anchor existe si y solo si el grupo no tiene descendientes (D1, ADR-0004).
let state = { nodes: [], edges: [], dir: 'TD', seq: 0, groups: [] };
let view = { scale: 1, tx: 0, ty: 0 };
let currentShape = 'rect';
let currentEdgeStyle = 'arrow';
let selection = null;             // {type:'node'|'edge'|'group', id} | {type:'multi', ids:[]}
let undoStack = [], redoStack = [];

const $ = (s) => document.querySelector(s);
const svg = $('#canvas');
const gGroups = $('#groups'), gNodes = $('#nodes'), gEdges = $('#edges');
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
//  Modelo: nodos, aristas, grupos
// =============================================================================
function nodeId() { return 'n' + (++state.seq); }
function getNode(id) { return state.nodes.find((n) => n.id === id); }
function getGroup(id) { return state.groups.find((g) => g.id === id); }

function addNode(shape, x, y, label) {
  const id = nodeId();
  const n = { id, shape, x, y, label: label || SHAPES[shape].name };
  sizeNode(n);
  state.nodes.push(n);
  return n;
}
function sizeNode(n) {
  const w = Math.max(MIN_W, Math.round(measureLabel(n.label) + PAD_X * 2));
  n.w = (n.shape === 'circle') ? Math.max(w, NODE_H + 16) : w;
  n.h = (n.shape === 'circle') ? n.w : NODE_H;
}

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
  } else if (selection.type === 'edge') {
    state.edges = state.edges.filter((e) => e.id !== selection.id);
  } else if (selection.type === 'group') {
    // Borrar un grupo borra solo la caja: los hijos sobreviven y pierden `parent` (D2).
    const gid = selection.id;
    state.groups = state.groups.filter((g) => g.id !== gid);
    for (const n of state.nodes) if (n.parent === gid) delete n.parent;
    for (const g of state.groups) if (g.parent === gid) delete g.parent;
  } else if (selection.type === 'multi') {
    const ids = new Set(selection.ids);
    state.nodes = state.nodes.filter((n) => !ids.has(n.id));
    state.edges = state.edges.filter((e) => !ids.has(e.from) && !ids.has(e.to));
  }
  selection = null;
  state = normalizeState(state);
  render();
}

// =============================================================================
//  Serializacion del estado (unica) y saneado (unica puerta de entrada, D6)
// =============================================================================
function serializeState() {
  return JSON.stringify({ nodes: state.nodes, edges: state.edges, dir: state.dir, seq: state.seq, groups: state.groups });
}

const HEX_RE = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
function normHex(hex) {
  let h = String(hex).replace('#', '').toLowerCase();
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  return '#' + h;
}
// Sanea declaraciones libres a pares "clave:valor" seguros (R7): nunca deja pasar
// texto que pueda cerrar el atributo/estilo en el SVG o el codigo mermaid.
function saneStyleExtra(s) {
  if (!s) return '';
  const parts = String(s).split(',').map((p) => p.trim()).filter(Boolean);
  const kept = parts.filter((p) => /^[A-Za-z-]+:[^;<>"']+$/.test(p));
  return kept.join(',');
}
function sanitizeColors(colors) {
  if (!colors || typeof colors !== 'object') return undefined;
  const out = {};
  if (colors.fill && HEX_RE.test(colors.fill)) out.fill = normHex(colors.fill);
  if (colors.stroke && HEX_RE.test(colors.stroke)) out.stroke = normHex(colors.stroke);
  if (colors.text && HEX_RE.test(colors.text)) out.text = normHex(colors.text);
  if (colors.strokeWidth && /^[0-9]+(\.[0-9]+)?(px|em|rem)?$/.test(String(colors.strokeWidth).trim())) {
    out.strokeWidth = String(colors.strokeWidth).trim();
  }
  return Object.keys(out).length ? out : undefined;
}
// Migracion perezosa D5 (color de paleta -> colors hex) + saneado de colors/styleExtra.
function normalizeElement(el) {
  if (!el.colors && el.color && el.color !== 'default' && NODE_COLORS[el.color]) {
    const [stroke, fill] = NODE_COLORS[el.color];
    el.colors = { fill: normHex(fill), stroke: normHex(stroke), strokeWidth: '2px' };
  }
  delete el.color;
  const sane = sanitizeColors(el.colors);
  if (sane) el.colors = sane; else delete el.colors;
  const se = saneStyleExtra(el.styleExtra);
  if (se) el.styleExtra = se; else delete el.styleExtra;
  return el;
}

// Unica puerta de entrada al estado (load, setStateFrom, restore): idempotente,
// rellena groups:[], migra colores, repara parent colgantes/ciclicos y mantiene
// el invariante de `anchor` (D6).
function normalizeState(s) {
  s = s || {};
  const rawNodes = Array.isArray(s.nodes) ? s.nodes : [];
  const rawGroups = Array.isArray(s.groups) ? s.groups : [];

  const nodes = rawNodes.filter((n) => n && n.id).map((n) => {
    const nn = { id: n.id, shape: SHAPES[n.shape] ? n.shape : 'rect', label: n.label != null ? n.label : n.id, x: +n.x || 0, y: +n.y || 0 };
    if (n.w) nn.w = n.w;
    if (n.h) nn.h = n.h;
    if (n.parent) nn.parent = n.parent;
    if (n.colors) nn.colors = n.colors;
    if (n.color) nn.color = n.color;
    if (n.styleExtra) nn.styleExtra = n.styleExtra;
    normalizeElement(nn);
    if (!nn.w || !nn.h) sizeNode(nn);
    return nn;
  });
  const nodeIds = new Set(nodes.map((n) => n.id));

  let groups = rawGroups.filter((g) => g && g.id && !nodeIds.has(g.id)).map((g) => {
    const gg = { id: g.id, label: g.label != null ? g.label : g.id };
    if (g.parent) gg.parent = g.parent;
    if (g.dir) gg.dir = g.dir;
    if (g.anchor && typeof g.anchor.x === 'number' && typeof g.anchor.y === 'number') gg.anchor = { x: g.anchor.x, y: g.anchor.y };
    if (g.colors) gg.colors = g.colors;
    if (g.styleExtra) gg.styleExtra = g.styleExtra;
    normalizeElement(gg);
    return gg;
  });
  const groupIds = new Set(groups.map((g) => g.id));

  for (const n of nodes) if (n.parent && !groupIds.has(n.parent)) delete n.parent;
  for (const g of groups) if (g.parent && (g.parent === g.id || !groupIds.has(g.parent))) delete g.parent;

  // Romper ciclos de parent entre grupos.
  const gmap = new Map(groups.map((g) => [g.id, g]));
  for (const g of groups) {
    const seen = new Set();
    let cur = g;
    while (cur && cur.parent) {
      if (seen.has(cur.id)) { delete cur.parent; break; }
      seen.add(cur.id);
      cur = gmap.get(cur.parent);
    }
  }

  // anchor <=> sin descendientes (D1). Un grupo "tiene descendientes" en cuanto
  // algo (nodo o grupo) le apunta como parent, sea directo o no: ya basta con un
  // hijo inmediato, no hace falta mirar mas alla.
  const hasDesc = new Set();
  for (const n of nodes) if (n.parent) hasDesc.add(n.parent);
  for (const g of groups) if (g.parent) hasDesc.add(g.parent);
  for (const g of groups) {
    if (hasDesc.has(g.id)) delete g.anchor;
    else if (!g.anchor) g.anchor = { x: 0, y: 0 };
  }

  const edges = Array.isArray(s.edges) ? s.edges.filter((e) => e && e.from && e.to).map((e) => ({
    id: e.id || ('e' + Math.random().toString(36).slice(2)),
    from: e.from, to: e.to, label: e.label || '',
    style: EDGE_STYLES[e.style] ? e.style : 'arrow',
  })) : [];

  return { dir: s.dir || 'TD', seq: s.seq || 0, nodes, edges, groups };
}

// =============================================================================
//  Undo / redo
// =============================================================================
function snapshot() {
  undoStack.push(serializeState());
  if (undoStack.length > 100) undoStack.shift();
  redoStack = [];
  refreshUndoButtons();
}
function restore(json) {
  state = normalizeState(JSON.parse(json));
  selection = null;
  syncDirButtons();
  render();
}
function undo() {
  if (!undoStack.length) return;
  redoStack.push(serializeState());
  restore(undoStack.pop());
  refreshUndoButtons();
}
function redo() {
  if (!redoStack.length) return;
  undoStack.push(serializeState());
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

// --- auto-contraste del texto sobre un relleno solido (WCAG 2.x) -------------
// Formula oficial de luminancia relativa: linealiza cada canal y pondera segun
// la sensibilidad del ojo (verde > rojo > azul).
function relLuminance(r, g, b) {
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
// admite '#rgb' y '#rrggbb'; devuelve [r,g,b] normalizados a 0..1.
function parseHex(hex) {
  let h = String(hex).replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  return [parseInt(h.slice(0, 2), 16) / 255, parseInt(h.slice(2, 4), 16) / 255, parseInt(h.slice(4, 6), 16) / 255];
}
// ratio de contraste WCAG entre dos luminancias relativas (siempre >= 1).
function contrastRatio(l1, l2) {
  const hi = Math.max(l1, l2), lo = Math.min(l1, l2);
  return (hi + 0.05) / (lo + 0.05);
}
const TEXT_DARK = '#111827', TEXT_LIGHT = '#f8fafc';
const TEXT_DARK_L = relLuminance(...parseHex(TEXT_DARK));
const TEXT_LIGHT_L = relLuminance(...parseHex(TEXT_LIGHT));
// Elige el candidato (oscuro o claro) con mejor ratio de contraste real contra
// el relleno dado, no un umbral de luminancia a ojo.
function textOn(hexFill) {
  const L = relLuminance(...parseHex(hexFill));
  return contrastRatio(L, TEXT_DARK_L) >= contrastRatio(L, TEXT_LIGHT_L) ? TEXT_DARK : TEXT_LIGHT;
}

function isNodeSelected(id) {
  if (!selection) return false;
  if (selection.type === 'node') return selection.id === id;
  if (selection.type === 'multi') return selection.ids.includes(id);
  return false;
}

function drawNode(n) {
  const g = document.createElementNS(SVGNS, 'g');
  g.setAttribute('class', 'node' + (isNodeSelected(n.id) ? ' sel' : ''));
  g.setAttribute('transform', `translate(${n.x - n.w / 2} ${n.y - n.h / 2})`);
  g.dataset.id = n.id;

  const shape = shapeGeometry(n.shape, n.w, n.h);
  let labelFill = null;
  if (n.colors && n.colors.fill) {
    shape.style.fill = n.colors.fill;
    if (n.colors.stroke) shape.style.stroke = n.colors.stroke;
    labelFill = n.colors.text || textOn(n.colors.fill);
  } else if (n.colors && n.colors.stroke) {
    shape.style.stroke = n.colors.stroke;
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
  if (labelFill) t.style.fill = labelFill;
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
//  Grupos (subgraph): caja derivada de los hijos, nunca persistida (D1)
// =============================================================================
// Nodos que pertenecen a `gid` o a cualquier grupo anidado dentro de `gid`.
function groupDescendantNodes(gid) {
  const out = [];
  for (const n of state.nodes) if (n.parent === gid) out.push(n);
  for (const cg of state.groups) if (cg.parent === gid) out.push(...groupDescendantNodes(cg.id));
  return out;
}
function allDescendantGroups(gid) {
  const out = [];
  for (const cg of state.groups.filter((x) => x.parent === gid)) {
    out.push(cg);
    out.push(...allDescendantGroups(cg.id));
  }
  return out;
}
// bbox(descendientes) + PAD_G + cabecera. Sin hijos: caja fija en `anchor`.
function groupBox(g) {
  const nodes = groupDescendantNodes(g.id);
  const childGroups = state.groups.filter((x) => x.parent === g.id);
  if (!nodes.length && !childGroups.length) {
    const a = g.anchor || { x: 0, y: 0 };
    return { x: a.x - 90, y: a.y - 40, w: 180, h: 80 };
  }
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of nodes) {
    minX = Math.min(minX, n.x - n.w / 2); maxX = Math.max(maxX, n.x + n.w / 2);
    minY = Math.min(minY, n.y - n.h / 2); maxY = Math.max(maxY, n.y + n.h / 2);
  }
  for (const cg of childGroups) {
    const b = groupBox(cg);
    minX = Math.min(minX, b.x); maxX = Math.max(maxX, b.x + b.w);
    minY = Math.min(minY, b.y); maxY = Math.max(maxY, b.y + b.h);
  }
  return {
    x: minX - PAD_G, y: minY - PAD_G - HEAD_G,
    w: (maxX - minX) + PAD_G * 2, h: (maxY - minY) + PAD_G * 2 + HEAD_G,
  };
}

function drawGroup(g) {
  const box = groupBox(g);
  const isSel = selection && selection.type === 'group' && selection.id === g.id;
  const gEl = document.createElementNS(SVGNS, 'g');
  gEl.setAttribute('class', 'group' + (isSel ? ' sel' : ''));
  gEl.dataset.id = g.id;

  const rect = document.createElementNS(SVGNS, 'rect');
  setAttrs(rect, { x: box.x, y: box.y, width: box.w, height: box.h, rx: 10 });
  rect.setAttribute('class', 'group-rect');
  if (g.colors && g.colors.fill) rect.style.fill = g.colors.fill;
  if (g.colors && g.colors.stroke) rect.style.stroke = g.colors.stroke;
  gEl.appendChild(rect);

  const head = document.createElementNS(SVGNS, 'rect');
  setAttrs(head, { x: box.x, y: box.y, width: box.w, height: HEAD_G, rx: 10 });
  head.setAttribute('class', 'group-head');
  if (g.colors && g.colors.fill) head.style.fill = g.colors.fill;
  gEl.appendChild(head);

  const t = document.createElementNS(SVGNS, 'text');
  t.setAttribute('class', 'group-label');
  setAttrs(t, { x: box.x + 10, y: box.y + HEAD_G / 2 });
  if (g.colors) t.style.fill = g.colors.text || (g.colors.fill ? textOn(g.colors.fill) : '');
  t.textContent = g.label;
  gEl.appendChild(t);

  gGroups.appendChild(gEl);
}
// raiz -> hojas, para que el anidado quede dibujado encima del padre.
function drawGroupTree(g) {
  drawGroup(g);
  for (const cg of state.groups.filter((x) => x.parent === g.id)) drawGroupTree(cg);
}
// Hit-test SOLO en cabecera y borde: el interior sigue siendo paneo / clic a nodos.
function groupAt(clientX, clientY) {
  const w = toWorld(clientX, clientY);
  for (let i = state.groups.length - 1; i >= 0; i--) {
    const g = state.groups[i];
    const b = groupBox(g);
    const inBox = w.x >= b.x && w.x <= b.x + b.w && w.y >= b.y && w.y <= b.y + b.h;
    if (!inBox) continue;
    const inHeader = w.y <= b.y + HEAD_G;
    const BORDER = 8;
    const nearBorder = (w.x - b.x <= BORDER) || (b.x + b.w - w.x <= BORDER) ||
                        (w.y - b.y <= BORDER) || (b.y + b.h - w.y <= BORDER);
    if (inHeader || nearBorder) return g;
  }
  return null;
}

// =============================================================================
//  Render completo
// =============================================================================
function render() {
  gGroups.textContent = '';
  gNodes.textContent = '';
  gEdges.textContent = '';
  for (const g of state.groups.filter((x) => !x.parent)) drawGroupTree(g);
  state.edges.forEach(drawEdge);
  state.nodes.forEach(drawNode);
  syncGroupButton();
  $('#hint').style.display = (state.nodes.length || state.groups.length) ? 'none' : '';
  positionFloatbar();
  refreshCode();
  save();
}

// =============================================================================
//  Generacion del codigo mermaid
// =============================================================================
function esc(s) { return String(s).replace(/"/g, '#quot;').replace(/\n/g, '<br>'); }

// Cadena canonica de declaraciones, orden fijo (fill, stroke, stroke-width, color,
// styleExtra) para que el ida y vuelta sea byte-idempotente (A2).
function declString(colors, styleExtra) {
  const c = colors || {};
  const parts = [];
  if (c.fill) parts.push('fill:' + normHex(c.fill));
  if (c.stroke) parts.push('stroke:' + normHex(c.stroke));
  if (c.strokeWidth) parts.push('stroke-width:' + c.strokeWidth);
  if (c.fill) parts.push('color:' + normHex(c.text || textOn(c.fill)));
  if (styleExtra) parts.push(styleExtra);
  return parts.join(',');
}
// FNV-1a de 32 bits, en hex de 8 digitos.
function fnv1a32(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}
// Nombre de clase determinista y derivado del contenido (§2bis, ADR-0004): nunca
// de un contador de sesion, para que dos grupos con los mismos colores compartan
// classDef y el nombre sea estable ante insercion/borrado (A2b).
function classNameFor(colors, styleExtra) {
  const c = colors || {};
  const part = (h) => h ? normHex(h).slice(1) : 'none';
  const effText = c.text || (c.fill ? textOn(c.fill) : null);
  let name = `bs_${part(c.fill)}_${part(c.stroke)}_${part(effText)}`;
  if (styleExtra) name += '_x' + fnv1a32(styleExtra);
  return name;
}

function groupChildrenNodes(gid) { return state.nodes.filter((n) => (n.parent || null) === gid); }
function groupChildrenGroups(gid) { return state.groups.filter((g) => (g.parent || null) === gid); }

function emitGroup(g, indent, lines, emitted) {
  const ind = '    '.repeat(indent);
  lines.push(`${ind}subgraph ${g.id}["${esc(g.label)}"]`);
  if (g.dir) lines.push(`${ind}    direction ${g.dir}`);
  for (const n of groupChildrenNodes(g.id)) {
    lines.push(`${ind}    ` + SHAPES[n.shape].wrap(n.id, esc(n.label)));
    emitted.add(n.id);
  }
  for (const sub of groupChildrenGroups(g.id)) emitGroup(sub, indent + 1, lines, emitted);
  lines.push(`${ind}end`);
}

function buildCode() {
  const lines = [`flowchart ${state.dir}`];
  const emitted = new Set();

  for (const n of state.nodes.filter((x) => !x.parent)) {
    lines.push('    ' + SHAPES[n.shape].wrap(n.id, esc(n.label)));
    emitted.add(n.id);
  }
  for (const g of state.groups.filter((x) => !x.parent)) emitGroup(g, 1, lines, emitted);
  // Red de seguridad: cada nodo se declara exactamente una vez, aunque su grupo
  // este mal saneado (defensivo; normalizeState ya no deberia dejar este caso).
  for (const n of state.nodes) {
    if (!emitted.has(n.id)) {
      lines.push('    ' + SHAPES[n.shape].wrap(n.id, esc(n.label)));
      emitted.add(n.id);
    }
  }

  for (const e of state.edges) {
    const st = EDGE_STYLES[e.style];
    const conn = e.label ? st.label(esc(e.label)) : st.open;
    lines.push(`    ${e.from} ${conn} ${e.to}`);
  }

  // ---- bloque de estilos: (a) style de nodos, (b) classDef de grupos
  //      (alfabetico), (c) class de grupos (mismo orden alfabetico) ----
  const styleLines = [];
  for (const n of state.nodes) {
    const decl = declString(n.colors, n.styleExtra);
    if (decl) styleLines.push(`style ${n.id} ${decl}`);
  }
  const classDefs = new Map();    // className -> declaracion
  const classMembers = new Map(); // className -> [ids de grupo] en orden de state.groups
  for (const g of state.groups) {
    const decl = declString(g.colors, g.styleExtra);
    if (!decl) continue;
    const cn = classNameFor(g.colors, g.styleExtra);
    if (!classDefs.has(cn)) classDefs.set(cn, decl);
    if (!classMembers.has(cn)) classMembers.set(cn, []);
    classMembers.get(cn).push(g.id);
  }
  const classNames = [...classDefs.keys()].sort();
  const classDefLines = classNames.map((cn) => `classDef ${cn} ${classDefs.get(cn)}`);
  const classLines = classNames.map((cn) => `class ${classMembers.get(cn).join(',')} ${cn}`);

  const styleBlock = [...styleLines, ...classDefLines, ...classLines];
  if (styleBlock.length) {
    lines.push('');
    for (const l of styleBlock) lines.push('    ' + l);
  }
  return lines.join('\n');
}

// Vuelca el codigo al panel derecho (textarea + capa resaltada). Se omite
// mientras el propio usuario esta editando el texto, para no pisarle el cursor.
let suppressCodeWrite = false;
function refreshCode() {
  if ($('#previewView').classList.contains('show')) schedulePreview();
  if (suppressCodeWrite) return;
  const code = buildCode();
  const ta = $('#codeInput');
  if (ta) { ta.value = code; updateHighlight(code); }
}

function updateHighlight(text) {
  const hl = $('#codeHl');
  if (hl) hl.innerHTML = highlight(text) + '\n';
}

function highlight(code) {
  return code.split('\n').map((line) => {
    let h = line
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    h = h.replace(/^(\s*)(flowchart|graph|style|subgraph|end|direction|classDef|class)\b/, (m, sp, kw) => `${sp}<span class="tok-kw">${kw}</span>`);
    h = h.replace(/(--&gt;|---|-\.-&gt;|==&gt;)/g, '<span class="tok-arr">$1</span>');
    h = h.replace(/&quot;([^&]*)&quot;|#quot;/g, (m) => `<span class="tok-str">${m}</span>`);
    return h;
  }).join('\n');
}

// =============================================================================
//  Parseo del codigo mermaid  (camino inverso: texto -> nodos, flechas y grupos)
//
//  Cubre el subconjunto de `flowchart` que este editor genera: cabecera,
//  definiciones de nodo con las 8 formas, flechas con etiqueta opcional (forma
//  con tuberia `|"..."|`), cadenas A --> B --> C, `subgraph ... end` anidados,
//  `style`/`classDef`/`class` y direccion interna de grupo. No pretende entender
//  Mermaid arbitrario; si algo no encaja, devuelve un error y el lienzo se queda
//  como estaba. Fuera de alcance (declarado, ADR-0004 §2bis): `A:::miClase`,
//  `linkStyle`, `click`, `%%`.
// =============================================================================
function unquoteLabel(s) {
  s = s.trim();
  if (s.length >= 2 && s[0] === '"' && s[s.length - 1] === '"') s = s.slice(1, -1);
  return s
    .replace(/#quot;/g, '"')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&amp;/g, '&');
}

// Pasa las flechas con texto EN LINEA (estilo `A -. txt .-> B`, `-- txt -->`,
// `== txt ==>`) a la forma con tuberia (`-.->|"txt"|`, etc.), que es la que sabe
// dividir el analizador. No toca las flechas compactas (`-->`, `-.->`...).
function normalizeLinks(line) {
  return line
    .replace(/-\.\s*"?([^"|]*?)"?\s*\.->/g, (m, t) => `-.->|"${t.trim()}"|`)
    .replace(/==\s*"?([^"|=]*?)"?\s*==>/g, (m, t) => `==>|"${t.trim()}"|`)
    .replace(/--\s+"?([^"|>]*?)"?\s+-->/g, (m, t) => `-->|"${t.trim()}"|`);
}

// Divide un extremo de flecha por `&` (multidestino de Mermaid: `B & C`),
// respetando corchetes, parentesis, llaves y comillas.
function splitAmp(str) {
  const out = [];
  let depth = 0, q = false, cur = '';
  for (const ch of str) {
    if (ch === '"') q = !q;
    if (!q) {
      if (ch === '[' || ch === '(' || ch === '{') depth++;
      else if (ch === ']' || ch === ')' || ch === '}') depth--;
      else if (ch === '&' && depth === 0) { out.push(cur); cur = ''; continue; }
    }
    cur += ch;
  }
  out.push(cur);
  return out.map((s) => s.trim()).filter(Boolean);
}

// A partir del texto que sigue al id de un nodo (p.ej. `["Etiqueta"]`) deduce
// forma y etiqueta.
function parseShape(rest) {
  const tests = [
    [/^\(\[([\s\S]*)\]\)$/, 'stadium'],
    [/^\[\[([\s\S]*)\]\]$/, 'subroutine'],
    [/^\[\(([\s\S]*)\)\]$/, 'cylinder'],
    [/^\(\(([\s\S]*)\)\)$/, 'circle'],
    [/^\{\{([\s\S]*)\}\}$/, 'hexagon'],
    [/^\[([\s\S]*)\]$/, 'rect'],
    [/^\(([\s\S]*)\)$/, 'round'],
    [/^\{([\s\S]*)\}$/, 'diamond'],
  ];
  for (const [re, shape] of tests) {
    const m = rest.match(re);
    if (m) return { shape, label: unquoteLabel(m[1]) };
  }
  return null;
}

// `style`/`classDef` comparten el mismo trocedaor de declaraciones. Los hex
// invalidos y las claves no reconocidas se descartan; el resto va a styleExtra
// saneado a pares `[A-Za-z-]+:[^;<>"']+` (R7).
function parseStyleDecl(str) {
  const parts = String(str).split(',').map((p) => p.trim()).filter(Boolean);
  const out = {};
  const extra = [];
  for (const p of parts) {
    const km = p.match(/^([A-Za-z-]+):(.*)$/);
    if (!km) continue;
    const key = km[1].toLowerCase();
    const val = km[2].trim();
    const hexOk = HEX_RE.test(val);
    if (key === 'fill' && hexOk) { out.fill = normHex(val); continue; }
    if (key === 'stroke' && hexOk) { out.stroke = normHex(val); continue; }
    if (key === 'color' && hexOk) { out.text = normHex(val); continue; }
    if (key === 'stroke-width') { out.strokeWidth = val; continue; }
    if (/^[A-Za-z-]+:[^;<>"']+$/.test(p)) extra.push(p);
  }
  out.styleExtra = extra.join(',');
  return out;
}

function parseCode(text) {
  const lines = text.split(/\r?\n/);
  let dir = 'TD';
  let started = false;
  const nodeMap = new Map();
  const order = [];
  const edges = [];
  const groupMap = new Map();
  const groupOrder = [];
  const stack = [];   // pila de ids de grupo abiertos
  let gseq = 0;
  const nextAutoGroupId = () => {
    let id;
    do { id = 'g' + (++gseq); } while (nodeMap.has(id) || groupMap.has(id));
    return id;
  };

  const directStyles = new Map();  // id -> decl
  const classDefs = new Map();     // className -> decl
  const classAssign = new Map();   // id -> className

  const ensureNode = (token) => {
    const t = token.trim();
    const m = t.match(/^([A-Za-z_][\w-]*)/);
    if (!m) throw new Error('Nodo no valido: "' + t + '"');
    const id = m[1];
    if (groupMap.has(id)) throw new Error(`El grupo ${id} usa el mismo id que un nodo`);
    const rest = t.slice(id.length).trim();
    let node = nodeMap.get(id);
    if (!node) {
      node = { id, shape: 'rect', label: id };
      if (stack.length) node.parent = stack[stack.length - 1];
      nodeMap.set(id, node); order.push(id);
    }
    if (rest) {
      const sh = parseShape(rest);
      if (!sh) throw new Error('Forma no reconocida en: "' + t + '"');
      node.shape = sh.shape;
      node.label = sh.label;
    }
    return id;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    if (!started) {
      const fm = line.match(/^(?:flowchart|graph)\s+(TD|TB|LR|RL|BT)\b/i);
      if (!fm) throw new Error('La primera linea debe ser "flowchart TD" (o LR / BT / RL).');
      dir = fm[1].toUpperCase();
      if (dir === 'TB') dir = 'TD';
      started = true;
      continue;
    }

    const sgm = line.match(/^subgraph\s+(.*)$/i);
    if (sgm) {
      const rest = sgm[1].trim();
      let gid, glabel;
      let m2 = rest.match(/^([A-Za-z_][\w-]*)\s*\[\s*"([\s\S]*)"\s*\]$/);
      if (!m2) m2 = rest.match(/^([A-Za-z_][\w-]*)\s*\[\s*([^\]]*)\]$/);
      if (m2) { gid = m2[1]; glabel = unquoteLabel(m2[2]); }
      else if (/^[A-Za-z_][\w-]*$/.test(rest)) { gid = rest; glabel = rest; }
      else { glabel = unquoteLabel(rest); gid = nextAutoGroupId(); }
      if (nodeMap.has(gid)) throw new Error(`El grupo ${gid} usa el mismo id que un nodo`);
      let g = groupMap.get(gid);
      if (!g) {
        g = { id: gid, label: glabel };
        if (stack.length) g.parent = stack[stack.length - 1];
        groupMap.set(gid, g); groupOrder.push(gid);
      } else {
        g.label = glabel;
      }
      stack.push(gid);
      continue;
    }
    if (/^end$/i.test(line)) {
      if (!stack.length) throw new Error('Se encontro "end" sin un "subgraph" abierto.');
      stack.pop();
      continue;
    }
    const dirm = line.match(/^direction\s+(TD|TB|LR|RL|BT)\b/i);
    if (dirm) {
      if (stack.length) {
        let d = dirm[1].toUpperCase(); if (d === 'TB') d = 'TD';
        groupMap.get(stack[stack.length - 1]).dir = d;
      }
      continue;
    }
    const cdm = line.match(/^classDef\s+([A-Za-z_][\w-]*)\s+(.+)$/i);
    if (cdm) { classDefs.set(cdm[1], parseStyleDecl(cdm[2])); continue; }

    const clm = line.match(/^class\s+(.+)\s+([A-Za-z_][\w-]*)\s*$/i);
    if (clm) {
      const ids = clm[1].split(',').map((s) => s.trim()).filter(Boolean);
      for (const id of ids) classAssign.set(id, clm[2]);
      continue;
    }
    const sm = line.match(/^style\s+([A-Za-z_][\w-]*)\s+(.+)$/i);
    if (sm) { directStyles.set(sm[1], parseStyleDecl(sm[2])); continue; }

    // linea de flecha(s) o nodo suelto
    const norm = normalizeLinks(line);
    const parts = norm.split(/(-\.->|==>|-->|---)/);
    if (parts.length >= 3) {
      let leftTok = parts[0];
      for (let k = 1; k < parts.length; k += 2) {
        const style = CONN_STYLE[parts[k]];
        let right = parts[k + 1] || '';
        let label = '';
        const lm = right.match(/^\s*\|\s*"?([^"|]*)"?\s*\|/);
        if (lm) { label = unquoteLabel(lm[1]); right = right.slice(lm[0].length); }
        const froms = splitAmp(leftTok).map(ensureNode);
        const tos = splitAmp(right).map(ensureNode);
        for (const f of froms) for (const t of tos) edges.push({ from: f, to: t, label, style });
        leftTok = right;
      }
    } else {
      ensureNode(line);
    }
  }

  if (!started) throw new Error('Falta la cabecera "flowchart TD".');
  if (stack.length) throw new Error('Falta cerrar "end" para: ' + stack[stack.length - 1]);

  // Precedencia: si un id recibe `class` y `style`, gana `style`.
  const applyDecl = (id, target) => {
    let decl = directStyles.get(id);
    if (!decl) {
      const cn = classAssign.get(id);
      if (cn && classDefs.has(cn)) decl = classDefs.get(cn);
    }
    if (!decl) return;
    const colors = {};
    if (decl.fill) colors.fill = decl.fill;
    if (decl.stroke) colors.stroke = decl.stroke;
    if (decl.text) colors.text = decl.text;
    if (decl.strokeWidth) colors.strokeWidth = decl.strokeWidth;
    if (Object.keys(colors).length) target.colors = colors;
    if (decl.styleExtra) target.styleExtra = decl.styleExtra;
  };
  for (const [id, n] of nodeMap) applyDecl(id, n);
  for (const [id, g] of groupMap) applyDecl(id, g);

  // secuencia para futuros ids automaticos (considera tambien los ids de grupo)
  let seq = 0;
  for (const id of order) { const d = id.match(/(\d+)$/); if (d) seq = Math.max(seq, +d[1]); }
  for (const id of groupOrder) { const d = id.match(/(\d+)$/); if (d) seq = Math.max(seq, +d[1]); }

  return {
    ok: true,
    data: {
      dir, seq,
      nodes: order.map((id) => nodeMap.get(id)),
      edges,
      groups: groupOrder.map((id) => groupMap.get(id)),
    },
  };
}

// Coloca en el lienzo el resultado de un parseo, conservando la posicion de los
// nodos que ya existian, el anchor de los grupos que ya existian, y situando lo
// nuevo cerca de sus vecinos.
function applyParsed(data) {
  const prevNodePos = new Map(state.nodes.map((n) => [n.id, { x: n.x, y: n.y }]));
  const prevGroupAnchor = new Map(state.groups.map((g) => [g.id, g.anchor]));

  const nodes = data.nodes.map((n) => {
    const p = prevNodePos.get(n.id);
    const nn = { id: n.id, shape: n.shape, label: n.label, x: p ? p.x : 0, y: p ? p.y : 0 };
    if (n.parent) nn.parent = n.parent;
    if (n.colors) nn.colors = n.colors;
    if (n.styleExtra) nn.styleExtra = n.styleExtra;
    sizeNode(nn);
    nn._new = !p;
    return nn;
  });
  placeNodes(nodes, data.edges, data.groups || [], prevNodePos.size === 0);
  nodes.forEach((n) => delete n._new);

  let gcascade = 0;
  const groups = (data.groups || []).map((g) => {
    const gg = { id: g.id, label: g.label };
    if (g.parent) gg.parent = g.parent;
    if (g.dir) gg.dir = g.dir;
    if (g.colors) gg.colors = g.colors;
    if (g.styleExtra) gg.styleExtra = g.styleExtra;
    const oldAnchor = prevGroupAnchor.get(g.id);
    if (oldAnchor) gg.anchor = oldAnchor;
    else { gg.anchor = { x: 40 * gcascade, y: -80 - 40 * gcascade }; gcascade++; }
    return gg;
  });

  state = normalizeState({
    dir: data.dir, seq: data.seq + data.edges.length + 1, nodes,
    edges: data.edges.map((e, i) => ({ id: 'e' + (data.seq + 1 + i), from: e.from, to: e.to, label: e.label, style: e.style })),
    groups,
  });

  if (selection) {
    const still = selection.type === 'node' ? state.nodes.some((n) => n.id === selection.id)
      : selection.type === 'group' ? state.groups.some((g) => g.id === selection.id)
      : selection.type === 'multi' ? true
      : state.edges.some((e) => e.id === selection.id);
    if (!still) selection = null;
  }
  syncDirButtons();
  render();
}

function placeNodes(nodes, edges, groups, fresh) {
  const isNew = nodes.filter((n) => n._new);
  if (!isNew.length) return;
  if (fresh) { layeredLayout(nodes, edges, state.dir, groups); return; }

  const byId = new Map(nodes.map((n) => [n.id, n]));
  let cascade = 1;
  for (const n of isNew) {
    const nb = [];
    for (const e of edges) {
      if (e.from === n.id && byId.get(e.to) && !byId.get(e.to)._new) nb.push(byId.get(e.to));
      if (e.to === n.id && byId.get(e.from) && !byId.get(e.from)._new) nb.push(byId.get(e.from));
    }
    if (nb.length) {
      n.x = Math.round(nb.reduce((s, p) => s + p.x, 0) / nb.length / 10) * 10;
      n.y = Math.round((nb.reduce((s, p) => s + p.y, 0) / nb.length + 110) / 10) * 10;
    } else {
      n.x = 40 * cascade; n.y = 40 * cascade; cascade++;
    }
    let guard = 0;
    while (guard++ < 50 && nodes.some((o) => o !== n && Math.abs(o.x - n.x) < 10 && Math.abs(o.y - n.y) < 10)) {
      n.x += 30; n.y += 30;
    }
  }
}

// Ruta de grupo de un nodo/grupo (cadena de ids desde la raiz), para que
// layeredLayout ordene cada capa y los miembros de un grupo caigan juntos.
function groupPathOf(el, groups) {
  const gmap = new Map((groups || []).map((g) => [g.id, g]));
  const path = [];
  let pid = el.parent;
  while (pid) {
    path.unshift(pid);
    const g = gmap.get(pid);
    pid = g ? g.parent : undefined;
  }
  return path.join('/');
}

// Auto-distribucion por capas (para codigo importado desde cero).
function layeredLayout(nodes, edges, dir, groups) {
  const adj = new Map(nodes.map((n) => [n.id, []]));
  const indeg = new Map(nodes.map((n) => [n.id, 0]));
  for (const e of edges) {
    if (adj.has(e.from) && indeg.has(e.to)) { adj.get(e.from).push(e.to); indeg.set(e.to, indeg.get(e.to) + 1); }
  }
  const layer = new Map();
  const q = [];
  nodes.forEach((n) => { if (indeg.get(n.id) === 0) { layer.set(n.id, 0); q.push(n.id); } });
  if (!q.length && nodes.length) { layer.set(nodes[0].id, 0); q.push(nodes[0].id); }
  while (q.length) {
    const id = q.shift();
    const L = layer.get(id);
    for (const t of adj.get(id) || []) {
      const nl = L + 1;
      if (nl < nodes.length && (layer.get(t) ?? -1) < nl) { layer.set(t, nl); q.push(t); }
    }
  }
  nodes.forEach((n) => { if (!layer.has(n.id)) layer.set(n.id, 0); });

  const gpath = new Map(nodes.map((n) => [n.id, groupPathOf(n, groups)]));
  const byLayer = new Map();
  nodes.forEach((n) => { const L = layer.get(n.id); (byLayer.get(L) || byLayer.set(L, []).get(L)).push(n); });
  for (const arr of byLayer.values()) {
    arr.sort((a, b) => {
      const pa = gpath.get(a.id), pb = gpath.get(b.id);
      if (pa === pb) return 0;
      return pa < pb ? -1 : 1;
    });
  }
  const GX = 200, GY = 120;
  const horizontal = (dir === 'LR' || dir === 'RL');
  for (const [L, arr] of byLayer) {
    arr.forEach((n, i) => {
      const across = (i - (arr.length - 1) / 2) * GX;
      const along = L * GY;
      if (horizontal) { n.x = along * (dir === 'RL' ? -1 : 1); n.y = across; }
      else { n.x = across; n.y = along * (dir === 'BT' ? -1 : 1); }
    });
  }
}

// =============================================================================
//  Interaccion: arrastrar nodos y grupos, conectar, panear
// =============================================================================
let drag = null;

function startNodeDrag(ev, n) {
  if (ev.target.classList.contains('port')) return;
  ev.stopPropagation();
  if (ev.shiftKey) { toggleMultiSelect(n.id); return; }
  select('node', n.id);
  const start = toWorld(ev.clientX, ev.clientY);
  drag = { type: 'node', node: n, dx: start.x - n.x, dy: start.y - n.y, moved: false, snap: false };
  svg.setPointerCapture(ev.pointerId);
}

function startGroupDrag(ev, g) {
  ev.stopPropagation();
  select('group', g.id);
  const start = toWorld(ev.clientX, ev.clientY);
  const members = groupDescendantNodes(g.id).map((n) => ({ n, x0: n.x, y0: n.y }));
  const descGroups = allDescendantGroups(g.id).filter((cg) => cg.anchor).map((cg) => ({ cg, x0: cg.anchor.x, y0: cg.anchor.y }));
  const selfAnchor = g.anchor ? { x0: g.anchor.x, y0: g.anchor.y } : null;
  drag = { type: 'group', group: g, sx: start.x, sy: start.y, members, descGroups, selfAnchor, moved: false, snap: false };
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
  const g = groupAt(ev.clientX, ev.clientY);
  if (g) { startGroupDrag(ev, g); return; }
  select(null);
  drag = { type: 'pan', sx: ev.clientX, sy: ev.clientY, tx: view.tx, ty: view.ty };
  svg.classList.add('panning');
  svg.setPointerCapture(ev.pointerId);
}

svg.addEventListener('pointerdown', startPan);

// Renombrar un grupo: doble clic en su cabecera/borde (mismo hit-test que el
// arrastre, groupAt(); .group-head/.group-rect son pointer-events:none a
// proposito, asi que este es el UNICO camino real por el que llega el evento).
svg.addEventListener('dblclick', (ev) => {
  if (ev.target.closest('.node') || ev.target.closest('.edge')) return;
  const g = groupAt(ev.clientX, ev.clientY);
  if (g) editGroupLabel(g);
});

svg.addEventListener('pointermove', (ev) => {
  if (!drag) return;
  const w = toWorld(ev.clientX, ev.clientY);
  if (drag.type === 'node') {
    if (!drag.snap) { snapshot(); drag.snap = true; }
    drag.moved = true;
    drag.node.x = Math.round((w.x - drag.dx) / 10) * 10;
    drag.node.y = Math.round((w.y - drag.dy) / 10) * 10;
    render();
  } else if (drag.type === 'group') {
    if (!drag.snap) { snapshot(); drag.snap = true; }
    drag.moved = true;
    // Delta ENTERO redondeado a 10 (D3): nunca se redondea nodo a nodo, o se
    // destruirian los offsets relativos entre los miembros del grupo.
    const dx = Math.round((w.x - drag.sx) / 10) * 10;
    const dy = Math.round((w.y - drag.sy) / 10) * 10;
    for (const m of drag.members) { m.n.x = m.x0 + dx; m.n.y = m.y0 + dy; }
    for (const dg of drag.descGroups) dg.cg.anchor = { x: dg.x0 + dx, y: dg.y0 + dy };
    if (drag.selfAnchor) drag.group.anchor = { x: drag.selfAnchor.x0 + dx, y: drag.selfAnchor.y0 + dy };
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
//  Seleccion (nodo / arista / grupo / multiple) + barra flotante
// =============================================================================
function select(type, id) {
  selection = type ? { type, id } : null;
  render();
}
function toggleMultiSelect(id) {
  if (!selection || selection.type !== 'multi') selection = { type: 'multi', ids: [] };
  const idx = selection.ids.indexOf(id);
  if (idx >= 0) selection.ids.splice(idx, 1); else selection.ids.push(id);
  if (!selection.ids.length) selection = null;
  render();
}
function syncGroupButton() {
  const btn = $('#groupBtn');
  if (btn) btn.disabled = !(selection && selection.type === 'multi' && selection.ids.length > 0);
}
function groupSelection() {
  if (!selection || selection.type !== 'multi' || !selection.ids.length) return;
  snapshot();
  const id = 'g' + (++state.seq);
  state.groups.push({ id, label: 'Grupo' });
  for (const nid of selection.ids) { const n = getNode(nid); if (n) n.parent = id; }
  state = normalizeState(state);
  select('group', id);
}

function currentColorTarget() {
  if (!selection) return null;
  if (selection.type === 'node') return getNode(selection.id);
  if (selection.type === 'group') return getGroup(selection.id);
  return null;
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
  } else if (selection.type === 'edge') {
    const e = state.edges.find((x) => x.id === selection.id);
    if (!e) { fb.style.display = 'none'; return; }
    const a = getNode(e.from), b = getNode(e.to);
    if (!a || !b) { fb.style.display = 'none'; return; }
    cx = view.tx + ((a.x + b.x) / 2) * view.scale;
    top = view.ty + ((a.y + b.y) / 2) * view.scale - 52;
  } else if (selection.type === 'group') {
    const g = getGroup(selection.id);
    if (!g) { fb.style.display = 'none'; return; }
    const b = groupBox(g);
    cx = view.tx + (b.x + b.w / 2) * view.scale;
    top = view.ty + b.y * view.scale - 52;
  } else if (selection.type === 'multi') {
    const ns = selection.ids.map(getNode).filter(Boolean);
    if (!ns.length) { fb.style.display = 'none'; return; }
    const avgX = ns.reduce((s, n) => s + n.x, 0) / ns.length;
    const minY = Math.min(...ns.map((n) => n.y - n.h / 2));
    cx = view.tx + avgX * view.scale;
    top = view.ty + minY * view.scale - 52;
  } else {
    fb.style.display = 'none'; return;
  }
  fb.style.display = 'flex';
  // el fondo tiene un padre relativo (.canvas-wrap); las coords son relativas a el
  fb.style.left = Math.max(8, cx - fb.offsetWidth / 2) + 'px';
  fb.style.top = Math.max(8, top) + 'px';
  updateFloatbarVisibility();
}

function syncFloatbarColorInputs() {
  const el = currentColorTarget();
  const c = (el && el.colors) || {};
  const fill = $('#fbFill'), stroke = $('#fbStroke'), hex = $('#fbHex');
  if (fill) fill.value = c.fill || '#3b82f6';
  if (stroke) stroke.value = c.stroke || '#1d4ed8';
  if (hex) hex.value = c.fill || '';
}
function updateFloatbarVisibility() {
  const t = selection ? selection.type : null;
  const colorable = t === 'node' || t === 'group';
  $('#floatbar').querySelectorAll('.swatch, .sep, #fbFill, #fbStroke, #fbHex').forEach((el) => {
    el.style.display = colorable ? '' : 'none';
  });
  const removeBtn = $('#fbRemoveFromGroup');
  if (removeBtn) removeBtn.style.display = (t === 'node' && getNode(selection.id) && getNode(selection.id).parent) ? '' : 'none';
  $('#fbEdit').style.display = (t === 'node' || t === 'edge' || t === 'group') ? '' : 'none';
  $('#fbDel').style.display = (t === 'node' || t === 'edge' || t === 'group' || t === 'multi') ? '' : 'none';
  $('#fbDel').textContent = (t === 'group') ? 'Desagrupar' : 'Borrar';
  if (colorable) syncFloatbarColorInputs();
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
function editGroupLabel(g) {
  const b = groupBox(g);
  const cx = view.tx + (b.x + b.w / 2) * view.scale;
  const cy = view.ty + (b.y + HEAD_G / 2) * view.scale;
  showEditor(cx, cy, 140, g.label, (val) => {
    snapshot();
    g.label = val.trim() || g.label;
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
  if (!state.nodes.length && !state.groups.length) { view = { scale: 1, tx: 0, ty: 0 }; applyView(); return; }
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of state.nodes) {
    minX = Math.min(minX, n.x - n.w / 2); maxX = Math.max(maxX, n.x + n.w / 2);
    minY = Math.min(minY, n.y - n.h / 2); maxY = Math.max(maxY, n.y + n.h / 2);
  }
  for (const g of state.groups.filter((x) => !x.parent)) {
    const b = groupBox(g);
    minX = Math.min(minX, b.x); maxX = Math.max(maxX, b.x + b.w);
    minY = Math.min(minY, b.y); maxY = Math.max(maxY, b.y + b.h);
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
async function renderPreview(codeText) {
  const host = $('#previewHost'), err = $('#previewErr');
  err.textContent = '';
  const code = (codeText != null) ? codeText : buildCode();
  if (!code.trim() || (codeText == null && !state.nodes.length)) {
    host.innerHTML = '<div class="empty">Sin nodos todavia.</div>'; return;
  }
  const my = ++previewSeq;
  try {
    const { svg: out } = await mermaid.render('prev' + my, code);
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
  const { svg: out } = await mermaid.render('exp' + Date.now(), currentCode());
  return out;
}
// codigo vigente: lo que ve el usuario en el editor (o el generado, si no existe)
function currentCode() {
  const ta = $('#codeInput');
  return (ta && ta.value.trim()) ? ta.value : buildCode();
}

$('#copy').onclick = async () => {
  try { await navigator.clipboard.writeText(currentCode()); toast('Codigo copiado'); }
  catch { toast('No se pudo copiar'); }
};
$('#dlMmd').onclick = () => download('diagrama.mmd', new Blob([currentCode()], { type: 'text/plain' }));
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
    state = normalizeState(s);
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
  if (sw && selection && (selection.type === 'node' || selection.type === 'group')) {
    snapshot();
    const el = currentColorTarget();
    if (!el) return;
    const key = sw.dataset.color;
    if (key === 'default') { delete el.colors; }
    else {
      const [stroke, fill] = NODE_COLORS[key];
      el.colors = { fill: normHex(fill), stroke: normHex(stroke), strokeWidth: '2px' };
    }
    render();
  }
});
function setElColor(field, value) {
  const el = currentColorTarget();
  if (!el) return;
  snapshot();
  el.colors = Object.assign({ strokeWidth: '2px' }, el.colors);
  el.colors[field] = value;
  render();
}
// Los controles de color y de grupo son nuevos (ADR-0004): se buscan de forma
// defensiva (si el markup no los trae todavia, o en el banco de pruebas que
// carga editor.js sobre un DOM minimo, editor.js sigue cargando igual).
const fbFillEl = $('#fbFill'), fbStrokeEl = $('#fbStroke'), fbHexEl = $('#fbHex');
if (fbFillEl) fbFillEl.addEventListener('input', () => {
  const v = normHex(fbFillEl.value);
  setElColor('fill', v);
  if (fbHexEl) fbHexEl.value = v;
});
if (fbStrokeEl) fbStrokeEl.addEventListener('input', () => setElColor('stroke', normHex(fbStrokeEl.value)));
if (fbHexEl) fbHexEl.addEventListener('change', () => {
  const v = fbHexEl.value.trim();
  if (!HEX_RE.test(v)) { toast('Hex no valido (usa #rgb o #rrggbb)'); syncFloatbarColorInputs(); return; }
  const nv = normHex(v);
  setElColor('fill', nv);
  if (fbFillEl) fbFillEl.value = nv;
});
const fbRemoveFromGroupEl = $('#fbRemoveFromGroup');
if (fbRemoveFromGroupEl) fbRemoveFromGroupEl.onclick = () => {
  if (!selection || selection.type !== 'node') return;
  const n = getNode(selection.id);
  if (!n || !n.parent) return;
  snapshot();
  delete n.parent;
  state = normalizeState(state);
  render();
};
$('#fbDel').onclick = deleteSelection;
$('#fbEdit').onclick = () => {
  if (!selection) return;
  if (selection.type === 'node') editLabel(getNode(selection.id));
  else if (selection.type === 'edge') editEdgeLabel(state.edges.find((e) => e.id === selection.id));
  else if (selection.type === 'group') editGroupLabel(getGroup(selection.id));
};
const groupBtnEl = $('#groupBtn');
if (groupBtnEl) groupBtnEl.onclick = groupSelection;

$('#undo').onclick = undo;
$('#redo').onclick = redo;
$('#zoomIn').onclick = () => zoomBy(1.2);
$('#zoomOut').onclick = () => zoomBy(1 / 1.2);
$('#zoomFit').onclick = fitView;
$('#clear').onclick = () => {
  if (!state.nodes.length && !state.edges.length && !state.groups.length) return;
  if (!confirm('Vaciar el lienzo? Se perdera el diagrama actual.')) return;
  snapshot();
  state.nodes = []; state.edges = []; state.groups = []; selection = null;
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
  renderPreview(currentCode());
};

// --- edicion del codigo -> lienzo --------------------------------------------
// Al escribir en el panel, se parsea (con retardo) y se reconstruye el diagrama.
const codeInput = $('#codeInput');
let codeTimer = null;
function showCodeError(msg) {
  const el = $('#codeErr');
  el.textContent = msg || '';
  el.classList.toggle('show', !!msg);
}
codeInput.addEventListener('input', () => {
  updateHighlight(codeInput.value);
  clearTimeout(codeTimer);
  codeTimer = setTimeout(() => {
    let res;
    try { res = parseCode(codeInput.value); }
    catch (e) { res = { ok: false, error: e.message }; }
    if (res.ok) {
      showCodeError('');
      snapshot();
      suppressCodeWrite = true;
      applyParsed(res.data);
      suppressCodeWrite = false;
    } else {
      showCodeError(res.error || 'Codigo no valido');
    }
    if ($('#previewView').classList.contains('show')) renderPreview(codeInput.value);
  }, 300);
});
codeInput.addEventListener('scroll', () => {
  const hl = $('#codeHl');
  hl.scrollTop = codeInput.scrollTop;
  hl.scrollLeft = codeInput.scrollLeft;
});

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
  if (document.activeElement === $('#codeInput')) return;  // el textarea gestiona su edicion
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
//  Guardar / cargar en el servidor local (carpeta graphs/)
// =============================================================================
const TOKEN = new URLSearchParams(location.search).get('t') || '';
const SERVER = location.protocol === 'http:' && !!TOKEN;

async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.method || 'GET',
    headers: Object.assign({ 'X-Token': TOKEN }, opts.body ? { 'Content-Type': 'application/json' } : {}),
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

function fmtDate(sec) {
  try {
    const d = new Date(sec * 1000);
    return d.toLocaleDateString() + ' ' + d.toTimeString().slice(0, 5);
  } catch { return ''; }
}

// Reemplaza el diagrama actual por un estado guardado (con sus posiciones).
function setStateFrom(s) {
  if (!s || !Array.isArray(s.nodes)) return false;
  state = normalizeState(s);
  selection = null;
  undoStack = []; redoStack = []; refreshUndoButtons();
  syncDirButtons();
  render();
  fitView();
  return true;
}

async function refreshSavedList() {
  const list = $('#savedList');
  try {
    const { graphs } = await api('/list');
    if (!graphs.length) { list.innerHTML = '<div class="saved-empty">No hay diagramas guardados.</div>'; return; }
    list.innerHTML = '';
    for (const g of graphs) {
      const item = document.createElement('div');
      item.className = 'saved-item';
      item.innerHTML = '<span class="nm"></span><span class="dt"></span><button class="del" title="Borrar">&#10005;</button>';
      item.querySelector('.nm').textContent = g.name;
      item.querySelector('.dt').textContent = fmtDate(g.savedAt);
      const open = () => loadGraph(g.name);
      item.querySelector('.nm').onclick = open;
      item.querySelector('.dt').onclick = open;
      item.querySelector('.del').onclick = (e) => { e.stopPropagation(); deleteGraph(g.name); };
      list.appendChild(item);
    }
  } catch (_) { /* servidor no disponible: se ignora */ }
}

async function saveGraph() {
  const name = $('#graphName').value.trim();
  if (!name) { toast('Escribe un nombre'); $('#graphName').focus(); return; }
  try {
    await api('/save', { method: 'POST', body: { name, mmd: currentCode(), state } });
    toast('Guardado: ' + name);
    refreshSavedList();
  } catch (e) { toast('No se pudo guardar: ' + e.message); }
}

async function loadGraph(name) {
  try {
    const data = await api('/load?name=' + encodeURIComponent(name));
    if (data.state && setStateFrom(data.state)) {
      // ok, restaurado con posiciones
    } else if (data.mmd) {
      applyParsed(parseCode(data.mmd).data);
    } else {
      toast('El diagrama esta vacio'); return;
    }
    $('#graphName').value = name;
    toast('Cargado: ' + name);
  } catch (e) { toast('No se pudo cargar: ' + e.message); }
}

async function deleteGraph(name) {
  if (!confirm('Borrar el diagrama "' + name + '"? (borra el .mmd y el .layout.json)')) return;
  try { await api('/delete', { method: 'POST', body: { name } }); toast('Borrado: ' + name); refreshSavedList(); }
  catch (e) { toast('No se pudo borrar: ' + e.message); }
}

if (SERVER) {
  $('#saveGraph').onclick = saveGraph;
  $('#graphName').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); saveGraph(); } });
} else {
  $('#saveSection').querySelector('.saverow').style.display = 'none';
  $('#savedList').style.display = 'none';
  const h = $('#saveHint');
  h.hidden = false;
  h.textContent = 'Guardar y cargar estan disponibles al abrir con el lanzador Mermaid (servidor local).';
}

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

(async function init() {
  const savedTheme = localStorage.getItem('bstools.mermaid.theme');
  const light = savedTheme === 'light';
  if (light) document.documentElement.classList.add('light');
  mermaid.initialize({ startOnLoad: false, theme: light ? 'default' : 'dark', securityLevel: 'loose' });

  buildPalette();

  // Si se abrio con un .mmd (menu contextual), se precarga; si trae layout, con
  // sus posiciones. Si no, se restaura la ultima sesion o el ejemplo.
  let loaded = false;
  if (SERVER) {
    try {
      const pre = await api('/preload');
      if (pre && pre.state && setStateFrom(pre.state)) loaded = true;
      else if (pre && pre.mmd) { applyParsed(parseCode(pre.mmd).data); loaded = true; }
      if (loaded && pre.name) $('#graphName').value = pre.name;
    } catch (_) { /* sin precarga */ }
  }
  if (!loaded && !load()) seedExample();

  syncDirButtons();
  render();
  fitView();

  if (SERVER) refreshSavedList();
})();
