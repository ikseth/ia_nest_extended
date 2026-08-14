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
- `--rag-*`: configuran ingesta, presupuesto y auto-route del RAG; consulta
  `--help` para la lista completa.
- `--pull-models`: descarga el modelo de embeddings despues de comprobar que
  Ollama es alcanzable. El ID de extraccion pertenece al core y no se trata
  como tag de Ollama.
- `--help`: muestra la ayuda completa.

El script es idempotente: se puede ejecutar de nuevo para reutilizar la DB y
actualizar el entorno Python. En modo interactivo pregunta las URL y los modelos
de apoyo, proponiendo los recomendados; `--assume-yes` los toma sin preguntar.
La configuracion queda en `.env`, que no se versiona. El compose publica
PostgreSQL solo en `127.0.0.1:55432`.

Las variables de la capa usan el prefijo `IANEST_EXTENDED_`. `.env.example`
documenta URL del core y Ollama, modelos, dimension, telemetria, identidad por
defecto, defaults de enriquecimiento, presupuesto, top-k y umbrales. El timeout
unico se parte en dos: `CONNECT_TIMEOUT_SECONDS` (conexion) e
`INACTIVITY_TIMEOUT_SECONDS` (inactividad entre eventos de un flujo).

`IANEST_EXTENDED_EXTRACTION_MODEL` es el ID del modelo declarado en `models[]`
de la configuracion del core de la instalacion, no necesariamente el tag de
Ollama. El ID se consulta con `model.list` (`GET /model/list`); por ejemplo, una
instalacion puede exponer `qwen_tech` aunque el tag servido sea `qwen2.5:7b`.
El instalador usa `qwen_tech` como ejemplo configurable y, si el core esta
alcanzable durante la configuracion interactiva, muestra los IDs disponibles.

Pytest toma `IANEST_EXTENDED_TEST_DSN` solo como DSN semilla. Su fixture deriva
y crea `<dbname>_test`, instala ahi pgvector y ejecuta la migracion. La base
indicada por `IANEST_EXTENDED_DATABASE_DSN` es la base runtime y pytest nunca
la migra ni escribe.

## Migracion explicita del esquema

La migracion es un paso de despliegue, no un efecto de arrancar un comando
(ADR 0011, punto 6). Ningun comando muta el esquema salvo:

    ianest-extended runtime migrate

El resto lo VERIFICA y, si falta migrar, falla con error tipado indicando este
comando. `install.sh` lo invoca al preparar el entorno.

## CLI de operador

Una unica superficie instalable, `ianest-extended`, con gramatica GRUPO ACCION
calcada de la del core. Todas las acciones aceptan `--json`, y `--env-file RUTA`
permite usar el comando fuera de la raiz del repo. Los harnesses
`python -m ianest_extended.chat|ingest|knowledge|maintain` quedan RETIRADOS: una
sola superficie, sin alias.

La identidad deja de ser obligatoria: `--user-id`, `--service`, `--session-id` y
`--namespace` toman defaults de configuracion (`service` es `local_cli`). Si no
se indica `--session-id`, se genera uno y se RECUERDA en un fichero local, de
ruta configurable y no versionado, para que el tier `dialog` encadene
invocaciones. `--domain` es un unico valor: gatea el conocimiento, viaja al core
como dominio de ruteo y etiqueta la memoria.

Capacidades SOBREESCRITAS (enriquecidas):

    ianest-extended prompt run --prompt "Recuerda que prefiero respuestas breves"
    ianest-extended prompt run --prompt "Que recuerdas?" --show-context
    ianest-extended prompt run --prompt "hola" --no-enrich
    ianest-extended prompt run --prompt "hola" --dry-run

Config da DEFAULTS y las banderas son override POR PETICION: `--enrich`,
`--use-memory`, `--use-rag`, `--write-back` y `--auto-domain` admiten su forma
negada (`--no-...`) y, sin indicar, toman el valor configurado. `--no-enrich` es
un macro (ni recuperacion, ni inyeccion, ni write-back) que sigue emitiendo
telemetria propia. Una combinacion contradictoria es error tipado, no
precedencia silenciosa. Los numeros (top-k, presupuestos, umbrales) no llevan
bandera: viven en la configuracion.

Capacidades REENVIADAS sin alterar (no las enriquece esta capa):

    ianest-extended domain list
    ianest-extended domain route --prompt "administra linux"
    ianest-extended model list
    ianest-extended runtime health
    ianest-extended config validate
    ianest-extended eval run --param suite=humo
    ianest-extended prompt stream --prompt "hola"

`prompt stream` se reenvia al core y NO lleva memoria ni RAG en esta fase. El
cuerpo reenviado se declara con `--prompt`, `--param CLAVE=VALOR` y
`--payload JSON`, y la respuesta llega intacta: esta capa no la valida ni la
reescribe.

Capacidades PROPIAS:

    ianest-extended memory recall --prompt "Que recuerdas?"
    ianest-extended memory maintain --dry-run
    ianest-extended memory_type list
    ianest-extended knowledge ingest --corpus manual-unix --domain linux docs/manuales/
    ianest-extended knowledge status
    ianest-extended knowledge suggest --corpus manual-unix
    ianest-extended knowledge confirm --corpus manual-unix --domain linux
    ianest-extended knowledge reject --corpus manual-unix --domain codigo

`memory.write`, `memory.consolidate` y `memory_type.validate` existen como
capacidades del servicio, pero no tienen comando: su consumidor es `conscience`
por REST (fase 7c).

Codigos de salida, iguales a los del core: `0` correcto, `1` error tipado en
stderr con formato `Tipo (campo): mensaje` (o su JSON con `--json`), y `2` uso
incorrecto, que imprime la ayuda del grupo.

## RAG upfront

`knowledge ingest` acepta un fichero o un directorio curado de `.txt`/`.md`.
`--domain` se puede repetir y cada valor se valida contra `domain.list`; si se
omite, el corpus queda sin vinculos y solo participa en recuperacion global. La
ingesta es idempotente por corpus, vinculo de dominio, `source_ref` y ordinal.
`prompt run` recupera solo corpus con vinculo confirmado al dominio explicito;
con `--auto-domain` (o `AUTO_DOMAIN=true`) pide antes `domain.route` al core
cuando el caller no declara dominio. Cada consulta RAG emite `rag.retrieve` y su
bloque compite por el presupuesto de contexto sin recortar las memorias
delegadas ni el prompt del usuario.

Si se pide RAG y su sustrato no esta disponible, el fallo es tipado: nunca un
enriquecimiento vacio en silencio.

## Mantenimiento de memoria

Con PostgreSQL local disponible:

    ianest-extended memory maintain --dry-run
    ianest-extended memory maintain

`--dry-run` calcula el resumen sin cambiar engramas ni lineage. La ejecucion
real archiva `dialog` fuera de la ventana caliente y promociona literalmente
los `episodic` elegibles a `semantic`; reutiliza su embedding y no conecta al
core ni a Ollama, porque el composition-root construye cada dependencia solo
cuando la operacion invocada la necesita. Emite `memory.maintain` y, por cada
transicion aplicada, `memory.consolidation`.

## Telemetria

Cada interaccion emite eventos JSONL en el directorio configurado: `prompt.run`
siempre, mas `enrich.recall`, `enrich.write_back` y `rag.retrieve` en el camino
enriquecido. Cada evento lleva su `request_id` propio y el
`downstream_request_id` de la llamada al core, que es el nombre generico del
ente para encadenar la traza entre capas.

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
