# Handoff de implementacion: fase 3 (vertical minimo de memoria)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus/Fable), rol disenador.
Verificacion: Opus (e2e final contra core real en laboratorio).
Base: `main` con fase 2 integrada (PR #1).

Lee antes: `AGENTS.md` (orden completo), `docs/POLITICA_WRITEBACK.md`,
ADR 0006, `docs/FORMA_ENRIQUECIMIENTO.md`. Ante ambiguedad: PARA y pregunta.

## Objetivo

El bucle completo envolviendo `prompt.run` del core (REST, via 2):
`enrich(identity, prompt)` -> recall -> componer -> core -> write-back ->
respuesta. Con telemetria propia. El core NO se toca.

## Dentro de fase 3

1. **Config de la capa** (env vars con prefijo `IANEST_EXTENDED_`, mas
   `.env.example` actualizado): `CORE_URL` (default `http://127.0.0.1:8000`),
   `OLLAMA_URL` (default `http://127.0.0.1:11434`), `EMBEDDING_MODEL`
   (`bge-m3`), `EMBEDDING_DIMENSION` (`1024`), `EXTRACTION_MODEL`
   (`qwen2.5:7b`), `TELEMETRY_DIR` (default `telemetry/`), y los numeros de
   composicion (budget, k por tier, umbral dedup 0.92, umbral confianza 0.7).

2. **`OllamaEmbedder`** (adaptador del port `Embedder`): API de embeddings de
   Ollama, vector normalizado, dimension validada contra config; errores
   tipados; timeout.

3. **`CoreClient`** (REST): `prompt_run(prompt, identity, model=None)` contra
   el core; propaga identidad completa; devuelve respuesta + traza (incluye
   `request_id` y `finish_reason`); errores tipados; timeout configurable.

4. **`enrich`** (el vertical): recall por identidad (gates + ranking de fase 2,
   k y presupuesto de `POLITICA_WRITEBACK.md`), composicion del bloque de
   memoria (orden: delegadas -> semantic -> episodic -> dialog pegado al
   prompt; presupuesto aproximado por caracteres/4; recorte del peor-rankeado),
   llamada al core, write-back segun `POLITICA_WRITEBACK.md` (dialog siempre;
   extraccion JSON con modelo declarado; confianza >= 0.7; dedup-refuerzo
   >= 0.92; menciones a `unresolved_mentions`; JSON invalido -> descartar y
   telemetria). Devuelve la respuesta del core y su traza.

5. **Soporte de store**: metodo de refuerzo (`stability+1`,
   `last_reinforced_at`) y busqueda de similar para dedup (mismo user+ns,
   umbral). Sin tocar el esquema salvo necesidad minima documentada.

6. **Telemetria JSONL** (espejo del espiritu core ADR 0010/0015): fichero
   diario en `TELEMETRY_DIR`, eventos `enrich.recall` y `enrich.write_back`
   con: timestamp, `request_id` propio, `core_request_id`, identidad completa,
   contadores (k pedidos/devueltos por tier, items extraidos/escritos/
   reforzados/descartados), `latency_ms`, `status`. Una linea por evento.

7. **CLI minima**: `python -m ianest_extended.chat --user U --session S
   [--domain D] "texto"` -> imprime la respuesta; flag `--show-context` para
   ver el bloque de memoria inyectado (depuracion).

8. **Instalador (extension de fase 2b)**: flags `--embedding-model`,
   `--extraction-model`, `--core-url`, `--ollama-url` con los recomendados por
   defecto; en modo interactivo PREGUNTA estos valores (con el recomendado
   propuesto); escribe/actualiza el `.env` de la instalacion; `--pull-models`
   opcional hace `ollama pull` SOLO si Ollama es alcanzable. `--assume-yes`
   toma recomendados sin preguntar.

9. **Tests**:
   - Unit/integration con **stub del core** (servidor HTTP local deterministra
     en tests: responde `prompt.run` con eco verificable y traza sintetica) y
     `FakeEmbedder`; DB con el patron skip de fase 2.
   - Aceptacion (con DB local + stub core): (a) continuidad: item de
     preferencia escrito en sesion A aparece en el bloque de memoria compuesto
     en sesion B (mismo user); (b) anti-ruido: turno smalltalk (extraccion
     stub devuelve cero items) escribe dialog y cero episodic; (c) refuerzo:
     repetir un hecho no duplica, incrementa `stability`; (d) telemetria: ambos
     eventos por interaccion, enlazados por `request_id`.
   - El e2e contra core+Ollama reales NO se automatiza aqui: lo hace el
     disenador en laboratorio.

## Fuera de fase 3 (NO implementar)

- Consolidacion/promocion, archivado por TTL, evento `memory.consolidation`
  (fase 4). RAG y web (fases 5/6). Contrato publico/REST propio (fase 7).
- Cambios en el core o su configuracion. Resolucion de entidades.
- CSV agregado de telemetria (diferido con nombre).

## Restricciones

- Sin comandos git (sandbox); commits del disenador. ASCII en prosa;
  identificadores en ingles; errores tipados; repo publico sin datos internos.
- No conectes a hosts remotos: stub del core y FakeEmbedder en tests; URLs
  reales solo desde config en runtime.

## Blanco de aceptacion

- pytest en verde con DB local (skips sin DB, como fase 2); los cuatro tests
  de aceptacion (a)-(d) pasando.
- `./install.sh --skip-db --assume-yes` sigue verde e idempotente con la
  extension de config.
- `bash -n install.sh` limpio; ASCII limpio.

## Entrega

Ficheros en la rama activa; nota en `docs/handoff/fase_3_entrega.md`
(decisiones, dudas, inconsistencias senaladas, estado de pytest, entrada de
CHANGELOG anadida bajo No publicado).
