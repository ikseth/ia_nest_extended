# Handoff de implementacion: fase 5c (workflow de conocimiento)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus/Fable), rol disenador.
Verificacion: Opus (e2e en laboratorio).
Base: `main` con fase 5b (modelo N:M) integrada.

Lee antes: `AGENTS.md`, ADR 0009 (N:M, source/confirmed), ADR 0010 (el
conocimiento lo cura el operador hoy; conscience guardian futuro). Ante
ambiguedad: PARA y pregunta.

## Objetivo

Herramientas de OPERADOR sobre el carril `source`/`confirmed` que ya existe:
chequeo de completitud, auto-sugerencia de dominios via `domain.route`, y
confirmar/rechazar propuestas. Nada autonomo: todo lo invoca el operador; el
gate por `confirmed` de fase 5b sigue protegiendo la recuperacion.

## Dentro de fase 5c

1. **`knowledge status`** (`python -m ianest_extended.knowledge status`):
   consulta los dominios del core (`CoreClient.list_domains()`) y, por cada uno
   salvo `general`, cuenta los corpus con al menos un vinculo `confirmed=true`.
   Reporta que dominios NO tienen conocimiento (huecos). Salida legible; codigo
   de salida 0.

2. **Auto-sugerencia de dominios** (`python -m ianest_extended.knowledge suggest
   --corpus NAME`): toma una muestra del contenido del corpus (concatena hasta N
   caracteres de sus chunks, configurable), la clasifica con
   `CoreClient.domain_route`, y crea vinculos `source='auto'`, `confirmed=false`
   para el dominio elegido y las alternativas por encima de un umbral
   (`RAG_SUGGEST_MIN_CONFIDENCE`, default ~0.6). Idempotente por
   (`corpus_id`, `domain`); NO auto-confirma; NO pisa vinculos `manual` ni
   `confirmed=true` existentes. Resumen: propuestas creadas con su confianza.

3. **Confirmar / rechazar** (`python -m ianest_extended.knowledge confirm|reject
   --corpus NAME --domain D`):
   - `confirm`: pone `confirmed=true` en el vinculo (auto -> confirmado). El
     dominio debe ser valido del core (reusa `list_domains`).
   - `reject`: elimina el vinculo `auto` no confirmado. No toca vinculos
     `manual`/`confirmed` (error tipado si se intenta rechazar uno confirmado,
     para no borrar curacion por error).
   Ambos idempotentes y con mensaje claro.

4. **Config** (`.env.example` + `ExtendedConfig`): `RAG_SUGGEST_MIN_CONFIDENCE`,
   `RAG_SUGGEST_SAMPLE_CHARS` (~2000).

5. **Telemetria** (opcional, si encaja sin esfuerzo): evento `knowledge.suggest`
   con corpus, dominios propuestos y confianzas.

6. **Tests** (patron fases 2-5b: DB `<dbname>_test`, skip sin DB; stub del core
   con `domain.list` y `domain.route`):
   - `status`: con corpus confirmados en unos dominios y no en otros, reporta los
     huecos correctos (excluye `general`).
   - `suggest`: el stub de `domain.route` devuelve dominio+confianza; se crean
     vinculos `auto`/`confirmed=false` para los que superan el umbral; los que no,
     no. No duplica ni pisa `manual`.
   - `confirm`: un `auto` pasa a `confirmed=true` y entonces SI gatea la
     recuperacion (integra con el gate de fase 5b).
   - `reject`: elimina el `auto`; rechazar un `confirmed` -> error tipado.

## Fuera de fase 5c (NO implementar)

- Clasificacion por chunk (se clasifica el corpus como muestra agregada).
- `knowledge maintain` / re-etiquetado por ciclo de vida de dominios (ronda
  aparte).
- Roles/grants de postgres (ADR 0010, endurecimiento progresivo).
- Cambios en memoria, core, o contrato publico.

## Restricciones

Sin comandos git (sandbox); commits del disenador. ASCII en prosa;
identificadores en ingles; errores tipados; sin hosts remotos en tests (stub del
core). `domain.route` es solo lectura (clasifica); todo lo escribe el operador.

## Blanco de aceptacion

- pytest en verde con DB local (skips sin DB); los cuatro grupos de tests
  pasando.
- `./install.sh --skip-db --assume-yes` sigue verde e idempotente.
- `bash -n install.sh` y ASCII limpios.

## Entrega

Ficheros en la rama activa; nota en `docs/handoff/fase_5c_entrega.md` (decisiones,
dudas, inconsistencias, estado de pytest, entrada de CHANGELOG bajo No publicado).
