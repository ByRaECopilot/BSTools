'use strict';
/*
 * Prioridad 4: regresion de lo que YA funciona hoy en editor.js.
 * Estos casos deben estar en VERDE con el editor.js actual (antes de que
 * Atlas toque nada) y deben SEGUIR en verde despues de la feature de grupos:
 * es la red que avisa si el emisor/parser deja de reconocer lo de siempre.
 */
module.exports = function (t) {
  const { test, fresh, callFn, parseOk, buildFrom, roundTrip, assertEqual, assertDeepEqual, assertMatch } = t;

  test('regresion: las 8 formas hacen ida y vuelta sin cambiar de forma', () => {
    const { sandbox } = fresh();
    const wraps = {
      rect: '["ETIQUETA"]',
      round: '("ETIQUETA")',
      stadium: '(["ETIQUETA"])',
      subroutine: '[["ETIQUETA"]]',
      cylinder: '[("ETIQUETA")]',
      circle: '(("ETIQUETA"))',
      diamond: '{"ETIQUETA"}',
      hexagon: '{{"ETIQUETA"}}',
    };
    for (const [shape, wrap] of Object.entries(wraps)) {
      const mmd = 'flowchart TD\n    N1' + wrap;
      const data = parseOk(sandbox, mmd);
      assertEqual(data.nodes[0].shape, shape, 'la forma "' + shape + '" debe reconocerse tal cual al parsear (no debe romperla la feature de grupos)');
      const code = buildFrom(sandbox, data);
      const reparsed = parseOk(sandbox, code);
      assertEqual(reparsed.nodes[0].shape, shape, 'la forma "' + shape + '" debe sobrevivir un ciclo completo parse->build->parse');
    }
  });

  test('regresion: <br/> en la etiqueta se conserva como salto de linea real', () => {
    const { sandbox } = fresh();
    const data = parseOk(sandbox, 'flowchart TD\n    N1["Linea uno<br/>Linea dos"]');
    assertEqual(data.nodes[0].label, 'Linea uno\nLinea dos', '<br/> debe convertirse en salto de linea real (unquoteLabel)');
    const code = buildFrom(sandbox, data);
    assertMatch(code, /Linea uno<br>Linea dos/, 'al re-emitir, el salto de linea debe volver a <br> (esc())');
  });

  test('regresion: el cilindro [( )] se reconoce y se re-emite igual', () => {
    const { sandbox } = fresh();
    const code = roundTrip(sandbox, 'flowchart TD\n    DB[("Base de datos")]');
    assertMatch(code, /DB\[\("Base de datos"\)\]/, 'el cilindro debe sobrevivir el round trip completo');
  });

  test('regresion: flecha punteada con texto en linea -. "txt" .-> se normaliza y se parsea', () => {
    const { sandbox } = fresh();
    const data = parseOk(sandbox, 'flowchart TD\n    A["A"]\n    B["B"]\n    A -. "quiza" .-> B');
    assertEqual(data.edges.length, 1, 'debe reconocer exactamente una arista');
    assertEqual(data.edges[0].style, 'dotted', 'el estilo debe quedar como "dotted"');
    assertEqual(data.edges[0].label, 'quiza', 'la etiqueta en linea debe extraerse del texto');
  });

  test('regresion: flecha gruesa ==> se reconoce', () => {
    const { sandbox } = fresh();
    const data = parseOk(sandbox, 'flowchart TD\n    A["A"]\n    B["B"]\n    A ==> B');
    assertEqual(data.edges[0].style, 'thick', 'debe reconocer ==> como estilo "thick"');
  });

  test('regresion: multidestino "A & B --> C" produce el producto cartesiano de aristas', () => {
    const { sandbox } = fresh();
    const data = parseOk(sandbox, 'flowchart TD\n    A["A"]\n    B["B"]\n    C["C"]\n    A & B --> C');
    assertEqual(data.edges.length, 2, '"A & B --> C" debe producir 2 aristas (A->C, B->C)');
    const pares = data.edges.map((e) => e.from + '->' + e.to).sort();
    assertDeepEqual(pares, ['A->C', 'B->C'], 'los pares deben ser exactamente A->C y B->C');
  });

  test('regresion: normalizeLinks no toca una flecha compacta sin texto en linea', () => {
    const { sandbox } = fresh();
    const linea = 'A --> B';
    const out = callFn(sandbox, 'normalizeLinks', linea);
    assertEqual(out, linea, 'una flecha compacta debe quedar intacta');
  });

  test('regresion: splitAmp respeta corchetes, parentesis y comillas', () => {
    const { sandbox } = fresh();
    const out = callFn(sandbox, 'splitAmp', 'A["x & y"] & B');
    assertDeepEqual(out, ['A["x & y"]', 'B'], 'el & dentro de comillas/corchetes no debe partir la cadena');
  });

  test('regresion: parseShape reconoce las 8 formas por su regex', () => {
    const { sandbox } = fresh();
    const casos = [
      ['["Texto"]', 'rect'], ['(["Texto"])', 'stadium'], ['[["Texto"]]', 'subroutine'],
      ['[("Texto")]', 'cylinder'], ['(("Texto"))', 'circle'], ['{{"Texto"}}', 'hexagon'],
      ['("Texto")', 'round'], ['{"Texto"}', 'diamond'],
    ];
    for (const [rest, esperado] of casos) {
      const r = callFn(sandbox, 'parseShape', rest);
      assertEqual(r && r.shape, esperado, 'parseShape("' + rest + '") debe devolver shape="' + esperado + '"');
    }
  });

  test('regresion: etiqueta de arista via tuberia |"texto"| se reconoce', () => {
    const { sandbox } = fresh();
    const data = parseOk(sandbox, 'flowchart TD\n    A["A"]\n    B["B"]\n    A -->|"Si"| B');
    assertEqual(data.edges[0].label, 'Si', 'la etiqueta con tuberia debe extraerse');
  });
};
