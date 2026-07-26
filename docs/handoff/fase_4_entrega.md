# Entrega de implementacion: fase 4

Fecha: 2026-07-26
Rama indicada por el usuario: `fase-4-consolidacion`
Impacto de version: ninguno; no hay contrato publico cortado hasta la fase 7.

## Resultado

Queda implementada la consolidacion mecanica del gradiente estricto:

- `ConsolidationEvent` tipado con trigger extensible, principal, fuentes,
  destino opcional, contenido, namespace y razon.
- `ConsolidationExecutor` como punto de servicio unico, con telemetria
  `memory.consolidation`.
- Aplicacion transaccional en PostgreSQL: comprueba autoridad del destino,
  crea el engrama, registra `consolidated_from` y archiva las fuentes sin
  `DELETE`.
- Costura de conscience ejercida: un principal externo puede escribir su tipo
  delegado y pedir que el ejecutor archive y enlace fuentes estrictas, sin
  obtener escritura directa sobre ellas.
- `python -m ianest_extended.maintain`, idempotente por seleccion exclusiva de
  engramas activos, con `--dry-run` sin mutacion de DB.
- Archivado de `dialog` fuera de ventana y promocion literal individual de
  `episodic` a `semantic`, sin sintesis multi-item.
- Telemetria `memory.maintain` con dialogos archivados, episodicos promovidos,
  candidatos vistos y marca de dry-run.
- Cinco pruebas PostgreSQL para promocion, no-candidato, archivado de dialog,
  autoridad delegada y dry-run.

## Decisiones de implementacion

- `IANEST_EXTENDED_DIALOG_HOT_WINDOW` se expresa en segundos. Su default es
  14400, igual a la vida media inicial de `dialog`.
- La recencia de promocion usa
  `COALESCE(last_reinforced_at, created_at)`: un refuerzo reciente vuelve a
  calentar el engrama.
- `tasks` se excluye de promocion porque el roster reconciliado declara que no
  asciende a `semantic`.
- La promocion literal copia el embedding de la fuente. Por eso `maintain` no
  construye un embedder ni conecta a Ollama o al core.
- El ejecutor general usa el embedder configurado solo cuando el contenido de
  destino no es una copia literal de una fuente unica.
- Destino, lineage y archivo se aplican en una sola transaccion. Un fallo no
  deja una promocion parcial.
- `--dry-run` emite el resumen de telemetria, pero no cambia filas, estados ni
  enlaces en PostgreSQL.
- No se anadio migracion: `memory_links`, estados y campos de archivo ya
  existian desde la fase 2.

## Dudas e inconsistencias

No quedaron ambiguedades de fase 4 que exigieran una decision del disenador.

Se detecto una incidencia preexistente fuera del alcance: el encabezado H1 de
`docs/handoff/fase_3_fixes_brief.md` contiene un guion largo no ASCII. No se
corrigio por inferencia, conforme al modo ciego multi-IA. Todos los ficheros
creados o editados en esta entrega pasan el control ASCII.

## Estado de validacion

- `.venv/bin/python -m pytest`: `20 passed, 15 skipped`.
- Los quince skips tienen aviso explicito por
  `IANEST_EXTENDED_TEST_DSN no definido`: seis pruebas PostgreSQL de fase 2,
  cuatro de fase 3 y las cinco nuevas de fase 4.
- `.venv/bin/python -m compileall -q src tests`: limpio.
- `bash -n install.sh`: limpio.
- `.venv/bin/python -m pip check`: sin dependencias rotas.
- `python -m ianest_extended.maintain --help`: limpio.
- `./install.sh --skip-db --assume-yes`: verde en dos ejecuciones consecutivas,
  ambas con `20 passed, 15 skipped`.
- `.env` conserva una unica entrada por clave tras ambas ejecuciones.
- Control ASCII de todos los ficheros creados o editados: limpio.

## No validado en esta maquina

- No hay PostgreSQL local: los cinco criterios de fase 4 quedan automatizados,
  pero su SQL no se ejecuto aqui. El fixture conserva el patron
  `<dbname>_test` de fase 3 y no acepta hosts remotos.
- No se conecto a core, Ollama ni ningun host remoto.
- `shellcheck` no esta instalado; se ejecuto `bash -n install.sh`.

## Entrada de CHANGELOG

Se anadio bajo `No publicado / Anadido` la implementacion de fase 4 y se
declaro impacto de version ninguno.
