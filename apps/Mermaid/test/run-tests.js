'use strict';
/*
 * Banco de pruebas de "grupos + estilos libres" (ADR-0004) para Mermaid.
 * Carga el editor.js REAL (sin tocarlo) y ejercita sus funciones puras o
 * casi-puras. Sin dependencias: solo Node. Ver README.md para como correrlo.
 *
 * Nace en rojo mientras Atlas construye la feature: es lo esperado y correcto.
 */
const fs = require('fs');
const path = require('path');
const { loadEditor, getVar, setVar, callFn } = require('./dom-shim');
const assertLib = require('./assert');
const { fnv1a32Hex } = require('./fnv1a');

const CASES_DIR = path.join(__dirname, 'cases');
const MERMAID_DIR = path.join(__dirname, '..');

const tests = [];
function test(name, fn) { tests.push({ name, fn }); }

function fresh() { return loadEditor(); }

// Ejecuta buildCode() con `data` inyectado como el `state` de nivel superior
// del editor (state.dir/nodes/edges/seq/groups). Es el "puente" del shim:
// buildCode es casi-pura (lee el `state` de modulo), asi que para probarla
// como funcion pura primero se le inyecta el estado deseado.
function buildFrom(sandbox, data) {
  setVar(sandbox, 'state', {
    dir: data.dir || 'TD',
    seq: data.seq || 0,
    nodes: data.nodes || [],
    edges: data.edges || [],
    groups: data.groups || [],
  });
  return callFn(sandbox, 'buildCode');
}

function parseOk(sandbox, text) {
  const res = callFn(sandbox, 'parseCode', text);
  if (!res || !res.ok) throw new Error('parseCode fallo: ' + (res && res.error));
  return res.data;
}

// buildCode(parseCode(x)) - el camino completo de ida y vuelta de codigo.
function roundTrip(sandbox, text) {
  const data = parseOk(sandbox, text);
  return buildFrom(sandbox, data);
}

const helpers = Object.assign(
  { test, fresh, getVar, setVar, callFn, buildFrom, parseOk, roundTrip, fnv1a32Hex, fs, path, MERMAID_DIR },
  assertLib
);

const files = fs.readdirSync(CASES_DIR).filter((f) => f.endsWith('.cases.js')).sort();
if (!files.length) {
  console.log('No se encontraron casos en ' + CASES_DIR);
  process.exitCode = 1;
} else {
  for (const f of files) {
    try {
      const register = require(path.join(CASES_DIR, f));
      register(helpers);
    } catch (e) {
      console.log('ERROR AL CARGAR ' + f + ': ' + e.message);
      process.exitCode = 1;
    }
  }

  let ok = 0;
  let fail = 0;
  const failures = [];
  for (const { name, fn } of tests) {
    try {
      fn();
      ok++;
      console.log('  OK    ' + name);
    } catch (e) {
      fail++;
      failures.push({ name, error: e });
      console.log('  FALLO ' + name);
    }
  }

  if (failures.length) {
    console.log('');
    console.log('--- Detalle de fallos --------------------------------------------');
    for (const { name, error } of failures) {
      console.log('');
      console.log('Caso: ' + name);
      if (error && error.label !== undefined) {
        console.log('  Assert:   ' + error.label);
        console.log('  Esperado: ' + error.expected);
        console.log('  Obtenido: ' + error.actual);
      } else {
        console.log('  Error: ' + (error && error.message ? error.message : String(error)));
      }
    }
  }

  console.log('');
  console.log('====================================================');
  console.log('OK ' + ok + ' / FALLO ' + fail + '  (total ' + (ok + fail) + ' casos)');
  console.log('====================================================');

  if (fail) process.exitCode = 1;
}
