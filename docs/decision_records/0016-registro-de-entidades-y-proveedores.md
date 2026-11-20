# Decision 0016: registro de entidades, primera entrega (proveedores y confianza)

Fecha: 2026-11-20
Estado: aceptado (diseno en meta H12P3 y meta ADR 0018; entrega en meta H12P7)

## Contexto

Meta ADR 0017 (el marco de la conversacion) y 0018 (el catalogo de recursos)
ponen en extended la memoria de con quien se habla y de que hay. Meta H12P3
fija como se guarda: un solo registro de entidades (el de este ADR 0004), con
clases y lista cerrada de hechos, claves externas con espacio de nombres, lo
observado separado de lo curado, historico de solo anadir, principal
`operator` y un fichero de siembra que aplica el instalador.

Hoy la tabla `entities` existe (ADR 0004) pero sin uso real: escribir
sobrescribe el perfil sin historico, solo se busca por `id`, no hay capacidad
ni CLI, y `Principal` solo tiene `extended` y `conscience`.

Meta H12P7 (2026-11-20) parte la entrega. El conector con Home Assistant, que
daria areas y aparatos, se aparca en meta `H13`. Esta primera entrega deja el
registro completo y una sola clase con consumidor hoy: `provider`, con su
confianza, que el core necesita para consultar solo lo confiado dentro del
techo (meta ADR 0018, punto 2; `extended CR-0006`, tramo A).

## Decision

### 1. Un registro, con clases y lista cerrada

`entities` sigue siendo el unico registro. Cada clase (`kind`) declara en un
solo sitio del codigo sus hechos observados y sus hechos curados. Un hecho
fuera de la lista hace fallar la escritura o la siembra.

Clases de esta entrega:

| Clase | Observado | Curado |
|---|---|---|
| `provider` | `name` | `trusted` (booleano) |

Despues, por adicion a la lista: `person`, `device` y `home` (meta `H12`,
tanda B), `area` y `appliance` (meta `H13`). Ninguna entra sin consumidor
(core ADR 0035).

### 2. Lo observado y lo curado tienen duenos distintos

- Lo observado solo lo escribe `extended` (el refresco, mecanico, como el
  etiquetado de `entity_refs` del ADR 0004).
- Lo curado solo lo escriben `operator` y `conscience`.

Es la autoridad por capacidad del ADR 0002, aplicada por partes de la fila.

### 3. Claves externas con espacio de nombres

Tabla `(namespace, external_id) -> entity_id`, unica entre las claves vigentes;
el id de la entidad es siempre suyo y una entidad puede tener varias claves.
Las claves guardan cuando se anadieron y cuando se retiraron. Una clave sin
entidad no crea nada. En esta entrega solo se usa `provider:<nombre>`; los
espacios `directory`, `account:<cuenta>` y `seed` llegan con sus clases.

### 4. Fila actual mas historico de solo anadir

La fila de `entities` es la version actual. `entity_versions` guarda, en la
misma transaccion, la copia completa de cada version (clase, nombre, alias,
observado, curado, estado), su autor (principal) y su origen (refresco, CLI o
siembra con su huella). Lo que no cambia nada no crea version. Retirar es una
version mas con estado `retired`; no hay borrado fisico (ADR 0002).

### 5. Proveedores: el techo lo pone la operacion, la confianza el operador

- El techo es la lista de proveedores a los que el ente puede conectarse,
  declarada por la operacion (configuracion del laboratorio, la misma que lee el
  core). Extended la recibe por configuracion.
- El refresco crea `provider:<nombre>` para cada proveedor del techo, sin
  confianza, y retira (con version) el que sale del techo.
- La confianza es el hecho curado `trusted`. En cada turno extended manda al
  core los proveedores vigentes, confiados y dentro del techo. Confiar fuera
  del techo no hace que se consulte nada: la memoria solo resta.

### 6. Interfaz y siembra

- Interfaz `entity.put`, `entity.retire`, `entity.get`, `entity.list`,
  `entity.history`, `entity.refresh` y `entity.apply` (fichero entero, con plan
  previo), hoy solo por la CLI de la maquina de extended, con principal
  `operator` (nuevo). Ni REST ni MCP escriben entities.
- Siembra: un fichero TOML (`ENTITIES_SEED` en el instalador) con
  `[[entity]]`, `key`, `kind` y hechos curados. Se valida entero (clase, lista
  cerrada, claves repetidas, proveedor dentro del techo) y se aplica en una
  transaccion, todo o nada; un error falla nombrando la entrada.
- Propiedad: lo que declara la siembra es de la siembra. Un hecho sembrado
  cambiado por la CLI vuelve a su valor en el siguiente apply (el plan lo
  ensena); lo que desaparece del fichero se retira solo si lo creo la siembra.
  Reaplicar sin cambios da plan vacio y ninguna version.
- Instalador: migraciones, refresco, validacion y apply, en ese orden.

## Consecuencias

- Migracion nueva, principal `operator`, capacidades `entity.*` en la CLI y
  parte `trusted_providers` del contexto del turno hacia el core. Adicion de
  contrato: MINOR en la serie pre-1.0.
- El core consulta la interseccion solo cuando entregue `extended CR-0006`
  tramo A. Hasta entonces extended no manda el campo y nada cambia.
- `entity.unresolved` (claves sin entidad) llega con el marco (tanda B), que es
  quien las produce.

## Lo que esta decision NO cubre

- Las clases del marco y `session_frames` (meta H12P3 D1 y D6; tanda B).
- Areas, aparatos, resumen y preseleccion (meta `H13`).
- Autenticacion de principales entre capas: por eso hoy solo escribe la CLI.
