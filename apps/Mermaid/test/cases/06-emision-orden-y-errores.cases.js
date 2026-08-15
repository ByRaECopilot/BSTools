'use strict';
/*
 * Contrato de generacion y parseo (ADR-0004 S2/S2bis): orden fijo de emision,
 * precedencia style > class, saneado de styleExtra (R7, OWASP/XSS) y los
 * errores que deben quedar SIEMPRE visibles (nunca resueltos en silencio).
 */
module.exports = function (t) {
  const { test, fresh, callFn, parseOk, buildFrom, assertEqual, assertTrue, assertDeepEqual, assertThrows } = t;

  test('orden de emision: huerfanos primero, subgraph despues, arista despues de TODOS los grupos', () => {
    const { sandbox } = fresh();
    const state = {
      dir: 'TD', seq: 5,
      nodes: [
        { id: 'H1', shape: 'rect', label: 'Huerfano', x: 0, y: 0, w: 100, h: 52 },
        { id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, parent: 'G1' },
      ],
      edges: [{ id: 'e1', from: 'H1', to: 'N1', label: '', style: 'arrow' }],
      groups: [{ id: 'G1', label: 'Grupo' }],
    };
    const code = buildFrom(sandbox, state);
    const lineas = code.split('\n').map((l) => l.trim()).filter(Boolean);
    const idxH1 = lineas.findIndex((l) => l.startsWith('H1['));
    const idxSub = lineas.findIndex((l) => l.startsWith('subgraph'));
    const idxEdge = lineas.findIndex((l) => l.includes('H1') && l.includes('N1') && l.includes('-->'));
    assertTrue(idxH1 !== -1 && idxSub !== -1 && idxEdge !== -1, 'deben aparecer las 3 piezas: nodo huerfano, subgraph y arista', code);
    assertTrue(idxH1 < idxSub, 'el huerfano H1 debe declararse ANTES del subgraph (orden fijo, ADR S2)', code);
    assertTrue(idxEdge > idxSub, 'la arista debe emitirse DESPUES de (todos) los grupos (ADR S2)', code);
  });

  test('las aristas NUNCA se emiten dentro de un subgraph (ni siquiera si conecta dos miembros del mismo grupo)', () => {
    const { sandbox } = fresh();
    const state = {
      dir: 'TD', seq: 5,
      nodes: [
        { id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, parent: 'G1' },
        { id: 'N2', shape: 'rect', label: 'Dos', x: 0, y: 0, w: 100, h: 52, parent: 'G1' },
      ],
      edges: [{ id: 'e1', from: 'N1', to: 'N2', label: '', style: 'arrow' }],
      groups: [{ id: 'G1', label: 'Grupo' }],
    };
    const code = buildFrom(sandbox, state);
    let depth = 0, aristaDepth = null;
    for (const raw of code.split('\n')) {
      const l = raw.trim();
      if (/^subgraph\b/.test(l)) depth++;
      else if (l === 'end') depth--;
      else if (l.includes('N1') && l.includes('N2') && l.includes('-->')) aristaDepth = depth;
    }
    assertTrue(aristaDepth !== null, 'la arista N1-->N2 debe aparecer en algun sitio del codigo', code);
    assertEqual(aristaDepth, 0, 'la arista debe quedar fuera de cualquier subgraph (profundidad 0), ADR S2: "evita la sutileza de Mermaid por la que una arista declarada dentro pertenece a la caja"');
  });

  test('cada nodo se declara EXACTAMENTE una vez (Set de emitidos, ADR S2)', () => {
    const { sandbox } = fresh();
    const state = {
      dir: 'TD', seq: 5,
      // parent apunta a un grupo que NO esta en state.groups: grupo huerfano no saneado.
      nodes: [{ id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, parent: 'Fantasma' }],
      edges: [], groups: [],
    };
    const code = buildFrom(sandbox, state);
    const apariciones = (code.match(/\bN1\[/g) || []).length;
    assertEqual(apariciones, 1, 'N1 con parent a un grupo que no existe debe emitirse en la raiz UNA sola vez (ni 0 ni 2), ADR S2');
  });

  test('classDef se emiten ordenados alfabeticamente por nombre de clase (no por orden de creacion)', () => {
    const { sandbox } = fresh();
    const state = {
      dir: 'TD', seq: 5,
      nodes: [
        { id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, parent: 'GZ' },
        { id: 'N2', shape: 'rect', label: 'Dos', x: 0, y: 0, w: 100, h: 52, parent: 'GA' },
      ],
      edges: [],
      groups: [
        { id: 'GZ', label: 'Z', colors: { fill: '#ffffff', stroke: '#000000', text: '#000000' } },
        { id: 'GA', label: 'A', colors: { fill: '#111111', stroke: '#222222', text: '#ffffff' } },
      ],
    };
    const code = buildFrom(sandbox, state);
    const nombres = [...code.matchAll(/classDef\s+(\S+)/g)].map((m) => m[1]);
    assertTrue(nombres.length === 2, 'deben emitirse 2 classDef (uno por grupo con color)', code);
    const ordenados = [...nombres].sort();
    assertDeepEqual(nombres, ordenados, 'los classDef deben salir en orden alfabetico por nombre, aunque GZ se creara antes que GA (ADR S2)');
  });

  test('precedencia: si un id tiene class Y style, gana style (mas especifico, ADR S2bis)', () => {
    const { sandbox } = fresh();
    const mmd = [
      'flowchart TD',
      '    N1["Uno"]',
      '    classDef miClase fill:#111111,stroke:#222222,color:#ffffff',
      '    class N1 miClase',
      '    style N1 fill:#c62828,stroke:#6b1414,stroke-width:2px,color:#ffffff',
    ].join('\n');
    const data = parseOk(sandbox, mmd);
    const n1 = data.nodes.find((n) => n.id === 'N1');
    assertEqual((n1.colors || {}).fill, '#c62828', 'style debe ganarle a class cuando ambos aplican al mismo id (ADR S2bis: "gana style, es lo mas especifico")');
  });

  test('styleExtra saneado a pares [A-Za-z-]+:[^;<>"\']+ (R7, seguridad OWASP/XSS)', () => {
    const { sandbox } = fresh();
    const mmd = 'flowchart TD\n    N1["Uno"]\n    style N1 fill:#c62828,stroke-dasharray:5 5,evil:</style><script>alert(1)</script>';
    const data = parseOk(sandbox, mmd);
    const n1 = data.nodes.find((n) => n.id === 'N1');
    assertEqual((n1.colors || {}).fill, '#c62828', 'fill: debe reconocerse en una linea style con mas declaraciones ademas de fill/stroke (ya no basta con COLOR_BY_STROKE de hoy, ADR S2bis)');
    const extra = (n1.colors || {}).styleExtra || n1.styleExtra || '';
    assertTrue(extra.includes('stroke-dasharray:5 5'), 'un par valido (stroke-dasharray:5 5) debe conservarse en styleExtra', extra);
    assertTrue(!extra.includes('evil') && !/[<>"']/.test(extra), 'un par cuyo VALOR contiene < > " debe descartarse ENTERO (no sanearse a medias): styleExtra vuelve al codigo y al renderer, que corre con securityLevel:"loose" (R7)', extra);
  });

  test('error explicito: "end" sobrante nunca se ignora en silencio', () => {
    const { sandbox } = fresh();
    assertThrows(() => {
      const r = callFn(sandbox, 'parseCode', 'flowchart TD\n    N1["Uno"]\nend\nend');
      if (!r.ok) throw new Error(r.error);
    }, 'un "end" sin subgraph abierto debe ser un error visible, no ignorarse (ADR S2bis)');
  });

  test('error explicito: subgraph sin cerrar al terminar el fichero', () => {
    const { sandbox } = fresh();
    assertThrows(() => {
      const r = callFn(sandbox, 'parseCode', 'flowchart TD\n    subgraph G1["G1"]\n    N1["Uno"]');
      if (!r.ok) throw new Error(r.error);
    }, 'un subgraph que nunca cierra debe ser un error visible (ADR S2bis)');
  });

  test('error explicito: un grupo con el mismo id que un nodo nunca se resuelve solo', () => {
    const { sandbox } = fresh();
    assertThrows(() => {
      const r = callFn(sandbox, 'parseCode', 'flowchart TD\n    G1["Nodo"]\n    subgraph G1["Grupo"]\n    N1["Uno"]\n    end');
      if (!r.ok) throw new Error(r.error);
    }, 'un grupo con el mismo id que un nodo debe fallar visiblemente ("El grupo X usa el mismo id que un nodo", ADR S2bis)');
  });

  test('classDef y class son OBLIGATORIOS en el parser, no opcionales (si no, recargar el propio .mmd pierde el color)', () => {
    const { sandbox } = fresh();
    const mmd = [
      'flowchart TD',
      '    subgraph G1["Grupo"]',
      '        N1["Uno"]',
      '    end',
      '    classDef bs_c62828_none_ffffff fill:#c62828,color:#ffffff',
      '    class G1 bs_c62828_none_ffffff',
    ].join('\n');
    const data = parseOk(sandbox, mmd);
    const g1 = data.groups.find((g) => g.id === 'G1');
    assertTrue(!!g1, 'debe reconocer el grupo G1', data.groups);
    assertEqual((g1.colors || {}).fill, '#c62828', 'el color del grupo debe leerse de classDef+class, no perderse (ADR S2bis, el bug que la feature viene a matar)');
  });
};
