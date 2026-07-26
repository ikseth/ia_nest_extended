# ia_nest_extended

Capa de ENRIQUECIMIENTO del ente IA_NEST: memoria, RAG y datos web. Vive ENCIMA
del core (`ia_nest_core`), consumiendo sus contratos publicos; no modifica el
core (via 2, core ADR 0031).

- `IA_NEST_EXTENDED_CONTEXT.md`: que es y su relacion con el ente.
- `docs/ALCANCE.md`: dentro/fuera de esta capa.
- `docs/DEPENDENCIAS.md`: vinculo versionado con el core.
- `docs/PLAN.md`: fases (memoria primero).

## Instalacion de desarrollo

El instalador esta orientado primero a openSUSE. Detecta Docker funcional o,
como alternativa, Podman con soporte Compose. Si no encuentra ninguno, ofrece
instalar Podman con `zypper`. Tambien crea `.venv` con Python 3.13, instala el
paquete editable y ejecuta pytest.

Desde una copia nueva del repo:

    ./install.sh

La instalacion de paquetes del sistema requiere confirmacion y acceso `root` o
`sudo`. Para aceptar esa instalacion sin pregunta:

    ./install.sh --assume-yes

Opciones disponibles:

- `--skip-db`: prepara `.venv`, instala el paquete y ejecuta las pruebas con los
  skips esperados de PostgreSQL.
- `--skip-tests`: prepara los recursos, pero no ejecuta pytest.
- `--core-url`, `--ollama-url`, `--embedding-model`,
  `--embedding-dimension` y `--extraction-model`: fijan la configuracion local
  sin preguntas.
- `--pull-models`: descarga los modelos configurados despues de comprobar que
  Ollama es alcanzable.
- `--help`: muestra la ayuda completa.

El script es idempotente: se puede ejecutar de nuevo para reutilizar la DB y
actualizar el entorno Python. En modo interactivo pregunta las URL y los modelos
de apoyo, proponiendo los recomendados; `--assume-yes` los toma sin preguntar.
La configuracion queda en `.env`, que no se versiona. El compose publica
PostgreSQL solo en `127.0.0.1:55432`.

Las variables de la capa usan el prefijo `IANEST_EXTENDED_`. `.env.example`
documenta URL del core y Ollama, modelos, dimension, telemetria, presupuesto,
top-k y umbrales.

`IANEST_EXTENDED_EXTRACTION_MODEL` es el ID del modelo declarado en `models[]`
de la configuracion del core de la instalacion, no necesariamente el tag de
Ollama. El ID se consulta con `model.list` (`GET /model/list`); por ejemplo, una
instalacion puede exponer `qwen_tech` aunque el tag servido sea `qwen2.5:7b`.
El instalador mantiene `qwen2.5:7b` como sugerencia y, si el core esta
alcanzable durante la configuracion interactiva, muestra los IDs disponibles.

Pytest toma `IANEST_EXTENDED_TEST_DSN` solo como DSN semilla. Su fixture deriva
y crea `<dbname>_test`, instala ahi pgvector y ejecuta la migracion. La base
indicada por `IANEST_EXTENDED_DATABASE_DSN` es la base runtime y pytest nunca
la migra ni escribe.

## Chat minimo con memoria

Con PostgreSQL, el core y Ollama locales disponibles:

    python -m ianest_extended.chat \
        --user operador \
        --session sesion-1 \
        --domain general \
        "Recuerda que prefiero respuestas breves"

Para inspeccionar el bloque inyectado antes del prompt:

    python -m ianest_extended.chat \
        --user operador \
        --session sesion-1 \
        --show-context \
        "Que recuerdas?"

Cada interaccion emite eventos JSONL `enrich.recall` y
`enrich.write_back` en el directorio de telemetria configurado.

## Mantenimiento de memoria

Con PostgreSQL local disponible:

    python -m ianest_extended.maintain --dry-run
    python -m ianest_extended.maintain

`--dry-run` calcula el resumen sin cambiar engramas ni lineage. La ejecucion
real archiva `dialog` fuera de la ventana caliente y promociona literalmente
los `episodic` elegibles a `semantic`; reutiliza su embedding y no conecta al
core ni a Ollama. Emite `memory.maintain` y, por cada transicion aplicada,
`memory.consolidation`.

`IANEST_EXTENDED_DIALOG_HOT_WINDOW` se expresa en segundos y vale 14400 por
defecto, igual a la vida media inicial de `dialog`. Los umbrales de promocion
son `IANEST_EXTENDED_PROMOTE_MIN_STABILITY=3`,
`IANEST_EXTENDED_PROMOTE_MIN_SCORE=0.8` y
`IANEST_EXTENDED_PROMOTE_RECENCY_MAX=0.1`.

Para parar la DB sin borrar sus datos:

    docker compose -f docker-compose.dev.yml down

Si se selecciono Podman:

    podman compose -f docker-compose.dev.yml down

En instalaciones que expongan el proveedor como comando independiente, usa
`podman-compose` en lugar de `podman compose`.

Para limpiar tambien el volumen y todos los datos locales, anade `--volumes` al
comando `down`. Esta operacion no se puede deshacer.
