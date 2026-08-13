# Entrega de implementacion: fase 5c (workflow de conocimiento)

Fecha: 2026-08-13

## Resultado

Implementado el workflow de operador pedido en
`docs/handoff/fase_5c_brief.md`:

- `python -m ianest_extended.knowledge status` consulta `domain.list`, excluye
  `general`, cuenta corpus activos con vinculo confirmado y marca los huecos.
- `suggest --corpus NAME` concatena una muestra estable de chunks, llama a
  `domain.route` y guarda el dominio principal y alternativas que alcanzan el
  umbral como `source=auto`, `confirmed=false`.
- `confirm --corpus NAME --domain D` valida D contra el catalogo del core y
  confirma un vinculo existente de forma idempotente.
- `reject --corpus NAME --domain D` elimina solo propuestas auto no confirmadas;
  repetir sobre un vinculo ausente es idempotente y los vinculos manuales o
  confirmados producen `ProtectedKnowledgeLinkError`.

La sugerencia usa upsert condicionado: puede refrescar la confianza de una
propuesta auto pendiente, pero no pisa un vinculo manual ni confirmado. La
recuperacion no cambia: solo los vinculos confirmados gatean conocimiento.

## Configuracion

Anadidas a `ExtendedConfig`, `.env.example` e instalador:

- `IANEST_EXTENDED_RAG_SUGGEST_MIN_CONFIDENCE=0.6`
- `IANEST_EXTENDED_RAG_SUGGEST_SAMPLE_CHARS=2000`

## Pruebas

- `pytest`: 35 passed, 24 skipped. Los cuatro casos PostgreSQL de Fase 5c se
  omiten porque no hay DB local, siguiendo el patron `<dbname>_test` de Fase 3.
- `./install.sh --skip-db --assume-yes`: VERDE; reutiliza `.venv`, actualiza la
  configuracion de forma idempotente y obtiene el mismo resultado de pytest.
- `bash -n install.sh`: VERDE.
- Compilacion de modulos Python: VERDE.
- Prosa y ficheros modificados: ASCII limpio.

## Decisiones y limites

- La muestra se ordena por `source_ref`, `ordinal` y desempates estables antes
  de truncarse al limite configurable.
- `general` no genera propuestas: es el dominio agnostico y no representa un
  vinculo de gate.
- Alternativas mal formadas o fuera del catalogo se ignoran; un dominio
  principal fuera del catalogo es una respuesta invalida del core.
- La telemetria opcional `knowledge.suggest` no se anadio: no era necesaria para
  el blanco de aceptacion y evita ampliar el cableado del CLI.
- Sin cambios de esquema: Fase 5c opera sobre `rag_corpus_domains` de Fase 5b.
- Fuera de fase respetado: sin clasificacion por chunk, `knowledge maintain`,
  re-etiquetado, roles/grants, cambios en memoria, core o contrato publico.

## Dudas e inconsistencias

Ninguna detectada. Impacto SemVer: ninguno; el contrato publico sigue pendiente
de Fase 7.
