'use strict';
/* Aserciones minimas, sin dependencias. Cada fallo lleva caso + esperado +
 * obtenido (nunca un assert mudo). */

class AssertionError extends Error {
  constructor(label, expected, actual) {
    super(label);
    this.label = label;
    this.expected = expected;
    this.actual = actual;
  }
}

function fmt(v) {
  if (typeof v === 'string') return v;
  try { return JSON.stringify(v); } catch (_) { return String(v); }
}

function stableStringify(v) {
  return JSON.stringify(v, function replacer(k, val) {
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      const out = {};
      for (const kk of Object.keys(val).sort()) out[kk] = val[kk];
      return out;
    }
    return val;
  });
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) throw new AssertionError(label || 'assertEqual', fmt(expected), fmt(actual));
}

function assertDeepEqual(actual, expected, label) {
  const a = stableStringify(actual), e = stableStringify(expected);
  if (a !== e) throw new AssertionError(label || 'assertDeepEqual', e, a);
}

function assertTrue(cond, label, extra) {
  if (!cond) throw new AssertionError(label || 'assertTrue', 'condicion verdadera', extra !== undefined ? fmt(extra) : 'condicion falsa');
}

function assertMatch(str, re, label) {
  if (!re.test(str)) throw new AssertionError(label || 'assertMatch', 'que cumpla ' + re.toString(), fmt(str));
}

function assertThrows(fn, label) {
  let threw = false, err;
  try { fn(); } catch (e) { threw = true; err = e; }
  if (!threw) throw new AssertionError(label || 'assertThrows', 'que lanzara un error', 'no lanzo ningun error');
  return err;
}

module.exports = { AssertionError, assertEqual, assertDeepEqual, assertTrue, assertMatch, assertThrows, fmt };
