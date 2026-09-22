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

Lo que si hacen desde el ADR 0014 es **negarse a inventar quien llama**: una
peticion a REST o MCP sin `identity.user_id` -o sin `identity.session_id`, salvo
en las capacidades de sesion- se rechaza con error tipado que nombra el campo.
El servidor tampoco recuerda sesiones: el fichero de estado es de la CLI, que es
para quien se penso.

Antes no era asi, y por eso se decidio: una peticion sin `user_id` se atribuia a
`local_operator`, y una sin `session_id` caia en una sesion que el servicio
genero una vez y no rotaba jamas. Dos clientes anonimos distintos eran, para la
capa, **el mismo interlocutor en el mismo hilo**: medido en el laboratorio el
2026-09-22, diez horas y dos conversaciones ajenas dentro de una misma sesion.

Rechazar no es autenticar. La capa deja de suponer una identidad; **no verifica
la que recibe**, y eso sigue siendo trabajo de la frontera.

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

El mismo fichero admite cualquier clave con prefijo `IANEST_EXTENDED_` y la
conserva sin traducir en `extended.env`, despues del bloque que genera el
instalador. Es el canal para declarar ajustes del esquema de la capa que no
tienen opcion propia en setup. El instalador no valida esos valores: su esquema
y su validacion viven en `config.py` y se aplican al arrancar la capa.

Una clave desconocida sin ese prefijo sigue siendo error. Tambien es error
`configuration_collision` declarar una variable que setup ya genera; el mensaje
nombra la clave y la opcion equivalente. Nunca se elige en silencio entre las
dos fuentes. Las claves heredadas conservan el orden del fichero y viajan al
`setup.conf` efectivo.

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

Para declarar N corpus se usa `CORPUS_MANIFEST`, excluyente con
`CORPUS_PATH`, `CORPUS_NAME` y `CORPUS_DOMAINS`. Declarar el manifiesto junto a
cualquiera de esas tres claves es un error de validacion; sin manifiesto ni
terna el instalador no ingiere nada. El formato es texto ASCII, una linea por
corpus y tres campos separados por `|`:

```text
# nombre | dominios separados por coma | ruta al texto
linux_docs | linux | nuevo/linux/linux.txt
scripting_docs | codigo,linux | recuperado/scripting.txt
domotica_docs | domotica | nuevo/domotica
```

Las lineas vacias y las que empiezan por `#` se ignoran, y los espacios que
rodean cada campo se recortan. Una ruta relativa se resuelve desde el directorio
del manifiesto; una absoluta se conserva. Antes de la primera ingesta se valida
el fichero entero: sintaxis, nombres unicos y no vacios, dominios no vacios y
rutas legibles. Los dominios no se contrastan en el instalador con el catalogo
del core: esa validacion pertenece a `knowledge ingest`.

Los corpus se procesan en el orden declarado. Cada uno se ingiere con todos sus
dominios y despues se confirma cada vinculo. Si una ingesta o confirmacion falla,
el instalador aborta nombrando el corpus y conserva la causa del comando. No es
una transaccion: lo ya ingerido permanece. Repetir el setup despues de corregir
el fallo no duplica chunks ni vinculos por la idempotencia indicada arriba.

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

## Las migraciones se reaplican todas, y eso impone una regla

`runtime migrate` aplica TODAS las migraciones en cada ejecucion, en orden, sin
llevar registro de cuales ya corrieron. De ahi un invariante que conviene tener
presente al escribir una nueva:

> **Toda migracion debe poder reaplicarse DESPUES de las posteriores.**

Una que estreche lo que otra mas nueva ensancho rompe el despliegue en la
segunda ejecucion, no en la primera. Medido el 2026-09-21: con un enlace
`summarizes` ya escrito por la 0005, la 0004 volvia a poner su `CHECK` sin ese
valor y el instalador fallaba con `CheckViolation`. La instalacion inicial iba
bien; la repeticion, no.

En la practica, una migracion que amplia una enumeracion comprueba primero si su
valor ya esta admitido y no hace nada si lo esta.

## Lo que el instalador NO hace: abrir el cortafuegos

Las units escuchan donde digan `REST_HOST` y `MCP_HOST`, y el instalador espera
a que los puertos respondan antes de verificar. Pero **no toca el cortafuegos
del huesped**: si la maquina filtra por puerto -`firewalld` con la zona `public`
solo permite `ssh` en una instalacion minima de openSUSE-, el servicio escuchara
en la direccion declarada y aun asi sera inalcanzable desde fuera.

Abrir el puerto es hoy un paso del operador, fuera del alcance de este
instalador, y conviene saberlo porque un despliegue que declara sus servicios
pero no su exposicion esta incompleto.

Publicar mas alla de loopback es ademas una decision con doctrina detras
(`ia_nest_meta` ADR 0011): esta capa no autentica, asi que la exposicion se
declara -que se expone, con que perimetro y con que caducidad- o no se hace.

## Verificacion posterior en maquina real

Los criterios que requieren red, systemd, reinicio o contenedores solo se
cierran en la maquina destino. Alli se ejecutan dos pasadas seguidas, la sonda de
DSN invalido, `knowledge status`, un reinicio completo y, despues, un
`ianest-extended prompt run` desde el directorio personal del operador.
