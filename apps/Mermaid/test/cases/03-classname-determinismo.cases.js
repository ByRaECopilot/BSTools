'use strict';
/*
 * Prioridad 2 (ADR-0004 S2bis): determinismo del nombre de classDef.
 * bs_<fill>_<stroke>_<text>, hex normalizado a 6 digitos minuscula, componente
 * ausente -> "none", stroke-width NUNCA entra en el nombre, y con styleExtra
 * se anade "_x<hash8>" (FNV-1a de 32 bits).
 *
 * Los dos primeros casos usan los ejemplos LITERALES que trae el propio ADR
 * (lineas 166-170): "bs_c62828_6b1414_ffffff" y "bs_c62828_none_ffffff".
 */
module.exports = function (t) {
  const { test, fresh, callFn, fnv1a32Hex, assertEqual, assertTrue, assertMatch } = t;

  test('classNameFor: ejemplo literal del ADR - fill+stroke+text conocidos', () => {
    const { sandbox } = fresh();
    const name = callFn(sandbox, 'classNameFor', { fill: '#c62828', stroke: '#6b1414', text: '#ffffff' }, '');
    assertEqual(name, 'bs_c62828_6b1414_ffffff', 'el ADR-0004 (S2bis, linea 166-167) da este nombre como ejemplo exacto');
  });

  test('classNameFor: stroke ausente -> componente "none" (ejemplo literal del ADR)', () => {
    const { sandbox } = fresh();
    const name = callFn(sandbox, 'classNameFor', { fill: '#c62828', text: '#ffffff' }, '');
    assertEqual(name, 'bs_c62828_none_ffffff', 'el ADR-0004 (S2bis, linea 169-170) da este nombre como ejemplo exacto');
  });

  test('classNameFor: stroke-width NO entra en el nombre (se deriva de stroke)', () => {
    const { sandbox } = fresh();
    const a = callFn(sandbox, 'classNameFor', { fill: '#c62828', stroke: '#6b1414', text: '#ffffff', strokeWidth: '2px' }, '');
    const b = callFn(sandbox, 'classNameFor', { fill: '#c62828', stroke: '#6b1414', text: '#ffffff', strokeWidth: '5px' }, '');
    assertEqual(a, b, 'dos colores con distinto strokeWidth deben producir el MISMO nombre de clase (ADR S2bis, explicito)');
  });

  test('classNameFor: es funcion pura del contenido, determinista entre llamadas', () => {
    const { sandbox } = fresh();
    const c1 = callFn(sandbox, 'classNameFor', { fill: '#111111', stroke: '#222222', text: '#ffffff' }, '');
    const c2 = callFn(sandbox, 'classNameFor', { fill: '#111111', stroke: '#222222', text: '#ffffff' }, '');
    assertEqual(c1, c2, 'la misma entrada debe producir siempre el mismo nombre (no puede depender de un contador de sesion, ADR S2bis)');
  });

  test('classNameFor: formato general - bs_<fill>_<stroke|none>_<text>[_x<hash8>]', () => {
    const { sandbox } = fresh();
    const sinExtra = callFn(sandbox, 'classNameFor', { fill: '#abcdef', stroke: '#123456', text: '#ffffff' }, '');
    assertMatch(sinExtra, /^bs_[0-9a-f]{6}_(none|[0-9a-f]{6})_[0-9a-f]{6}$/, 'sin styleExtra no debe llevar el sufijo _x');

    const conExtra = callFn(sandbox, 'classNameFor', { fill: '#abcdef', stroke: '#123456', text: '#ffffff' }, 'stroke-dasharray:5 5');
    assertMatch(conExtra, /^bs_[0-9a-f]{6}_[0-9a-f]{6}_[0-9a-f]{6}_x[0-9a-f]{8}$/, 'con styleExtra debe llevar el sufijo _x<hash8> de 8 digitos hex (ADR S2bis)');
  });

  test('classNameFor: el sufijo _x es FNV-1a-32 (asumiendo que hashea styleExtra verbatim - confirmar con Atlas)', () => {
    const { sandbox } = fresh();
    const extra = 'stroke-dasharray:5 5';
    const name = callFn(sandbox, 'classNameFor', { fill: '#abcdef', stroke: '#123456', text: '#ffffff' }, extra);
    const hashEsperado = fnv1a32Hex(extra);
    assertTrue(name.endsWith('_x' + hashEsperado),
      'ASUNCION a confirmar con Atlas: el hash8 es FNV-1a-32(styleExtra) verbatim (no de una "cadena canonica" mas larga que incluya fill/stroke/text) - ver informe final de Veritas',
      name);
  });

  test('classNameFor: mismos colores + distinto styleExtra -> mismo prefijo, distinto sufijo', () => {
    const { sandbox } = fresh();
    const n1 = callFn(sandbox, 'classNameFor', { fill: '#abcdef', stroke: '#123456', text: '#ffffff' }, 'stroke-dasharray:5 5');
    const n2 = callFn(sandbox, 'classNameFor', { fill: '#abcdef', stroke: '#123456', text: '#ffffff' }, 'stroke-dasharray:2 2');
    assertTrue(n1 !== n2, 'distinto styleExtra debe producir un nombre completo distinto (para no compartir classDef con contenido distinto)');
    assertEqual(n1.split('_x')[0], n2.split('_x')[0], 'el prefijo bs_<fill>_<stroke>_<text> debe ser identico si los colores son iguales');
  });

  test('classNameFor: colores distintos -> nombres distintos (no colisiona por azar)', () => {
    const { sandbox } = fresh();
    const n1 = callFn(sandbox, 'classNameFor', { fill: '#c62828', stroke: '#6b1414', text: '#ffffff' }, '');
    const n2 = callFn(sandbox, 'classNameFor', { fill: '#22c55e', stroke: '#166534', text: '#ffffff' }, '');
    assertTrue(n1 !== n2, 'colores de contenido distinto deben producir nombres distintos');
  });
};
