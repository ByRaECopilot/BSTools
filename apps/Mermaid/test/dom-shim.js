'use strict';
/*
 * Shim minimo de document/localStorage para cargar el editor.js REAL (sin
 * modificarlo) dentro de un vm.Script de Node, sin dependencias externas.
 *
 * Tecnica: los `function foo(){}` de nivel superior de editor.js se cuelgan
 * como propiedades del objeto "sandbox" contextificado (comportamiento
 * estandar de var/function en un script de nivel superior, incluso en modo
 * estricto) y por eso son invocables directamente como sandbox.parseCode(...),
 * sandbox.buildCode(...), etc.
 *
 * Las variables `let`/`const` de nivel superior (state, selection, view...)
 * NO se cuelgan como propiedades del sandbox: viven en un entorno lexico
 * propio del contexto, compartido entre todos los vm.Script que se ejecuten
 * sobre el MISMO objeto contextificado. Para leerlas o escribirlas desde
 * fuera se usa el "puente": se deja un valor en sandbox.__bridge__ (una
 * propiedad normal, visible en ambos sentidos) y se ejecuta un vm.Script de
 * una linea que hace `nombre = __bridge__;` o `__bridge__ = nombre;`.
 * Ver getVar()/setVar() mas abajo.
 */
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const { URLSearchParams } = require('url');

const EDITOR_PATH = path.join(__dirname, '..', 'editor.js');

// =============================================================================
//  DOM minimo: solo lo que editor.js toca de verdad (ver README.md, seccion
//  "Que cubre el shim" para el inventario completo).
// =============================================================================
function toDatasetKey(attr) {
  // 'data-fill' -> 'fill' ; 'data-stroke-width' -> 'strokeWidth' (no se usa hoy,
  // pero se deja generico por si Atlas anade mas atributos data-*).
  return attr.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}

function matchesOne(el, sel) {
  sel = sel.trim();
  if (!sel) return false;
  if (sel[0] === '#') return el.id === sel.slice(1);
  if (sel[0] === '.') return el._classes.has(sel.slice(1));
  return String(el.tagName).toLowerCase() === sel.toLowerCase();
}
function matches(el, selectorList) {
  return selectorList.split(',').some((s) => matchesOne(el, s));
}
function walk(el, fn) {
  for (const c of el.children) { fn(c); walk(c, fn); }
}

class FakeElement {
  constructor(tag) {
    this.tagName = tag;
    this._classes = new Set();
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.style = {};
    this.dataset = {};
    this._listeners = {};
    this._text = '';
    this._html = '';
    this.disabled = false;
    this.hidden = false;
    this.value = '';
    this._id = '';
  }
  get id() { return this._id; }
  set id(v) { this._id = v; this.attributes.id = v; if (this._registry) this._registry.set(v, this); }
  get className() { return [...this._classes].join(' '); }
  set className(v) { this._classes = new Set(String(v).split(/\s+/).filter(Boolean)); }
  get classList() {
    const el = this;
    return {
      add: (...cs) => cs.forEach((c) => el._classes.add(c)),
      remove: (...cs) => cs.forEach((c) => el._classes.delete(c)),
      toggle(c, force) {
        if (force === undefined) {
          if (el._classes.has(c)) { el._classes.delete(c); return false; }
          el._classes.add(c); return true;
        }
        if (force) el._classes.add(c); else el._classes.delete(c);
        return force;
      },
      contains: (c) => el._classes.has(c),
    };
  }
  setAttribute(k, v) {
    v = String(v);
    this.attributes[k] = v;
    if (k === 'id') this.id = v;
    else if (k === 'class') this.className = v;
    else if (k.startsWith('data-')) this.dataset[toDatasetKey(k)] = v;
  }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k) ? this.attributes[k] : null; }
  removeAttribute(k) { delete this.attributes[k]; }
  appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
  removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; }
  addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); }
  removeEventListener(type, fn) {
    if (!this._listeners[type]) return;
    this._listeners[type] = this._listeners[type].filter((f) => f !== fn);
  }
  set onclick(fn) { this._onclick = fn; }
  get onclick() { return this._onclick; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text; }
  set innerHTML(v) { this._html = String(v); this.children = []; }
  get innerHTML() { return this._html; }
  get outerHTML() { return `<${this.tagName}></${this.tagName}>`; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 1000, height: 700 }; }
  getContext() { return { font: '', measureText: (s) => ({ width: String(s).length * 7 }) }; }
  setPointerCapture() {}
  releasePointerCapture() {}
  focus() {}
  select() {}
  click() { (this._listeners.click || []).forEach((f) => f({ target: this })); if (this._onclick) this._onclick({ target: this }); }
  get offsetWidth() { return 120; }
  querySelector(sel) {
    let found = null;
    walk(this, (c) => { if (!found && matches(c, sel)) found = c; });
    return found;
  }
  querySelectorAll(sel) {
    const out = [];
    walk(this, (c) => { if (matches(c, sel)) out.push(c); });
    return out;
  }
  closest(sel) {
    let n = this;
    while (n) { if (matches(n, sel)) return n; n = n.parentNode; }
    return null;
  }
}

