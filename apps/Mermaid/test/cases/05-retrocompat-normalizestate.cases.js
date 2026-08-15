'use strict';
/*
 * Prioridad 5 (ADR-0004 D5, D6, D1, criterio A3): retrocompatibilidad de los
 * .layout.json viejos (version 1, sin groups, con la clave vieja "color") y
 * el contrato de normalizeState como unica puerta de entrada al estado.
 *
 * Usa como fixtures los DOS .layout.json reales que ya existen en
 * graphs/ (SDG y "OPC Office"), tal como estan hoy en el repo - no se tocan.
 */
module.exports = function (t) {
  const { test, fresh, callFn, fs, path, MERMAID_DIR, assertEqual, assertTrue, assertDeepEqual } = t;

  const GRAPHS_DIR = path.join(MERMAID_DIR, 'graphs');

  function loadFixture(name) {
    const raw = fs.readFileSync(path.join(GRAPHS_DIR, name), 'utf8');
    return JSON.parse(raw);
  }

  test('A3: SDG.layout.json (v1, sin groups) normaliza sin perder nodos ni aristas', () => {
    const { sandbox } = fresh();
    const layout = loadFixture('SDG.layout.json');
    assertEqual(layout.version, 1, 'fixture de control: SDG.layout.json debe seguir siendo v1 (si esto falla, Atlas ya la resalvo y hay que renovar el fixture)');
    const normalized = callFn(sandbox, 'normalizeState', layout.state);
    assertTrue(Array.isArray(normalized.groups), 'normalizeState debe rellenar groups:[] si falta (D6)', normalized.groups);
    assertEqual(normalized.groups.length, 0, 'SDG no tenia grupos: la lista debe quedar vacia, no perderse');
    assertEqual(normalized.nodes.length, layout.state.nodes.length, 'no debe perderse ningun nodo al normalizar (' + layout.state.nodes.length + ' en SDG)');
    assertEqual(normalized.edges.length, layout.state.edges.length, 'no debe perderse ninguna arista al normalizar (' + layout.state.edges.length + ' en SDG)');
  });

  test('A3: "OPC Office.layout.json" (v1, sin groups) normaliza sin perder nodos ni aristas', () => {
    const { sandbox } = fresh();
    const layout = loadFixture('OPC Office.layout.json');
    const normalized = callFn(sandbox, 'normalizeState', layout.state);
    assertEqual(normalized.nodes.length, layout.state.nodes.length, 'no debe perderse ningun nodo al normalizar');
    assertEqual(normalized.edges.length, layout.state.edges.length, 'no debe perderse ninguna arista al normalizar');
  });

  test('A3: un nodo con color de paleta ("color":"#3b82f6") conserva su color tras normalizar', () => {
    const { sandbox } = fresh();
    const layout = loadFixture('SDG.layout.json');
    const original = layout.state.nodes.find((n) => n.color && n.color !== 'default');
    assertTrue(!!original, 'fixture de control: debe existir al menos un nodo con color de paleta en SDG', layout.state.nodes.slice(0, 3));
    const normalized = callFn(sandbox, 'normalizeState', layout.state);
    const migrado = normalized.nodes.find((n) => n.id === original.id);
    assertTrue(!!migrado.colors, 'el nodo "' + original.id + '" debe tener colors{} tras migrar desde color:"' + original.color + '" (D5)', migrado);
    assertTrue(!('color' in migrado), 'la clave vieja "color" debe desaparecer tras migrar (D5)', migrado);
  });

  test('D5: migracion perezosa color (paleta) -> colors {fill,stroke,strokeWidth}', () => {
    const { sandbox } = fresh();
    const s = { dir: 'TD', seq: 1, nodes: [{ id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, color: '#3b82f6' }], edges: [] };
    const n = callFn(sandbox, 'normalizeState', s);
    const n1 = n.nodes.find((x) => x.id === 'N1');
    assertTrue(!('color' in n1), 'la clave vieja "color" debe desaparecer tras migrar (D5)', n1);
    assertTrue(!!n1.colors, 'debe aparecer "colors" (D5)', n1);
    assertEqual(n1.colors.fill, '#dbeafe', 'preset azul en NODE_COLORS: [\'#3b82f6\',\'#dbeafe\'] -> fill=#dbeafe (D5, "no es #3b82f6 el relleno")');
    assertEqual(n1.colors.stroke, '#3b82f6', 'preset azul: stroke = #3b82f6 (D5)');
    assertEqual(n1.colors.strokeWidth, '2px', 'D5: strokeWidth por defecto 2px al migrar');
  });

  test('D5: color:"default" migra a SIN colors (no a un colors{} vacio)', () => {
    const { sandbox } = fresh();
    const s = { dir: 'TD', seq: 1, nodes: [{ id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, color: 'default' }], edges: [] };
    const n = callFn(sandbox, 'normalizeState', s);
    const n1 = n.nodes.find((x) => x.id === 'N1');
    assertTrue(!n1.colors, 'color:"default" no debe generar un colors{} vacio (D5: "color:\'default\' -> sin colors")', n1);
  });

  test('D6: normalizeState es idempotente (aplicarla dos veces = aplicarla una)', () => {
    const { sandbox } = fresh();
    const s = { dir: 'TD', seq: 1, nodes: [{ id: 'N1', shape: 'rect', label: 'Uno', x: 0, y: 0, w: 100, h: 52, color: '#3b82f6' }], edges: [], groups: [{ id: 'G1', label: 'G' }] };
    const once = callFn(sandbox, 'normalizeState', s);
    const twice = callFn(sandbox, 'normalizeState', once);
    assertDeepEqual(twice, once, 'normalizeState(normalizeState(s)) debe ser identico a normalizeState(s) (D6)');
  });

  test('D6: un parent de nodo que apunta a un grupo inexistente se borra (no cuelga el render)', () => {
    const { sandbox } = fresh();
    const s = { dir: 'TD', seq: 1, nodes: [{ id: 'N1', shape: 'rect', label: 'U', x: 0, y: 0, w: 100, h: 52, parent: 'Fantasma' }], edges: [], groups: [] };
    const n = callFn(sandbox, 'normalizeState', s);
    assertTrue(!n.nodes[0].parent, 'un parent que apunta a un grupo inexistente debe borrarse (D6, R8)', n.nodes[0]);
  });

  test('D6: un ciclo de parent entre grupos se rompe (no cuelga el render recursivo)', () => {
    const { sandbox } = fresh();
    const s = { dir: 'TD', seq: 1, nodes: [], edges: [], groups: [{ id: 'G1', label: 'G1', parent: 'G2' }, { id: 'G2', label: 'G2', parent: 'G1' }] };
    const n = callFn(sandbox, 'normalizeState', s);
    const g1 = n.groups.find((g) => g.id === 'G1');
    const g2 = n.groups.find((g) => g.id === 'G2');
    const sigueCiclico = g1.parent === 'G2' && g2.parent === 'G1';
    assertTrue(!sigueCiclico, 'el ciclo G1->G2->G1 debe romperse en al menos un extremo (D6, R8)', { g1, g2 });
  });

  test('D1: invariante de anchor - un grupo con hijos NO conserva anchor', () => {
    const { sandbox } = fresh();
    const s = { dir: 'TD', seq: 1, nodes: [{ id: 'N1', shape: 'rect', label: 'U', x: 0, y: 0, w: 100, h: 52, parent: 'G1' }], edges: [], groups: [{ id: 'G1', label: 'G1', anchor: { x: 300, y: 500 } }] };
    const n = callFn(sandbox, 'normalizeState', s);
    const g1 = n.groups.find((g) => g.id === 'G1');
    assertTrue(!g1.anchor, 'en cuanto el grupo gana un hijo, normalizeState debe borrar el anchor (D1: "anchor existe si y solo si el grupo no tiene descendientes")', g1);
  });

  test('D1: un grupo SIN hijos conserva su anchor (criterio A8, grupo vacio)', () => {
    const { sandbox } = fresh();
    const s = { dir: 'TD', seq: 1, nodes: [], edges: [], groups: [{ id: 'G1', label: 'G1', anchor: { x: 300, y: 500 } }] };
    const n = callFn(sandbox, 'normalizeState', s);
    const g1 = n.groups.find((g) => g.id === 'G1');
    assertDeepEqual(g1.anchor, { x: 300, y: 500 }, 'un grupo vacio SI debe conservar su anchor (D1) - es el unico dato que hay');
  });

  test('D6: hex de colors se normaliza a 6 digitos minuscula al entrar (necesario para classNameFor)', () => {
    const { sandbox } = fresh();
    const s = { dir: 'TD', seq: 1, nodes: [{ id: 'N1', shape: 'rect', label: 'U', x: 0, y: 0, w: 100, h: 52, colors: { fill: '#FFF', stroke: '#ABC' } }], edges: [] };
    const n = callFn(sandbox, 'normalizeState', s);
    const n1 = n.nodes.find((x) => x.id === 'N1');
    assertEqual(n1.colors.fill, '#ffffff', 'un hex de 3 digitos en mayuscula debe normalizarse a 6 digitos minuscula (D6/S2, "sin esto el nombre de clase no seria determinista")');
    assertEqual(n1.colors.stroke, '#aabbcc', 'idem para stroke');
  });
};
