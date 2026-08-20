# Contrato de ia_nest_extended

Estado: propuesta
Version: 0.1 - 2026-08-14

Frontera publica de la capa de enriquecimiento. Pasa a `activo` al cortarse su
primer tag (Fase 7d); hasta entonces describe el objetivo, no una promesa
vigente. Que cuenta como contrato y que lo rompe: `docs/VERSIONADO.md`.

Forma de la composicion entre capas: `ia_nest_meta/docs/ARQUITECTURA_DE_CAPAS.md`
(meta ADR 0007). Este documento la aplica; no la repite.

## Proposito

Ofrecer las capacidades del core ENRIQUECIDAS con memoria, conocimiento y datos
web, mas las capacidades propias de la capa, sin que un consumidor tenga que
saber cuantas capas hay debajo.

## Interfaces publicas

Las mismas capacidades por CLI, REST y MCP, como pieles finas de un unico
servicio en proceso. Ninguna piel llama a otra: las tres llaman al mismo
`ExtendedService`.

La REST escucha por defecto en `127.0.0.1:8001`, configurable con
`IANEST_EXTENDED_REST_HOST` e `IANEST_EXTENDED_REST_PORT`. No autentica: la
autenticacion sigue fuera de alcance y exponerla fuera de loopback es una
decision explicita de la instalacion.

Las rutas se derivan del nombre de capacidad (`prompt.run` -> `/prompt/run`).
Las propias y sobreescritas llaman al servicio unico. Cualquier otra ruta se
reenvia al core por el mecanismo generico, sin consultar `capability.list` ni
su cache. El catalogo fusionado describe; nunca habilita una invocacion.

Los flujos reenviados conservan `text/event-stream` y se retransmiten evento a
evento. Las respuestas JSON reenviadas son opacas. Un error ajeno conserva su
codigo HTTP y sus campos `type` y `origin`; un error propio declara
`origin=ia_nest_extended` (meta ADR 0009).

MCP expone cada herramienta con el nombre exacto de su capacidad, sin alias, y
deriva sus parametros (tipo, obligatoriedad y valores admitidos) del mismo
catalogo declarativo que alimenta las otras pieles. Construir el servidor es
siempre local: declara las capacidades propias y sobreescritas desde el catalogo
local, y las reenviadas desde una cache valida del catalogo del core. Nunca
consulta al core al arrancar.

Sin cache, MCP sirve lo propio y declara que falta el catalogo ajeno en las
instrucciones del servidor; `capability.list` conserva ademas la degradacion
tipada si el core sigue inalcanzable cuando se invoca. La cache solo mejora la
enumeracion: las herramientas reenviadas siguen el camino generico del servicio.

El transporte por defecto es `stdio`. La opcion `sse` escucha en
`127.0.0.1:8091` por defecto, configurable por los argumentos `--host` y
`--port` del servidor MCP. Esto no anade streaming a las herramientas: las
capacidades de flujo quedan fuera de MCP y su proyeccion nula en
`capability.list` declara el hueco, igual que en el core.

## El contrato uniforme

| | capacidades |
|---|---|
| **Reenviadas** sin alterar | las del core que esta capa no enriquece; hoy `runtime.health` y `config.validate` responden por el core, no por la pila |
| **Sobreescritas** (compuestas o enriquecidas) | `capability.list`, `prompt.run`, `reasoning.run`, `task.run` |
| **Propias** | `memory_type.*`, `memory.*`, `knowledge.*` |

El reenvio es GENERICO: no hay codigo por capacidad. Una capacidad que el core
anada es alcanzable a traves de esta capa sin tocar su codigo, y eso se verifica
con una prueba (Fase 7a).

`capability.list` es reflexiva y por eso no se reenvia: declara las capacidades
propias, obtiene el catalogo del core en ejecucion y devuelve la fusion. Una
sobreescritura aparece una vez con la declaracion de extended; una reenviada
conserva todos los campos declarados abajo. Cada entrada anade `provenance`
(`own`, `overridden` o `forwarded`) y la respuesta publica `extended_version` y
`core_version`.

Si el core no esta disponible, la respuesta conserva el catalogo local, deja
`core_version` nulo y publica `error` con la forma tipada del ente. El catalogo
sirve para explicar, nunca para habilitar una invocacion: ninguna capacidad deja
de ser alcanzable por no poder descubrirla.

La CLI deriva banderas tipadas y MCP deriva esquemas de herramienta de los
parametros que el catalogo declara para cada capacidad. En la CLI, un parametro
cuyo nombre colisiona con una bandera que la capa ya posee -identidad,
enriquecimiento o salida- NO se redeclara: la gobierna la bandera propia, y su
ayuda lo dice. Regla unica derivada del dato, nunca una lista de casos por
nombre.

Construir la CLI y MCP es SIEMPRE una operacion local: nunca consulta al core,
ni siquiera alcanzable. Para eso, el catalogo remoto que alimenta las banderas
y herramientas reenviadas se cachea como estado local (no versionado);
`capability.list` es quien la refresca, como efecto de consultar al core en
vivo. Sin cache, o con una cache de un core distinto del configurado, la CLI
conserva las banderas propias y lo ajeno se sigue invocando por `--param`; MCP
conserva las herramientas propias y declara el hueco ajeno.

