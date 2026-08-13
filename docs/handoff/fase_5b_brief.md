# Handoff de implementacion: fase 5b (modelo N:M de conocimiento por dominio)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus/Fable), rol disenador.
Verificacion: Opus (e2e en laboratorio).
Base: `main` con fase 5 (RAG upfront) integrada.

Lee antes: `AGENTS.md`, ADR 0009 (modelo N:M, con diagramas), ADR 0010
(aislamiento; aqui solo se respeta la SEPARABILIDAD, los roles/grants se difieren),
ADR 0008 (forma del RAG). Ante ambiguedad: PARA y pregunta.

## Objetivo

Sustituir el `domain` unico del RAG por una relacion N:M dominio<->corpus con
procedencia y confirmacion, y gatear la recuperacion por vinculos CONFIRMADOS.
Solo esto; el auto-etiquetado, el `knowledge maintain` y el chequeo de
completitud quedan FUERA (workflow siguiente).

## Dentro de fase 5b

1. **Migracion** (`db/migrations/0003_rag_domains.sql`):
   - Crea `rag_corpus_domains`: `id` (uuid), `corpus_id` (fk), `domain` (text),
     `source` (`manual|auto`), `confidence` (float, null si manual), `confirmed`
     (bool), `created_at`. Unico por (`corpus_id`, `domain`).
   - Migra cada `rag_corpora.domain` existente a una fila `source='manual'`,
     `confirmed=true`.
   - Elimina la columna `domain` de `rag_corpora`. Sin borrado de chunks ni de
     corpus.

2. **Ingesta** (`ianest_extended.ingest`): `--domain` admite uno o varios
   (repetible o lista). Cada uno:
   - se valida contra `CoreClient.list_domains()` (reusa la validacion del fix de
     fase 5; un dominio no-core -> error tipado, no se crea el vinculo);
   - se registra como vinculo `manual` + `confirmed` (idempotente por
     (`corpus_id`, `domain`)).
   Sin `--domain` no se crea vinculo (corpus sin dominio; recuperable solo en
   modo global).

3. **Recuperacion** (`PostgresRagStore.retrieve`): el gate por dominio pasa de
   `corpus.domain = D` a "corpus con vinculo `confirmed=true` a D" (join con
   `rag_corpus_domains`). Un vinculo `confirmed=false` NO gatea. Sin dominio ->
   similitud global sobre corpus activos (D1, ADR 0008, intacto).

4. **Separabilidad** (ADR 0010): las tablas de conocimiento (`rag_*`) siguen
   siendo propias, sin joins con las tablas de memoria (`engrams`, etc.). No se
   implementan roles/grants de postgres aqui (endurecimiento progresivo, diferido);
   solo se preserva que el conocimiento sea un store separable.

5. **Tests** (patron fases 2-5: DB `<dbname>_test`, skip sin DB; stub del core con
   `domain.list`):
   - N:M: un corpus con vinculos a `linux` y `codigo` se recupera con `domain=linux`
     Y con `domain=codigo`.
   - Anti-colision: un corpus solo de `cocina`... (usar dominios validos del stub:
     p.ej. `linux`, `codigo`) no aparece con otro dominio.
   - Confirmacion: un vinculo `confirmed=false` NO gatea; el mismo tras confirmar
     (o uno manual) SI.
   - Ingesta multi-dominio idempotente: re-ingestar no duplica vinculos.
   - Migracion: un `rag_corpora.domain` previo queda como vinculo manual/confirmed
     y el corpus sigue recuperable por ese dominio.

## Fuera de fase 5b (NO implementar)

- Auto-etiquetado por `domain.route`, confirmacion interactiva, `knowledge
  maintain` (ciclo de vida de dominios), chequeo de completitud. (Workflow, ronda
  propia.)
- Roles/grants de postgres, schemas o instancias separadas (ADR 0010,
  endurecimiento progresivo).
- Cambios en las tablas de memoria, en el core, o en el contrato publico.

## Restricciones

Sin comandos git (sandbox); commits del disenador. ASCII en prosa;
identificadores en ingles; errores tipados; sin hosts remotos (stub del core en
tests). No toques el sustrato de memoria ni el core.

## Blanco de aceptacion

- pytest en verde con DB local (skips sin DB); los cinco grupos de tests pasando.
- `./install.sh --skip-db --assume-yes` sigue verde e idempotente.
- `bash -n install.sh` y ASCII limpios.

## Entrega

Ficheros en la rama activa; nota en `docs/handoff/fase_5b_entrega.md` (decisiones,
dudas, inconsistencias, estado de pytest, entrada de CHANGELOG bajo No publicado).
