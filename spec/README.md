<!-- GENERADO por .claude/tools/docs-index.mjs — no editar a mano. Regenera con:
     node .claude/tools/docs-index.mjs -->

# Documentación — Tools

Raíz única: toda la documentación del proyecto vive bajo `spec/`, partida por **audiencia** (ADR-0042
D2): la **mesa del dueño** (set cerrado, ≤10 archivos — `fichas-gate.mjs --mesa`) y la **zona de
consulta** (todo lo demás, audiencia agentes). `spec/backlog/backlog.md` (el backlog permanente) NO
aparece aquí: es estado vivo, no un documento con vigencia — léelo directo o con
`fichas-gate.mjs --mesa`/`--olas`.

**Cómo leer este índice.** Todo documento declara su vigencia en el frontmatter.
**Sin `status` = no revisado, no vigente.** Antes de tratar un documento como verdad, mira su
`status`; y si un documento y el código se contradicen, **gana el código**.

| | Significado |
|---|---|
| 🟢 `vigente` | Describe el presente y se puede usar como verdad. |
| 🔵 `construido` | Su contenido ya está implementado; se conserva como especificación de lo que existe. |
| 🟣 `listo-para-construir` | Especificación cerrada, todavía sin implementar. Es trabajo pendiente real. |
| ⚪ `propuesto` | Redactado, esperando aprobación. No lo uses como base. |
| 🟡 `borrador` | Incompleto o con decisiones abiertas. No lo uses como base. |
| 🟠 `parcialmente-derogado` | Parte sigue vigente y parte murió. Lee su `superseded_by` antes de usarlo. |
| 🔴 `derogado` | Ya no describe la realidad. No lo uses; ve a su `superseded_by`. |
| ⚫ `historico` | Registro fechado (auditoría, incidente, parte del día). Cita el pasado a propósito. |

## Mapa de carpetas

| Carpeta | Qué contiene | Audiencia | Docs | Vigentes | Derogados / históricos | Índice |
|---|---|---|---:|---:|---:|---|
| `spec/constitution/` | Misión, principios, roadmap y stack — síntesis derivada de los ADRs | Mesa del dueño | 4 | 0 | 0 | — |
| `spec/guides/` | Manuales de uso, guías funcionales y legal (D2.5, re-domicilia lo que era `docs/`) | Zona de consulta (agentes) | 1 | 0 | 0 | — |
| `spec/operations/` | Runbooks: deploy, rollback, entornos, incidentes, inventario de secretos (D2.5) | Zona de consulta (agentes) | 1 | 0 | 0 | — |

**Total: 6 documentos** (excluido `spec/backlog/backlog.md`, estado vivo). ⚠️ **6 sin `status`** — se consideran no vigentes:
- `spec/constitution/mission.md`
- `spec/constitution/principles.md`
- `spec/constitution/roadmap.md`
- `spec/constitution/tech-stack.md`
- `spec/guides/guia-nueva-herramienta.md`
- `spec/operations/entorno-local.md`

## Todos los documentos

### `spec/constitution/` — Mesa del dueño

| | Documento | Título | KB |
|---|---|---|---:|
| ❓ | [`mission.md`](constitution/mission.md) | Mission — BSTools | 3 |
| ❓ | [`principles.md`](constitution/principles.md) | Principles — BSTools | 3 |
| ❓ | [`roadmap.md`](constitution/roadmap.md) | Roadmap — BSTools | 2 |
| ❓ | [`tech-stack.md`](constitution/tech-stack.md) | Tech Stack — BSTools | 7 |

### `spec/guides/` — Zona de consulta (agentes)

| | Documento | Título | KB |
|---|---|---|---:|
| ❓ | [`guia-nueva-herramienta.md`](guides/guia-nueva-herramienta.md) | Guía — cómo crear una herramienta nueva en BSTools | 13 |

### `spec/operations/` — Zona de consulta (agentes)

| | Documento | Título | KB |
|---|---|---|---:|
| ❓ | [`entorno-local.md`](operations/entorno-local.md) | Entorno de la máquina principal | 1 |