// Construye el arbol minimo que hace falta para que $('#id') y las
// querySelector(All) con alcance (ej. #floatbar .swatch) encuentren algo.
// Ids reales tomados de index.html: si Atlas cambia un id ahi, este arbol
// tiene que actualizarse igual (ver README.md).
function buildDom(idRegistry) {
  const mk = (tag, attrs) => {
    const el = new FakeElement(tag);
    el._registry = idRegistry;
    for (const k in attrs || {}) el.setAttribute(k, attrs[k]);
    return el;
  };

  const documentElement = mk('html', {});
  const body = mk('body', {});
  documentElement.appendChild(body);

  const dir = mk('div', { id: 'dir' });
  ['TD', 'LR', 'BT', 'RL'].forEach((d) => dir.appendChild(mk('button', { 'data-dir': d, class: d === 'TD' ? 'active' : '' })));
  body.appendChild(dir);
  body.appendChild(mk('button', { id: 'undo' }));
  body.appendChild(mk('button', { id: 'redo' }));
  body.appendChild(mk('button', { id: 'theme' }));
  body.appendChild(mk('button', { id: 'clear' }));

  body.appendChild(mk('div', { id: 'palette' }));

  const edgeStyle = mk('div', { id: 'edgeStyle' });
  ['arrow', 'open', 'dotted', 'thick'].forEach((es) => edgeStyle.appendChild(mk('button', { 'data-es': es, class: es === 'arrow' ? 'active' : '' })));
  body.appendChild(edgeStyle);

  const saveSection = mk('div', { id: 'saveSection' });
  const saverow = mk('div', { class: 'saverow' });
  saverow.appendChild(mk('input', { id: 'graphName' }));
  saverow.appendChild(mk('button', { id: 'saveGraph' }));
  saveSection.appendChild(saverow);
  saveSection.appendChild(mk('div', { id: 'savedList' }));
  saveSection.appendChild(mk('p', { id: 'saveHint' }));
  body.appendChild(saveSection);

  body.appendChild(mk('div', { id: 'hint' }));

  const svgEl = mk('svg', { id: 'canvas' });
  const world = mk('g', { id: 'world' });
  world.appendChild(mk('g', { id: 'edges' }));
  world.appendChild(mk('g', { id: 'nodes' }));
  // Capa de grupos del ADR-0004 (§3, paso 7): "antes de #edges". Se declara
  // aqui porque Atlas todavia no la ha anadido a index.html; si drawGroup()
  // hace $('#groups'), este shim ya la tiene lista.
  world.appendChild(mk('g', { id: 'groups' }));
  world.appendChild(mk('path', { id: 'tempEdge' }));
  svgEl.appendChild(world);
  body.appendChild(svgEl);

  body.appendChild(mk('input', { id: 'editor' }));

  const floatbar = mk('div', { id: 'floatbar' });
  ['default', '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7'].forEach((c) => floatbar.appendChild(mk('div', { class: 'swatch', 'data-color': c })));
  floatbar.appendChild(mk('div', { class: 'sep' }));
  floatbar.appendChild(mk('button', { id: 'fbEdit' }));
  floatbar.appendChild(mk('button', { id: 'fbDel' }));
  body.appendChild(floatbar);

  body.appendChild(mk('button', { id: 'zoomOut' }));
  body.appendChild(mk('button', { id: 'zoomFit' }));
  body.appendChild(mk('button', { id: 'zoomIn' }));

  body.appendChild(mk('button', { id: 'tabCode', class: 'active' }));
  body.appendChild(mk('button', { id: 'tabPreview' }));
  body.appendChild(mk('button', { id: 'copy' }));
  body.appendChild(mk('button', { id: 'dlMmd' }));
  body.appendChild(mk('button', { id: 'dlSvg' }));
  body.appendChild(mk('button', { id: 'dlPng' }));

  const codeView = mk('div', { id: 'codeView', class: 'code-edit' });
  codeView.appendChild(mk('pre', { id: 'codeHl' }));
  codeView.appendChild(mk('textarea', { id: 'codeInput' }));
  codeView.appendChild(mk('div', { id: 'codeErr' }));
  body.appendChild(codeView);

  const previewView = mk('div', { id: 'previewView' });
  previewView.appendChild(mk('div', { id: 'previewHost' }));
  previewView.appendChild(mk('div', { id: 'previewErr' }));
  body.appendChild(previewView);

  body.appendChild(mk('div', { id: 'toast' }));

  return { documentElement, mk };
}