### Garantia de transparencia

Esta capa reexpone el contrato del core del rango declarado en
`docs/DEPENDENCIAS.md`, **sin alterar su semantica**. Las capacidades
sobreescritas conservan la forma de peticion y de respuesta del core; lo unico
que cambia es que el prompt ejecutado lleva contexto recuperado.

En `task.run`, el enriquecimiento por subtarea requiere suministrar al core el
plan obtenido antes con `task.plan`. Ese camino no re-planifica: si EVALUATE lo
pide, el core corta con `replan_unavailable`. Desactivar el enriquecimiento
recupera el passthrough sin plan y, con el, la capacidad de re-planificacion.
No hay reintento automatico sin plan: seria no determinista y duplicaria coste.

`task.stream` se reenvia SIN enriquecer. Es un hueco conocido: el core no acepta
`plan` ni `requirements` suministrados en esa capacidad. `prompt.stream` tambien
sigue reenviado sin enriquecer.

La presentacion de las capacidades reenviadas es JSON mientras `extended
CR-0004` siga sin resolver. No se inventa render local para respuestas que la
capa no puede describir desde el catalogo.

El catalogo del core NO se re-declara aqui: su hogar es `core
docs/CORE_CONTRACT.md` (convencion transversal 6, meta ADR 0008). Un consumidor
lee ese documento en el rango declarado, y este para lo propio de la capa.

Igual con el **contexto de identidad del request** (`user_id`, `service`,
`session_id`, `domain_tag`, `namespace`): lo define el core y esta capa lo usa
como clave de indexacion. Que subconjunto entra en la clave de memoria, en
`docs/FORMA_ENRIQUECIMIENTO.md`.

### Parametros de extension del enriquecimiento

Viajan con las capacidades sobreescritas y son propios de esta capa:

- activar o desactivar el enriquecimiento completo (desactivado = passthrough:
  ni recuperacion, ni inyeccion, ni write-back),
- desactivar una fuente concreta por nombre,
- dominio explicito, o resolucion automatica por `domain.route`.

Las fuentes son declaradas por la capa, no fijadas por el consumidor: hoy
`memory` y `rag`; `web` en la Fase 6. Un consumidor descubre las disponibles, no
las presupone.

Combinacion contradictoria (desactivar el enriquecimiento y pedir una fuente) es
error tipado, no precedencia silenciosa.

## Capacidades propias

Estado: `implementada` (existe el mecanismo y se expone por las tres pieles) o
`prevista` (nombre reservado, sin implementacion).

### Memoria

| capacidad | proposito | estado |
|---|---|---|
| `memory_type.list` | roster de tipos declarados: namespaces, tier, scopes y `writer_principal` | implementada |
| `memory_type.validate` | valida una declaracion de tipo (invariantes V1-V4) | implementada |
| `memory.recall` | recupera lo que se inyectaria, sin ejecutar inferencia | implementada |
| `memory.write` | escribe un engrama, con autoridad por principal (ADR 0002) | implementada |
| `memory.consolidate` | ejecuta un evento de consolidacion (ADR 0007) | implementada |
| `memory.maintain` | barrido mecanico por umbrales: archiva y promociona | implementada |

`memory.write` y `memory.consolidate` son la costura de `conscience`: emite quien
tiene la autoridad, ejecuta esta capa. La autoridad se aplica en dos niveles,
principal en codigo y GRANT del motor (ADR 0010).

### Conocimiento

| capacidad | proposito | estado |
|---|---|---|
| `knowledge.ingest` | ingiere texto curado en un corpus | implementada |
| `knowledge.status` | cobertura de conocimiento por dominio del core | implementada |
| `knowledge.suggest` | propone dominios para un corpus via `domain.route` | implementada |
| `knowledge.confirm` | confirma un vinculo dominio-corpus | implementada |
| `knowledge.reject` | retira una propuesta, protegiendo la curacion manual | implementada |
| `knowledge.retrieve` | recuperacion RAG suelta, sin inferencia | prevista |
| `knowledge.corpus.list` | corpus y sus vinculos, para presentacion | prevista |

Las dos previstas existen para el consumo de `ia_nest_web`; no se implementan
hasta que ese consumidor las ejerza (core ADR 0035: una costura sin consumidor
real se pudre).

## No capacidades

Esta capa no implementa: inferencia (es del core), juicio de consolidacion ni
personalidad (conscience), regulacion tecnica (pulse), presentacion (web), ni
accion con efecto sobre sistemas externos (`tool_contracts` / `external_*`).

No expone su base de datos: el esquema es interno y se accede por capacidades.

## Reglas de compatibilidad

- Toda capacidad publica tiene contrato versionado y prueba de aceptacion.
- El reenvio no requiere codigo por capacidad; si lo requiriera, se ha roto el
  contrato uniforme.
- CLI, REST y MCP no tienen logica distinta entre si.
- Una capacidad del core reenviada nunca se degrada ni se filtra.
