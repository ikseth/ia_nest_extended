# Entrega de implementacion: fase 5b

Fecha: 2026-08-13
Rama indicada por el disenador: `fase-5b-conocimiento-nm`
Impacto SemVer: ninguno; el contrato publico se corta en Fase 7.

## Entregado

- `db/migrations/0003_rag_domains.sql` crea la relacion N:M
  `rag_corpus_domains`, unica por corpus y dominio, con `source`, `confidence`,
  `confirmed` y restricciones de procedencia.
- La migracion convierte cada `rag_corpora.domain` anterior en un vinculo
  `manual` confirmado y elimina solo la columna antigua. No borra corpus ni
  chunks y es idempotente.
- La ingesta admite cero o varios `--domain`. Los dominios repetidos se
  normalizan, cada valor se valida una vez contra `CoreClient.list_domains()` y
  los vinculos manuales confirmados se escriben con upsert idempotente.
- Un corpus sin dominio queda disponible solo para recuperacion global.
- `PostgresRagStore.retrieve` gatea mediante un vinculo del dominio solicitado
  con `confirmed=true`; los vinculos no confirmados no habilitan el corpus.
- Los modelos internos de chunk y resultado de ingesta representan dominios
  como coleccion, sin conservar la falsa cardinalidad 1:1.
- Las tablas `rag_*` siguen aisladas de las tablas de memoria, sin joins entre
  ambos stores.

## Pruebas

- `.venv/bin/python -m pytest`: 33 passed, 20 skipped. Los skips tienen aviso
  explicito porque `IANEST_EXTENDED_TEST_DSN` no esta definido y la DB local no
  esta disponible.
- Los cinco tests PostgreSQL de Fase 5b cubren: N:M, anti-colision,
  confirmacion, reingesta mult dominio idempotente y migracion del esquema
  anterior. Quedan preparados para la DB derivada `<dbname>_test` del fixture.
- `.venv/bin/python -m compileall -q src tests`: correcto.
- `.venv/bin/python -m ianest_extended.ingest --help`: correcto.
- `bash -n install.sh`: correcto.
- `./install.sh --skip-db --assume-yes`: correcto e idempotente; reutilizo el
  venv, reinstalo el editable y termino con 33 passed, 20 skipped esperados.
- ASCII: correcto en todos los ficheros creados o editados.

## Decisiones y senalizaciones

- La identidad de corpus usada por la ingesta sigue siendo su nombre. La
  migracion conserva posibles corpus historicos homonimos en vez de fusionarlos,
  porque el brief prohibe borrar corpus o chunks.
- No se detectaron inconsistencias entre el brief y ADR 0008/0009/0010.
- No se implementaron auto-etiquetado, confirmacion interactiva,
  `knowledge maintain`, completitud, roles/grants, schemas separados ni cambios
  en memoria o core.

## Changelog

Se anadio una entrada bajo `No publicado` con impacto de version `ninguno`.
