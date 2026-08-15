'use strict';
/*
 * Prioridad 1 (ADR-0004 S4): el ida-y-vuelta idempotente y el punto fijo.
 * A1 (ida y vuelta), A2 (punto fijo desde la SEGUNDA pasada, no identidad
 * con la entrada - ver la correccion del encargo), A2b (nombre estable ante
 * insercion) y A10 (recarga del propio .mmd generado).
 *
 * Nacen en ROJO con el editor.js de hoy: no hay groups, subgraph, classDef
 * ni class. Es lo esperado mientras Atlas construye la feature.
 */
const XENO_MMD = [
  'flowchart LR',
  '    A["Alpha"]',
  '    B["Beta"]',
  '    subgraph G1["Grupo Uno"]',
  '        C["Gamma"]',
  '        D["Delta"]',
  '    end',
  '    A --> B',
  '    B --> C',
  '    C --> D',
  '    style A fill:#c62828,stroke:#6b1414,stroke-width:2px,color:#ffffff',
  '    classDef bs_c62828_6b1414_ffffff fill:#c62828,stroke:#6b1414,stroke-width:2px,color:#ffffff',
  '    class G1 bs_c62828_6b1414_ffffff',
].join('\n');

module.exports = function (t) {
  const { test, fresh, callFn, parseOk, buildFrom, roundTrip, assertEqual, assertTrue, assertDeepEqual } = t;

  test('A1-lite: ida y vuelta conserva nodos, aristas y grupos (arrastre queda para E2E)', () => {
    const { sandbox } = fresh();
    const d1 = parseOk(sandbox, XENO_MMD);
    assertEqual(d1.nodes.length, 4, 'deben reconocerse los 4 nodos (A,B,C,D)');
    assertEqual(d1.edges.length, 3, 'deben reconocerse las 3 aristas');
    assertTrue(Array.isArray(d1.groups), 'parseCode debe devolver data.groups (ADR-0004 S2, S3 paso 12)', d1);
    assertEqual(d1.groups.length, 1, 'debe reconocerse el subgraph G1 como un grupo');

    const c1 = buildFrom(sandbox, d1);
    const d2 = parseOk(sandbox, c1);
    assertEqual(d2.nodes.length, d1.nodes.length, 'el numero de nodos no debe cambiar tras un ciclo completo');
    assertEqual(d2.edges.length, d1.edges.length, 'el numero de aristas no debe cambiar tras un ciclo completo');
    assertEqual(d2.groups.length, d1.groups.length, 'el numero de grupos no debe cambiar tras un ciclo completo');
  });

  test('A2: punto fijo desde la SEGUNDA pasada (no identidad con la entrada)', () => {
    const { sandbox } = fresh();
    // c1 = buildCode(parseCode(x))
    const c1 = roundTrip(sandbox, XENO_MMD);
    // c2 = buildCode(parseCode(buildCode(parseCode(x))))  =  roundTrip(c1)
    const c2 = roundTrip(sandbox, c1);
    assertEqual(c2, c1, 'buildCode(parseCode(buildCode(parseCode(x)))) debe ser BYTE-IDENTICO a buildCode(parseCode(x)). ' +
      'OJO: no se compara c1 contra el XENO_MMD original (las clases ajenas se disuelven, ADR S2bis) - el punto fijo se exige desde la 2a pasada.');
  });

  test('A2b: anadir un grupo nuevo NO cambia el nombre de clase de los que ya estaban', () => {
    const { sandbox } = fresh();
    const antes = {
      dir: 'LR', seq: 5,
      nodes: [{ id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, parent: 'G1' }],
      edges: [],
      groups: [{ id: 'G1', label: 'Uno', colors: { fill: '#c62828', stroke: '#6b1414', text: '#ffffff' } }],
    };
    const codeAntes = buildFrom(sandbox, antes);
    const nombreAntes = (codeAntes.match(/classDef\s+(\S+)/) || [])[1];
    assertTrue(!!nombreAntes, 'debe haber al menos un classDef para el grupo G1', codeAntes);

    const despues = {
      dir: 'LR', seq: 9,
      nodes: [
        { id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, parent: 'G1' },
        { id: 'N2', shape: 'rect', label: 'Dos', x: 0, y: 0, w: 100, h: 52, parent: 'G2' },
      ],
      edges: [],
      groups: [
        { id: 'G1', label: 'Uno', colors: { fill: '#c62828', stroke: '#6b1414', text: '#ffffff' } },
        { id: 'G2', label: 'Dos', colors: { fill: '#22c55e', stroke: '#166534', text: '#ffffff' } },
      ],
    };
    const codeDespues = buildFrom(sandbox, despues);
    assertTrue(codeDespues.includes('classDef ' + nombreAntes + ' '), 'el classDef de G1 debe seguir llamandose "' + nombreAntes + '" tras anadir G2 (ADR S2bis, criterio A2b)', codeDespues);
  });

  test('A2b (borrado): quitar un grupo NO cambia el nombre de clase del que queda', () => {
    const { sandbox } = fresh();
    const conDos = {
      dir: 'LR', seq: 9,
      nodes: [
        { id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, parent: 'G1' },
        { id: 'N2', shape: 'rect', label: 'Dos', x: 0, y: 0, w: 100, h: 52, parent: 'G2' },
      ],
      edges: [],
      groups: [
        { id: 'G1', label: 'Uno', colors: { fill: '#c62828', stroke: '#6b1414', text: '#ffffff' } },
        { id: 'G2', label: 'Dos', colors: { fill: '#22c55e', stroke: '#166534', text: '#ffffff' } },
      ],
    };
    const codeConDos = buildFrom(sandbox, conDos);
    const nombreG1 = (codeConDos.match(/class\s+G1\s+(\S+)/) || [])[1];
    assertTrue(!!nombreG1, 'debe existir una linea "class G1 <nombre>"', codeConDos);

    const soloUno = {
      dir: 'LR', seq: 9,
      nodes: [{ id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, parent: 'G1' }],
      edges: [],
      groups: [{ id: 'G1', label: 'Uno', colors: { fill: '#c62828', stroke: '#6b1414', text: '#ffffff' } }],
    };
    const codeSoloUno = buildFrom(sandbox, soloUno);
    assertTrue(codeSoloUno.includes('classDef ' + nombreG1 + ' '), 'al borrar G2, el classDef de G1 debe seguir llamandose "' + nombreG1 + '" (funcion pura del contenido)', codeSoloUno);
  });

  test('A10: el .mmd generado por la propia herramienta recupera el color del grupo al pegarlo de nuevo', () => {
    const { sandbox } = fresh();
    const estado = {
      dir: 'LR', seq: 10,
      nodes: [{ id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, parent: 'G1' }],
      edges: [],
      groups: [{ id: 'G1', label: 'Grupo', colors: { fill: '#c62828', stroke: '#6b1414', text: '#ffffff' } }],
    };
    const code = buildFrom(sandbox, estado);
    assertTrue(/classDef\s+bs_c62828_6b1414_ffffff/.test(code), 'buildCode debe emitir un classDef para el grupo con color (ADR S2bis)', code);
    assertTrue(/class\s+G1\s+bs_c62828_6b1414_ffffff/.test(code), 'buildCode debe emitir "class G1 <nombre>" (ADR S2)', code);

    const parsed = parseOk(sandbox, code);
    const g1 = parsed.groups.find((g) => g.id === 'G1');
    assertTrue(!!g1, 'el grupo G1 debe sobrevivir al reparseo del propio .mmd generado', parsed.groups);
    assertEqual(g1.colors && g1.colors.fill, '#c62828', 'el fill del grupo debe recuperarse via classDef+class (criterio A10)');
    assertEqual(g1.colors && g1.colors.stroke, '#6b1414', 'el stroke del grupo debe recuperarse via classDef+class (criterio A10)');
    // El texto puede venir explicito o derivarse (D5): se compara el efectivo,
    // no la representacion exacta almacenada (ver informe final, punto abierto).
    const textoEfectivo = (g1.colors && g1.colors.text) || callFn(sandbox, 'textOn', g1.colors.fill);
    assertEqual(textoEfectivo, '#ffffff', 'el texto (guardado o derivado) debe seguir siendo claro sobre #c62828 - si sale negro es la regresion medida en S2bis');
  });
};
