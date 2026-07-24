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
- `--help`: muestra la ayuda completa.

El script es idempotente: se puede ejecutar de nuevo para reutilizar la DB y
actualizar el entorno Python. El compose publica PostgreSQL solo en
`127.0.0.1:55432`.

Para parar la DB sin borrar sus datos:

    docker compose -f docker-compose.dev.yml down

Si se selecciono Podman:

    podman compose -f docker-compose.dev.yml down

En instalaciones que expongan el proveedor como comando independiente, usa
`podman-compose` en lugar de `podman compose`.

Para limpiar tambien el volumen y todos los datos locales, anade `--volumes` al
comando `down`. Esta operacion no se puede deshacer.
