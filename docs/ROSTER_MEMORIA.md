# Roster de tipos de memoria (Fase 2)

Estado: RECONCILIADO
Version: 0.2 - 2026-07-18

Instancia concreta del mecanismo: clases y autoridad (ADR 0002), tiers y
relevancia (ADR 0003), entities y multi-espacio (ADR 0004), disolucion de
historic (ADR 0005). Cada fila es una declaracion del registro de tipos;
`memory_type.validate` exige que no haya dos filas coincidentes en TODOS sus
ejes (modo de recuperacion, dueno, scope, namespace): eso seria aliasing
(Leccion 1). Dos tipos pueden compartir tier si difieren en otro eje.

## Tipos estrictos (dueno de escritura: extended)

| Tipo | Tier / patron | Scope | Namespaces | Escritura | H |
|---|---|---|---|---|---|
| `dialog` | conversacional | `session_id` | (crudo, sin ns) | write-back directo de turnos | ~4 h |
| `episodic` | episodica | `user_id` | `facts`, `tasks`, `preferences` | write-back con politica (dedup, filtro anti-ruido) + `entity_refs` | ~30 d |
| `semantic` | semantica | `user_id` | `facts`, `preferences` | solo consolidacion (Fase 4), comprimida | off |

Notas:

- `dialog` guarda los turnos de la sesion tal cual; el etiquetado y la
  destilacion a `episodic` los hace el write-back, no el dialogo mismo.
- `tasks` no asciende a `semantic`: los compromisos se completan o expiran, no
  se sedimentan (el patron que revele una tarea repetida es un `fact`).
- Los vectores de pesos y H son los del ADR 0003, configurables por registro.

## Tipos delegados (declarados; dueno de escritura: conscience)

| Tipo | Patron | Modo de recuperacion | Scope | Contenido |
|---|---|---|---|---|
| `entities` | perfil mutable versionado (no decae, se actualiza) | lookup de perfil; gate por `entity_ref` | `entity_id` propio | perfiles de personas, proyectos, objetos |
| `identity` | sedimento versionado | inyeccion permanente | entidad global | quien soy, que hago; el yo del ente (ns `persona`) |
| `principles` | registro evolutivo versionado | inyeccion permanente | entidad global | criterios/valores/heuristicas con refuerzo y estados |
| `safety` | sedimento | inyeccion permanente | `user_id` | limites y salvaguardas por usuario |

Notas:

- PERSONALIDAD = `identity` + `principles` (ADR 0005): el estado actual del yo,
  inyectado siempre en contexto (system prompt por perfil, core ADR 0025).
- No hay tipo `historic` (ADR 0005): la evidencia formativa son `evidence_refs`
  desde `identity`/`principles` hacia engramas (vivos o archivados; el archivo
  es direccionable porque no hay borrado fisico). El relato formativo por
  relevancia queda diferido con nombre.
- Ninguna delegada usa el ranking del ADR 0003: se inyectan o se consultan.
- Declarados y vacios hasta que conscience exista (ADR 0002): el retrieval los
  ve vacios y sigue; no hay logica especulativa construida. El dueno podra
  ajustar scope y politica dentro de los railes del registro.
- Extended etiqueta `entity_refs` inequivocos en el write-back (mecanico); el
  perfil de `entities` y la resolucion de ambiguedades son juicio del dueno.

## Fuera del roster

- `ops`: telemetria/operacional (core ADR 0010/0015), no memoria. Esta capa la
  EMITE (Fase 3), no la recuerda.
- Conocimientos (RAG): subsistema hermano (Fase 5), no un tipo de memoria
  (`docs/VISION_MEMORIA.md`).

## Dependencias de implementacion (Fase 2/3)

- Motor: `postgres + pgvector` (ADR 0003).
- Modelo de embeddings y dimensionalidad: por decidir (servible por Ollama).
- Diferidas con nombre (ADR 0004): grafo de asociacion entre entidades,
  asociacion temporal por ventana.
