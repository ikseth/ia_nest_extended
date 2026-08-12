# Entrega de implementacion: fase 5 (RAG upfront)

Fecha: 2026-08-12
Rama indicada por el usuario: `fase-5-rag-upfront`
Impacto de version: ninguno; no hay contrato publico cortado hasta la fase 7.

## Resultado

Queda implementado el RAG operativo para el camino upfront de `prompt.run`:

- Migracion `0002_rag.sql` con `rag_corpora` y `rag_chunks`, dimension vectorial
  compartida con el embedder de memoria e idempotencia por
  `corpus_id` + `source_ref` + `ordinal`.
- `PostgresRagStore` separado del store de memoria, con alta/reactivacion de
  corpus, upsert de chunks y recuperacion coseno sobre corpus activos.
- Gate exacto por dominio cuando se declara; similitud global cuando falta.
- CLI `python -m ianest_extended.ingest` para fichero o directorio de `.txt` y
  `.md`, con troceo y solape configurables, `OllamaEmbedder` en runtime y
  resumen de chunks nuevos/actualizados.
- `CoreClient.domain_route` tipado y dominio explicito propagado tambien como
  argumento de `prompt.run`.
- Integracion upfront en el flujo existente con orden delegadas -> RAG ->
  semantic -> episodic -> dialog, seguida del prompt de usuario intacto.
- Presupuesto conservador a 3.5 caracteres por token. El limite propio de RAG
  se aplica primero; ante presion global caen RAG y despues episodic. Las
  delegadas y el prompt del usuario no se recortan.
- Telemetria `rag.retrieve` con dominio, k pedido/devuelto, corpus tocados,
  latencia y datos de auto-route.
- Configuracion e instalador ampliados con todas las claves `RAG_*`. El modelo
  de extraccion queda expresado como ID del core y `--pull-models` solo descarga
  el modelo de embeddings, no intenta interpretar ese ID como tag de Ollama.
- Pruebas unitarias y PostgreSQL para los cinco grupos del brief.

## Decisiones de implementacion

- Memoria y RAG comparten PostgreSQL, pgvector y embedder, pero usan stores,
  modelos y tablas separados. La migracion RAG no lee ni muta tablas de memoria.
- Un corpus se identifica por `(name, domain)`. Esto permite el mismo nombre
  curatorial en dominios distintos sin debilitar el gate.
- En directorios, `source_ref` es la ruta relativa POSIX. Si se pasa
  `--source-ref`, actua como prefijo estable; cada fichero reinicia `ordinal`.
- El troceo aproxima tokens a 3.5 caracteres, prefiere cortes por salto de linea
  o espacio y conserva el solape configurado sin generar chunks vacios.
- La ingesta repetida cuenta como actualizados los chunks cuya clave ya existe,
  aunque el contenido no haya cambiado. Nunca crea duplicados.
- Una discrepancia entre la dimension configurada y `rag_chunks.embedding`
  produce `RagSchemaError` con instruccion explicita. El reindexado queda fuera
  de fase 5, como exige el brief.
- Auto-route solo se ejecuta sin dominio explicito y con
  `RAG_AUTO_DOMAIN=true`. Por debajo del umbral se conserva `domain=None` y se
  usa similitud global.
- El bloque envolvente pasa a llamarse `enrichment_context`, porque ya contiene
  dos subsistemas hermanos y no solo memoria.

## Dudas e inconsistencias

No quedaron ambiguedades ni inconsistencias de fase 5 que exigieran una
decision del disenador.

La correccion pedida para `IANEST_EXTENDED_EXTRACTION_MODEL` se aplico de forma
coherente en `.env.example`, `ExtendedConfig` e instalador: es un ID de
`models[]` del core. El pull de Ollama queda limitado al embedding.

## Estado de validacion

- `.venv/bin/python -m pytest`: `27 passed, 17 skipped`.
- Los diecisiete skips tienen aviso explicito por
  `IANEST_EXTENDED_TEST_DSN no definido`: seis pruebas PostgreSQL de fase 2,
  cuatro de fase 3, cinco de fase 4 y las dos nuevas de fase 5.
- El fixture conserva el patron seguro `<dbname>_test` de fase 3 y omite DSN que
  no apunte a loopback.
- `.venv/bin/python -m compileall -q src tests`: limpio.
- `bash -n install.sh`: limpio.
- `.venv/bin/python -m pip check`: sin dependencias rotas.
- `python -m ianest_extended.ingest --help`: limpio.
- `python -m ianest_extended.chat --help`: limpio.
- `./install.sh --skip-db --assume-yes`: verde en dos ejecuciones consecutivas,
  ambas con `27 passed, 17 skipped`.
- `.env` conserva una unica entrada por clave tras ambas ejecuciones.
- Busqueda de `task.run`/`task.plan` en codigo, tests, migraciones, instalador y
  plantilla de entorno: sin resultados.
- Busqueda de mutaciones de `engrams` en los ficheros de fase 5: sin resultados.

## No validado en esta maquina

- No hay PostgreSQL local: las dos pruebas SQL de fase 5 quedan automatizadas,
  pero se omitieron con aviso. No se uso una DB remota.
- No se ejecuto e2e contra core ni Ollama reales; corresponde al verificador en
  laboratorio. Los tests usan stub HTTP loopback y `FakeEmbedder`.
- `shellcheck` no esta instalado; se ejecuto `bash -n install.sh`.

## Entrada de CHANGELOG

Se anadio bajo `No publicado / Anadido` la implementacion de fase 5 y se declaro
impacto de version ninguno.
