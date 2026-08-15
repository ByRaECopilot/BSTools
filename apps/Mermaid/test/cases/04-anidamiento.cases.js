'use strict';
/*
 * Prioridad 3 (ADR-0004 D4, criterio A9): anidamiento sin perdida silenciosa.
 * El modelo debe soportar group.parent igual que node.parent, el parser debe
 * reconstruir la profundidad y el emisor debe re-emitirla. Hoy (editor.js
 * actual) esto se APLANA a proposito (comentario en editor.js:499-501) - por
 * eso estos casos nacen en rojo.
 */
const NESTED_MMD = [
  'flowchart TD',
  '    subgraph A["A"]',
  '        subgraph B["B"]',
  '            N1["Uno"]',
  '        end',
  '        N2["Dos"]',
  '    end',
  '    N3["Tres"]',
  '    N1 --> N2',
  '    N2 --> N3',
].join('\n');

module.exports = function (t) {
  const { test, fresh, parseOk, buildFrom, assertEqual, assertTrue } = t;

  test('A9: subgraph anidado - el grupo interno lleva parent al externo (D4)', () => {
    const { sandbox } = fresh();
    const data = parseOk(sandbox, NESTED_MMD);
    const gA = data.groups.find((g) => g.id === 'A');
    const gB = data.groups.find((g) => g.id === 'B');
    assertTrue(!!gA, 'debe existir el grupo A', data.groups);
    assertTrue(!!gB, 'debe existir el grupo B', data.groups);
    assertEqual(gB.parent, 'A', 'B esta anidado dentro de A: gB.parent debe ser "A" (D4)');
    assertTrue(!gA.parent, 'A es el grupo raiz: no debe tener parent', gA);
  });

  test('A9: la pertenencia de los nodos respeta la profundidad (el mas interno gana)', () => {
    const { sandbox } = fresh();
    const data = parseOk(sandbox, NESTED_MMD);
    const n1 = data.nodes.find((n) => n.id === 'N1');
    const n2 = data.nodes.find((n) => n.id === 'N2');
    const n3 = data.nodes.find((n) => n.id === 'N3');
    assertEqual(n1.parent, 'B', 'N1 esta dentro de B (el subgraph mas interno)');
    assertEqual(n2.parent, 'A', 'N2 esta dentro de A pero fuera de B');
    assertTrue(!n3.parent, 'N3 es huerfano: esta fuera de cualquier subgraph', n3);
  });

  test('D4: el modelo NO aplana el anidamiento (nada se pierde en silencio)', () => {
    const { sandbox } = fresh();
    const data = parseOk(sandbox, NESTED_MMD);
    assertEqual(data.groups.length, 2, 'deben sobrevivir los 2 grupos - la v1 de hoy los aplana a 0 (editor.js:499-501, "Los subgrupos se aplanan")');
  });

  test('A9: la re-emision conserva la misma profundidad de anidamiento', () => {
    const { sandbox } = fresh();
    const data = parseOk(sandbox, NESTED_MMD);
    const code = buildFrom(sandbox, data);
    const lineas = code.split('\n').map((l) => l.trim()).filter(Boolean);
    const idxSubA = lineas.findIndex((l) => l.startsWith('subgraph A'));
    const idxSubB = lineas.findIndex((l) => l.startsWith('subgraph B'));
    const idxEnds = [];
    lineas.forEach((l, i) => { if (l === 'end') idxEnds.push(i); });
    assertTrue(idxSubA !== -1 && idxSubB !== -1, 'ambos "subgraph" deben re-emitirse', code);
    assertTrue(idxSubA < idxSubB, 'subgraph A debe abrir antes que subgraph B (B esta anidado en A)', code);
    assertEqual(idxEnds.length, 2, 'debe haber exactamente 2 "end" (uno por cada subgraph, anidados)', code);
    // B debe cerrar ANTES que A (esta mas adentro): el primer "end" que
    // aparece corresponde a B, el segundo a A.
    assertTrue(idxEnds[0] > idxSubB && idxEnds[0] < idxEnds[1], 'el primer "end" debe cerrar el subgraph mas interno (B)', code);
  });

  test('A9: round trip completo conserva grupos y profundidad tras dos pasadas', () => {
    const { sandbox } = fresh();
    const d1 = parseOk(sandbox, NESTED_MMD);
    const c1 = buildFrom(sandbox, d1);
    const d2 = parseOk(sandbox, c1);
    assertEqual(d2.groups.length, d1.groups.length, 'el numero de grupos no debe cambiar tras un ciclo completo');
    const gB2 = d2.groups.find((g) => g.id === 'B');
    assertTrue(!!gB2 && gB2.parent === 'A', 'B debe seguir anidado dentro de A tras el ciclo completo', gB2);
  });
};
