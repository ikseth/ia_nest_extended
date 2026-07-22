# Decision 0002: clases de memoria (estrictas / delegadas) y autoridad de escritura

Fecha: 2026-07-18

## Decision

La memoria de `ia_nest_extended` se modela como un REGISTRO de tipos de memoria.
Cada tipo se DECLARA con un esquema comun: namespace, comportamiento de tier
(modo de recuperacion, compresion, ciclo de vida), read-scope, write-scope y
`writer_principal` (dueno de escritura). Sobre ese registro se definen dos clases:

- **estrictas** (basicas): su autor y su dueno de escritura es extended. Son la
  definicion basica de esta capa y son utiles hoy (continuidad conversacional,
  recuperacion por identidad). Extended es a la memoria lo que el core es a la
  inferencia: define las suyas y deja declarar mas.
- **delegadas**: declaradas contra el mismo esquema, pero cuyo dueno de escritura
  y mantenimiento es OTRA capa del ente. `persona`, `historica` y `principles`
  quedan declaradas con dueno `conscience`; existen en el registro pero vacias y
  no escritas hasta que conscience se construya.

Reglas que hacen que las clases signifiquen algo, no solo una etiqueta:

1. **Extended posee los INVARIANTES.** Las 3 lecciones de la cantera (core
   ADR 0011) son reglas de validacion del registro (`memory_type.validate`,
   espejo de `config.validate` del core): rechaza una declaracion que aliasaria
   tiers o derivaria namespace de forma inconsistente. El dueno personaliza
   contenido y politica de ciclo de vida DENTRO de los railes; no puede romper la
   fisica.

2. **Autoridad de escritura por capacidad.** El sustrato FUERZA `writer_principal`:
   rechaza una escritura de un principal que no sea el dueno del tipo. Es control
   de acceso por capacidad (heredado del enfoque capability-based de la cantera:
   "sin capacidad, no hay accion"). Con esto la Leccion 2 (separar lectura de
   escritura) gana dos caras: read-scope != write-scope en la derivacion de
   clave, y la escritura gated por principal.

3. **Lectura uniforme, escritura aislada.** La composicion de enriquecimiento lee
   TODOS los tipos (estrictos y delegados) para armar el prompt; por eso el core
   "usa" la persona escrita por conscience, la consume via enriquecimiento. Pero
   el camino experiencial (write-back tras la respuesta del core) solo puede
   escribir memorias estrictas; nunca las delegadas.

4. **Dogfooding (innegociable).** Las memorias estrictas se implementan A TRAVES
   del mismo contrato de registro y escritura que usaran las delegadas. El
   contrato tiene consumidor real desde el dia uno (extended se come su propia
   comida); conscience se suma despues como otro caller. Sin esto, el contrato
   delegado seria una costura sin consumidor (core ADR 0035) y se pudriria.

5. **Costura de consolidacion.** Conscience NUNCA escribe memorias estrictas, ni
   su contenido ni su estado. Emite un evento de consolidacion
   (`memory.consolidation`) y extended EJECUTA la transicion de estado
   (archivar/superseder/lineage) sobre las estrictas en su nombre. Conscience
   pide, extended actua; el unico que muta memorias estrictas es extended.

6. **Guardarrail (anti-entropia).** El registro admite hoy los consumidores
   nombrables: las estrictas y el unico dueno externo conocido (conscience). No
   es un marketplace de plugins de memoria para modulos hipoteticos (YAGNI; seria
   un ADR 0035 a nivel meta). Cuando exista un tercer modulo con memoria propia,
   se validara que el contrato le sirve.

## Motivo

Recupera la ambicion de la cantera `ia_nest` (memoria multinivel, consolidacion
por hitos, principios que sedimentan un caracter) y la reubica en la doctrina de
capas del ente: el SUSTRATO y el mecanismo del yo viven en extended; el JUICIO que
lo cultiva vive en conscience (core ADR 0033/0034). La cantera ponia memoria y
conciencia "en el centro del core"; la via 2 (core ADR 0031/0035) las separo.

El punto clave, dicho como principio: **el caracter del ente no es mutable por la
experiencia en bruto; solo la reflexion (conscience) reescribe el yo.** Si el
write-back experiencial pudiera escribir `persona`/`historica`/`principles`,
cualquier conversacion cruda envenenaria la identidad. La autoridad de escritura
por capacidad lo impide.

Y evita el error que el core ya pago (ADR 0035): construir logica de conscience
sin conscience. Aqui se construye solo el mecanismo con consumidor hoy (registro,
validacion, escritura de estrictas, lectura uniforme); las delegadas son
declaraciones que su dueno llenara.

## Consecuencia

- La Fase 2 del PLAN se reescribe: contrato de declaracion de tipos + tipos
  estrictos + validacion de las 3 lecciones + registro + autoridad de escritura.
  El roster concreto (que namespaces, que clase, gradiente de tiers) se reconcilia
  en Fase 2, no aqui; este ADR fija el MECANISMO, no la lista.
- El evento `memory.consolidation` es la costura extended<->conscience; se
  detallara (contrato versionado) cuando conscience se construya.
- El motor de almacenamiento queda detras de un port intercambiable; su eleccion
  no se casa en el modelo (core ADR 0009, adoptar antes que construir).
- Impacto de version: ninguno todavia (no hay contrato publico cortado; se corta
  en Fase 7). Entrada en `CHANGELOG.md` bajo No publicado.
