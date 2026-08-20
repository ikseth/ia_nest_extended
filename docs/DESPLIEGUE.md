# Despliegue de ia_nest_extended

## Proposito

`deploy/setup.sh` sustituye la secuencia manual de despliegue. `install.sh` no
forma parte de este camino: sigue siendo el preparador del entorno de desarrollo.

El layout efectivo es:

```text
/opt/ia_nest/
  repositories/
  config/extended/<instancia>/
    extended.env
    setup.conf
  state/extended/<instancia>/
    venv/
    telemetry/
    session_id
    catalog_cache.json
```

La configuracion queda fuera del repositorio, con modo `0600` y propiedad del
`OPERATOR_USER`. Los wrappers de `/usr/local/bin` resuelven esa configuracion,
por lo que el operador no activa ningun venv ni depende del directorio actual.

## Requisitos

- Bash, `curl` y Python `>=3.13,<3.14`.
- Acceso de escritura a `/opt/ia_nest`, `/usr/local/bin` y, si se instalan
  servicios, `/etc/systemd/system` y `systemctl`.
- Core y endpoint de embeddings ya desplegados. Este instalador no provisiona
  el backend de modelos.
- Un PostgreSQL con pgvector alcanzable, o Docker Compose/Podman Compose si se
  declara `PROVISION_STORE=true`.
- Acceso de red al indice de paquetes configurado para `pip`. El instalador lo
  comprueba antes de instalar y devuelve un error propio si no es alcanzable.

REST y MCP no tienen autenticacion. Sus defaults escuchan solo en loopback.

## Un comando

Copiar y editar el ejemplo, desde un checkout situado preferentemente bajo
`/opt/ia_nest/repositories/`:

```bash
cp deploy/ejemplo.setup.conf /tmp/extended.setup.conf
sudo deploy/setup.sh --config /tmp/extended.setup.conf
```

La precedencia es argumento, fichero y defecto. Antes de ejecutar efectos se
puede inspeccionar la resolucion; el DSN se oculta:

```bash
deploy/setup.sh --config /tmp/extended.setup.conf --print-config
```

Una segunda ejecucion actualiza el paquete, vuelve a aplicar migraciones
idempotentes, reingiere el texto declarado y deja el mismo estado. Si ya existe
`setup.conf` o `extended.env`, el instalador lo anuncia y lo preserva. Solo
`REPLACE_CONFIG=true` autoriza reemplazarlo.

## Almacen existente, incluida la via remota

Esta es una via de primera clase y no consulta ningun runtime de contenedores:

```text
STORE_DSN=postgresql://usuario:secreto@db.example.net:5432/ianest_extended
PROVISION_STORE=false
```

El instalador usa ese DSN para comprobar conectividad y ejecutar `runtime
migrate`. Un fallo termina con codigo distinto de cero y conserva la causa que
devuelve el cliente PostgreSQL.

Para provision local, usar un DSN de loopback completo y habilitar la provision:

```text
STORE_DSN=postgresql://ianest:secreto@127.0.0.1:55432/ianest_extended
PROVISION_STORE=true
```

Se crea un proyecto Compose por instancia con `pgvector/pgvector:pg17` y politica
de reinicio `unless-stopped`. El DSN remoto nunca se degrada a esta ruta ni exige
Docker o Podman.

Las migraciones SQL viajan dentro del paquete Python y `runtime migrate` las
resuelve como recursos instalados. No dependen del checkout ni del directorio
actual, y existe una sola copia de cada SQL en el repositorio.

## Corpus reproducible

La fuente es siempre TEXTO UTF-8 `.txt` o `.md`, como fichero o directorio. No
se exportan ni clonan vectores: los embeddings se derivan de nuevo con
`EMBEDDING_MODEL` y `EMBEDDING_DIMENSION` en la instalacion destino.

```text
CORPUS_PATH=/srv/corpus/operativo
CORPUS_NAME=operativo
CORPUS_DOMAINS=linux,codigo
```

El instalador ejecuta `knowledge ingest` con cada dominio declarado y despues
`knowledge confirm` para cada vinculo. La operacion es idempotente por corpus,
referencia de fuente y ordinal de chunk. `knowledge status` permite comprobar
los vinculos confirmados.

## Comandos y servicios

Quedan disponibles desde cualquier directorio:

```bash
ianest-extended prompt run --prompt "hola"
ianest-extended-rest
ianest-extended-mcp --transport sse
```

`SERVICE_INSTALL` controla si se escriben las units REST y MCP.
`SERVICE_ENABLE` controla aparte si se habilitan para reinicio y se arrancan.
Las units esperan `network-online.target`, corren como `OPERATOR_USER` y usan
`Restart=on-failure`.

Al habilitarlas, setup espera primero al puerto REST y al puerto MCP. Solo
despues consulta `systemctl is-active`; `Type=simple` por si solo no demuestra
que el proceso escuche.

## Verificacion y codigos de salida

`VERIFY` admite:

- `strict`: exige servicios habilitados y falla ante cualquier problema.
- `warn`: ejecuta las comprobaciones posibles y avisa si alguna falla.
- `skip`: omite solo la verificacion final; migracion, ingesta y arranque siguen
  siendo operaciones reales y sus fallos siguen siendo fatales.

La verificacion estricta ejecuta:

1. migracion del esquema sobre el DSN efectivo;
2. `memory_type list` y `knowledge status` por CLI;
3. espera activa de los puertos REST y MCP;
4. `GET /capability/list`, sin degradacion y con todas las capacidades propias;
5. `GET /memory_type/list` y `GET /knowledge/status` por REST.

Cualquier fallo devuelve codigo distinto de cero. Una prueba deliberada de DSN
invalido debe hacerse contra un nombre o puerto reservado para prueba, nunca
contra una instalacion real:

```bash
deploy/setup.sh --config /tmp/extended.setup.conf \
  --store-dsn postgresql://invalid:invalid@127.0.0.1:1/invalid
echo "$?"  # distinto de cero
```

## Verificacion posterior en maquina real

Los criterios que requieren red, systemd, reinicio o contenedores solo se
cierran en la maquina destino. Alli se ejecutan dos pasadas seguidas, la sonda de
DSN invalido, `knowledge status`, un reinicio completo y, despues, un
`ianest-extended prompt run` desde el directorio personal del operador.
