# Entrega de implementacion: fase 3

Fecha: 2026-07-24
Rama indicada por el usuario: `fase-3-vertical-minimo`
Impacto de version: ninguno; no hay contrato publico cortado hasta la fase 7.

## Resultado

Queda implementado el bucle completo de memoria sobre `prompt.run`:

    recall -> composicion -> core -> write-back -> respuesta

Incluye:

- Configuracion `IANEST_EXTENDED_*` y carga de `.env`.
- `CoreClient` contra `POST /prompt/run`, con identidad completa, timeout,
  traza y errores tipados.
- `OllamaEmbedder` contra `POST /api/embed`, con normalizacion y validacion de
  dimension.
- Recall por tipo y namespace con gates, top-k por tier, presupuesto aproximado
  a cuatro caracteres por token y orden delegadas -> semantic -> episodic ->
  dialog.
- Write-back de los dos turnos crudos a `dialog`; extraccion estructurada con
  modelo declarado; umbral de confianza; dedup-refuerzo; menciones sin resolver
  y descarte trazado de JSON invalido.
- Operaciones de store `find_similar` y `reinforce`, sin columnas nuevas.
- Telemetria JSONL diaria con eventos `enrich.recall` y
  `enrich.write_back`.
- CLI `python -m ianest_extended.chat`, incluido `--show-context`.
- Instalador ampliado con preguntas/flags de URL y modelos, `.env` idempotente
  y `--pull-models` condicionado a que Ollama responda.
- Stub HTTP local determinista, `FakeEmbedder`, pruebas unitarias y los cuatro
  criterios de aceptacion PostgreSQL.

## Decisiones de implementacion

- Se usa solo la biblioteca estandar para HTTP; no se anade una dependencia
  runtime.
- Las memorias delegadas de inyeccion permanente no se someten al gate de
  dominio. `semantic`, `episodic` y `dialog` si lo aplican.
- `entities` no se consulta en el chat minimo porque la identidad del request
  no contiene un `entity_id`; no se construye resolucion de entidades.
- El bloque no recorta memorias delegadas. Si exceden por si solas el
  presupuesto, prevalece su semantica de inyeccion permanente; el recorte
  elimina primero el engrama ranked de menor relevancia.
- Se anade `IANEST_EXTENDED_DATABASE_DSN`, con el DSN loopback del compose por
  defecto. El brief no lo enumeraba, pero la CLI necesita una direccion de
  store separada del DSN reservado a pruebas.
- La migracion comprueba la dimension real de `engrams.embedding`. Si difiere
  de la configurada, conserva las filas, elimina temporalmente el typmod,
  re-embebe su contenido con el adaptador activo y restaura
  `vector(dimension)`.
- La CLI ejecuta `migrate()` antes del primer recall para crear/sembrar una DB
  nueva y reconciliar su dimension.

## Inconsistencia detectada y resuelta

La fase 2 ejecutaba la DB de desarrollo con `FakeEmbedder(16)`, mientras que
ADR 0006 y este brief fijan `bge-m3` a 1024 dimensiones. Mantener el esquema de
16 habria dejado pytest verde y el runtime real roto. La reconciliacion de
dimension anterior evita borrado fisico y las pruebas PostgreSQL usan ahora la
dimension configurada (1024 por defecto).

## Correcciones e2e

Se corrigieron exactamente los tres hallazgos del e2e de laboratorio:

- H1: el prompt de extraccion usa namespaces concretos, confianza real, un
  ejemplo durable con `confidence: 0.9`, un ejemplo de smalltalk vacio y
  prohibicion de fences/texto exterior. El parser elimina fences y recupera el
  primer objeto JSON valido aunque haya texto colgante. La prueba unitaria
  cubre la confianza `0.0`, el namespace compuesto copiado y la salida fenced
  observados en qwen.
- H2: `IANEST_EXTENDED_TEST_DSN` es solo un DSN semilla. El fixture deriva
  `<dbname>_test`, la crea de forma idempotente, instala pgvector y ejecuta
  `migrate()` exclusivamente ahi. Pytest no usa ni modifica
  `IANEST_EXTENDED_DATABASE_DSN`; README y `.env.example` documentan la
  separacion.
- H3: `.env.example`, README y el instalador aclaran que
  `IANEST_EXTENDED_EXTRACTION_MODEL` es un ID existente en `models[]` de la
  config del core, consultable con `model.list`, no necesariamente el tag de
  Ollama. La sugerencia `qwen2.5:7b` se mantiene y el instalador interactivo
  lista los IDs si el core es alcanzable.

Evidencia local posterior: `python -m pytest` deja `19 passed, 10 skipped`; los
skips son los esperados porque no hay PostgreSQL local. `bash -n install.sh` y
`python -m compileall -q src tests` quedan limpios. Impacto de version: ninguno;
no cambia contrato publico.

## Estado de validacion

- `python -m pytest`: `19 passed, 10 skipped`.
- Los diez skips tienen aviso explicito por
  `IANEST_EXTENDED_TEST_DSN no definido`: seis pruebas PostgreSQL de fase 2 y
  cuatro criterios de aceptacion de fase 3.
- La validacion original de `./install.sh --skip-db --assume-yes` fue verde e
  idempotente en ejecuciones consecutivas (`17 passed, 10 skipped` antes de
  anadir las dos evidencias unitarias de H1).
- `bash -n install.sh`: limpio.
- `python -m compileall -q src tests`: limpio.
- `python -m pip check`: sin dependencias rotas.
- Control ASCII sobre docs, Python, tests, shell y ficheros raiz: limpio.
- `.env` quedo con una unica entrada por clave tras las ejecuciones
  consecutivas.

Las instalaciones editables se resolvieron sin indice de paquetes, usando los
recursos ya presentes. No se conecto a hosts remotos.

## No validado en esta maquina

- No hay PostgreSQL local: no se ejecutaron los diez tests de DB ni la
  reconciliacion SQL de dimension.
- No se ejecuto e2e contra core y Ollama reales; corresponde al laboratorio.
- No se uso `--pull-models`, porque Ollama no esta disponible y no se debia
  conectar a otro host.
- `shellcheck` no esta instalado.

## Entrada de CHANGELOG

Se anadio bajo `No publicado / Anadido` la implementacion del vertical minimo
de fase 3 y se declaro impacto de version ninguno.
