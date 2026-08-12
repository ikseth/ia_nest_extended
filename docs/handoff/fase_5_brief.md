# Handoff de implementacion: fase 5 (RAG operativo, camino upfront)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus/Fable), rol disenador.
Verificacion: Opus (e2e final contra core+Ollama reales en laboratorio).
Base: `main` con fases 2-4 integradas.

Lee antes: `AGENTS.md` (orden completo), ADR 0008, `docs/VISION_MEMORIA.md`
(RAG hermano, no tier), `docs/FORMA_ENRIQUECIMIENTO.md`, `docs/POLITICA_WRITEBACK.md`
(composicion del recall, para integrar el RAG en el mismo presupuesto).
Ante ambiguedad: PARA y pregunta.

## Objetivo

Sustrato de RAG operativo (corpus por dominio) + su integracion UPFRONT en el
enriquecimiento de `prompt.run`. Solo lectura; el RAG no es memoria. El core no
se toca. El camino per-subtarea (`task.run`/`task.plan`) queda FUERA (diferido a
core v0.4).

## Dentro de fase 5

1. **Esquema** (migracion SQL nueva en `db/migrations/`, sin tocar las tablas de
   memoria):
   - `rag_corpora`: `id` (uuid), `name`, `domain`, `description`, `status`
     (`active|archived`), `version`, `created_at`.
   - `rag_chunks`: `id` (uuid), `corpus_id` (fk), `content`, `embedding`
     (`vector(D)`, misma D que la config de memoria), `source_ref`, `ordinal`
     (int), `created_at`. Unico por (`corpus_id`, `source_ref`, `ordinal`)
     (ingesta idempotente).

2. **Ingesta** (`python -m ianest_extended.ingest --corpus NAME --domain D
   [--source-ref REF] PATH`): lee texto (fichero o directorio de `.txt`/`.md`),
   trocea (tamano y solape configurables), embebe con el `Embedder` (real
   `OllamaEmbedder` en runtime; `FakeEmbedder` en tests), inserta chunks. Crea el
   corpus si no existe. Re-ingestar el mismo `source_ref` no duplica (upsert por
   la clave unica). Resumen final: corpus, chunks nuevos/actualizados.

3. **Recuperacion** (`RagStore.retrieve(query_text, domain=None, top_k, ...)`):
   - gate: si `domain` dado, filtra `rag_corpora.domain = domain` (solo corpus
     `active`); si no, todos los corpus activos.
   - orden: similitud coseno del embedding de `query_text` contra `rag_chunks`.
   - devuelve top_k chunks con su score y corpus/dominio.

4. **Resolucion de dominio** (D2), en la config/flujo de enriquecimiento:
   - explicito: si el caller pasa dominio, se usa;
   - auto-route (opcional, flag): si no hay dominio y esta activado, extended
     llama a `domain.route` del core (nuevo metodo en `CoreClient`) y usa el
     dominio devuelto si la confianza supera un umbral configurable; si no,
     sin dominio (similitud global).

5. **Integracion upfront** en `enrich` (ampliar el flujo de fase 3): tras
   resolver dominio, recuperar RAG y anadir un bloque RAG a la composicion del
   prompt, DENTRO del presupuesto de `POLITICA_WRITEBACK.md`. Orden de secciones:
   delegadas -> RAG -> semantic -> episodic -> dialog + prompt del usuario.
   Presupuesto (D3, conservador, configurable):
   - conteo de tokens conservador (aprox. 3.5 caracteres por token; no infravalorar);
   - `RAG_TOP_K` por defecto 3, `RAG_MAX_TOKENS` por defecto ~500;
   - recorte bajo presupuesto: cae primero el RAG (peor score), luego `episodic`;
     NUNCA las delegadas ni el prompt del usuario.

6. **Config** (`.env.example` + `ExtendedConfig`): `RAG_ENABLED` (bool),
   `RAG_TOP_K`, `RAG_MAX_TOKENS`, `RAG_CHUNK_TOKENS` (~300), `RAG_CHUNK_OVERLAP`
   (~0.15), `RAG_AUTO_DOMAIN` (bool), `RAG_AUTO_DOMAIN_MIN_CONFIDENCE`.

7. **Telemetria**: evento `rag.retrieve` (JSONL) con dominio, k pedido/devuelto,
   corpus tocados, latencia, si hubo auto-route y su confianza.

8. **Instalador** (extension menor): flags/preguntas para `RAG_*` con
   recomendados; y CORRIGE el roce detectado: el default de
   `IANEST_EXTENDED_EXTRACTION_MODEL` en `.env.example` debe documentar que es el
   ID del modelo en el CORE (p.ej. `qwen_tech` en el lab), no el tag de Ollama;
   si el core responde, sugiere ids via `model.list`.

9. **Tests** (patron fases 2-4: DB `<dbname>_test`, skip sin DB; stub del core y
   `FakeEmbedder`):
   - Ingesta idempotente: re-ingestar mismo `source_ref` no duplica.
   - Gate de dominio: chunk de corpus `linux` se recupera con `domain=linux`; NO
     aparece con `domain=cocina` (anti-colision); sin dominio, aparece por
     similitud.
   - Presupuesto: con presupuesto pequeno, el bloque RAG se recorta antes que el
     resto; las delegadas y el prompt del usuario nunca se recortan.
   - Integracion: con dominio y corpus, el prompt compuesto (stub core) incluye
     la seccion RAG; sin corpus del dominio, no aparece y el resto sigue igual.
   - auto-route: con `RAG_AUTO_DOMAIN` y stub de `domain.route`, se usa el
     dominio devuelto sobre el umbral; por debajo, similitud global.

## Fuera de fase 5 (NO implementar)

- RAG per-subtarea en `task.run` / `task.plan` (diferido a core v0.4, ADR 0040).
- RAG etico/filosofico (es de conscience).
- Reindexado/migracion de dimension de RAG (reusa la D de memoria; si difiere,
  documentar, no construir).
- Cambios en el core, en las tablas de memoria, o en el contrato publico (fase 7).

## Restricciones

Sin comandos git (sandbox); commits del disenador. ASCII en prosa;
identificadores en ingles snake_case; errores tipados; repo publico sin datos
internos. Sin hosts remotos en tests (stub del core, FakeEmbedder); URLs reales
solo desde config en runtime.

## Blanco de aceptacion

- pytest en verde con DB local (skips sin DB); los cinco grupos de tests
  pasando.
- `./install.sh --skip-db --assume-yes` sigue verde e idempotente con la
  config RAG.
- `bash -n install.sh` y ASCII limpios.

## Entrega

Ficheros en la rama activa; nota en `docs/handoff/fase_5_entrega.md` (decisiones,
dudas, inconsistencias senaladas, estado de pytest, entrada de CHANGELOG bajo No
publicado).
