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

## Enmienda (2026-09-22): `episodic` no era memoria, era el residuo de un hilo

### Lo medido

Sesion real del operador, 2026-09-22, sobre `v0.3.2`. La recomendacion que el
propio modelo dio el dia anterior estaba guardada como
`episodic/facts (fuente: modelo, sin verificar)`, de ambito USUARIO, y encabezaba
el contexto de una conversacion nueva. El modelo la transcribio en vez de
recomendar; al transcribirla metio las palabras del interlocutor en su propia
respuesta, y entonces el anclaje lexico que asigna `stated_by` dejo de poder
distinguir emisores: todo cayo a `unknown`.

Resultado: **ninguna de las cuatro puntuaciones que el operador dio ese dia
llego al almacen**. Control con un `user_id` limpio, mismo codigo, misma
maquina, veinticinco minutos despues:

    ayer   usuario con memoria acumulada    5 extraidos   5 escritos   0 sin atribuir
    hoy    el mismo usuario                 1 extraido    0 escritos   1 sin atribuir
    hoy    usuario limpio                   5 extraidos   5 escritos   0 sin atribuir

La unica variable que cambia entre la segunda fila y la tercera es la memoria
acumulada. El bucle se cierra solo: la respuesta transcrita se guarda como
`dialog`, y al turno siguiente pesa mas.

### El diagnostico no es el veneno

El veneno es el sintoma. Lo que hay debajo es un **error de categoria**:
`episodic` se declaro como memoria del usuario, y lo que guarda es **el residuo
estructurado de un hilo** -frases cortas destiladas de unos turnos, con su
procedencia- que solo significan algo junto a la conversacion que las produjo.

La deuda D6 ya lo habia dicho sin nombrarlo: "la primera puntuacion es 6" es
correcto en su turno y ruido fuera de el. No era un fallo de la extraccion: era
un fragmento de hilo guardado como si fuera un recuerdo de una persona.

Y el ADR 0007 ya lo prohibia desde su enmienda del 2026-08-13: lo durable que
influye ENTRE CONTEXTOS es escritura supervisada del guardian. `episodic` es
durable, influye entre contextos y lo escribe una maquina. La frontera estaba
escrita y no estaba materializada.

### Decision

1. **`episodic` deja de ser memoria.** Pasa a ser **artefactos del hilo**: el
   mismo contenido y la misma maquinaria de procedencia del ADR 0013, con
   **ambito sesion** en lugar de usuario, y con un nombre que dice lo que es.
   Propuesta: `thread_artifacts`, a fijar en el roster.

2. **Un artefacto no se moja.** Registra "el interlocutor dijo X", nunca "X es
   verdad". Es lo que `stated_by` ya hacia por dentro; ahora lo dice tambien el
   tipo.

3. **`semantic` y la consolidacion (Fase 4) pasan a conscience.** Sin episodicos
   durables no hay sujeto que consolidar.

4. **Nada que extended escriba sobrevive a su hilo.** No es una carencia de la
   capa: es su limite. Curar -decidir que se recuerda y que no, en funcion de la
   personalidad y del valor que se dio a una conversacion- es juicio.

5. **Lo que un hilo archivado entrega al guardian**: los turnos crudos, los
   artefactos con su procedencia, el resumen del hilo, y magnitudes contables.
   Un hilo archivado deja un paquete de traspaso completo, y mejor que el de
   hoy: conscience destila del crudo en vez de heredar una destilacion mecanica
   que ya perdio referentes.

6. **Magnitudes, nunca valoracion.** Extended puede contar turnos, duracion,
   correcciones del interlocutor, contradicciones anotadas, entidades distintas
   mencionadas. **No puede emitir "este hilo fue importante"**: eso es el
   criterio, y el criterio es de conscience. Las magnitudes son insumo del
   juicio, no el juicio. Es el mismo test de frontera del ADR 0007.

### Consecuencias

- **Se revoca la opcion A del 2026-08-13** en lo que tenia de "extended sirve
  SOLA" con memoria entre sesiones. Se hace a sabiendas y con medida delante: la
  aproximacion mecanica no era neutra, degradaba la conversacion. Una memoria
  envenenada es peor que no tener memoria.
- **La Fase 3 se queda** en escribir `dialog` y los artefactos del hilo. **La
  Fase 4 sale** de esta capa.
- **L2 de la puerta se retira, y solo L2**: es la unica linea que cruza de
  sesion. L3, L4a y L4b ocurren dentro de una, y su maquinaria se conserva
  entera. Ese es el motivo de que esta enmienda no sea gratis pero tampoco
  arrase: lo medido esta semana sigue midiendo.
- **Los engramas `episodic` existentes no se pueden reescalar.** Hoy se escriben
  con `session_id` nulo: no hay hilo al que devolverlos. Se archivan, y siguen
  direccionables porque no hay borrado fisico. El operador debe saber que en el
  primer despliegue su memoria de usuario pasa a archivo.
- Renombrar y reescalar un tipo publicado toca `memory_type.*`: MINOR en la
  serie pre-1.0, con nota de migracion.

### Lo que esta enmienda NO cubre

- Que hace conscience con la cola de hilos archivados, con que criterio y en que
  orden. Aqui solo se le deja el material y las magnitudes.
- El olvido. Archivar no es purgar, y sigue sin haber borrado fisico.
- La frontera del hilo, que la fija el ADR 0015.