// =============================================================================
//  Carga real de editor.js en un contexto vm nuevo (uno por caso de prueba:
//  el estado de modulo -state, selection, undo/redo- no debe filtrarse entre
//  casos).
// =============================================================================
function loadEditor() {
  const source = fs.readFileSync(EDITOR_PATH, 'utf8');
  const idRegistry = new Map();
  const { documentElement, mk } = buildDom(idRegistry);

  const store = new Map();
  const localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  };

  const document = {
    documentElement,
    activeElement: null,
    createElement: (tag) => { const el = new FakeElement(tag); el._registry = idRegistry; return el; },
    createElementNS: (ns, tag) => { const el = new FakeElement(tag); el._registry = idRegistry; return el; },
    querySelector(sel) {
      if (sel[0] === '#') return idRegistry.get(sel.slice(1)) || null;
      let found = null;
      walk(documentElement, (c) => { if (!found && matches(c, sel)) found = c; });
      return found;
    },
    querySelectorAll(sel) {
      const out = [];
      walk(documentElement, (c) => { if (matches(c, sel)) out.push(c); });
      return out;
    },
    addEventListener() {},
    removeEventListener() {},
  };

  const sandbox = {
    document,
    location: { search: '', protocol: 'file:', href: 'file:///editor.js' },
    localStorage,
    console,
    setTimeout: () => 0,
    clearTimeout() {},
    URLSearchParams,
    navigator: { clipboard: { writeText: async () => {} } },
    fetch: async () => { throw new Error('fetch no disponible en el banco de pruebas (SERVER=false por diseno)'); },
    confirm: () => true,
    mermaid: { initialize() {}, render: async () => ({ svg: '<svg></svg>' }) },
    URL: { createObjectURL: () => 'blob:fake', revokeObjectURL: () => {} },
    Blob: function Blob() {},
    Image: function Image() {},
  };
  sandbox.window = sandbox;
  // window.addEventListener('keydown'/'resize', ...) - editor.js:1083/1097.
  sandbox.addEventListener = () => {};
  sandbox.removeEventListener = () => {};

  vm.createContext(sandbox);
  try {
    new vm.Script(source, { filename: 'editor.js' }).runInContext(sandbox);
  } catch (e) {
    e.message = 'No se pudo cargar editor.js en el shim: ' + e.message;
    throw e;
  }

  return { sandbox, idRegistry, mk, localStorageStore: store };
}

// --- puente para leer/escribir variables `let`/`const` de nivel superior ----
function getVar(sandbox, name) {
  sandbox.__bridge__ = undefined;
  new vm.Script(`__bridge__ = (typeof ${name} !== 'undefined') ? ${name} : undefined;`).runInContext(sandbox);
  return sandbox.__bridge__;
}
function setVar(sandbox, name, value) {
  sandbox.__bridge__ = value;
  new vm.Script(`${name} = __bridge__;`).runInContext(sandbox);
}
// invoca una funcion de nivel superior por nombre, util cuando el nombre es
// dinamico o cuando la funcion todavia no existe (evita el TypeError de JS
// "x is not a function" fuera de contexto y lo cambia por un mensaje claro).
function callFn(sandbox, name, ...args) {
  const fn = sandbox[name];
  if (typeof fn !== 'function') {
    throw new Error(`${name}() no existe todavia en editor.js (se esperaba que Atlas la anadiera - ADR-0004 S3)`);
  }
  return fn(...args);
}

module.exports = { loadEditor, getVar, setVar, callFn, EDITOR_PATH, FakeElement };
