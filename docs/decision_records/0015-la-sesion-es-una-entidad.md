# Decision 0015: la sesion es una entidad, no una etiqueta

Fecha: 2026-09-22

## Contexto: el hilo no existe en ninguna parte

Extended trabaja sobre HILOS de conversacion, identificados por su sesion y
asociados a un usuario. Esa es su cobertura y su limite: que un hilo evolucione
sin contradecirse. Lo de mas alla -que algo de ese hilo merezca recordarse- es
juicio, y es de conscience (ADR 0007, enmienda del 2026-09-12).

Pero el hilo, como cosa, no esta modelado. Hoy una sesion es una columna de
texto en `engrams`: **existe por haber sido mencionada**. No tiene dueno
declarado, ni fecha, ni estado, ni nombre. No se puede listar, porque no hay
donde mirar.

De esa ausencia salen los dos fallos de la deuda D7, que apuntan en direcciones
opuestas:

- **Se corta por reloj.** `dialog` se archiva a las 4 h de haberse ESCRITO cada
  turno, sin mirar si su sesion sigue viva. Una conversacion de seis horas
  pierde su principio.
- **No se corta nunca donde deberia.** La sesion recordada del servidor no
  rota. Medido el 2026-09-22: diez horas y dos interlocutores distintos dentro
  de un mismo hilo, con una sintesis que los resume como si fueran uno.

Las dos son la misma ausencia. Un temporizador de retencion responde a "cuanto
guardo esto", no a "hasta donde llega este hilo".

## Decision

### 1. La sesion se declara

Una sesion es una entidad con `user_id`, creacion, ultima actividad, estado,
titulo y las marcas de tiempo de su ciclo de vida. Deja de inferirse de que
alguien la nombrara.

### 2. Archivar y cerrar son de duenos distintos

Tres estados en una sola linea de vida, y cada transicion tiene su dueno:

    activa --(reloj; extended)--> archivada --(amortizacion; conscience)--> cerrada

- **activa**: el hilo admite turnos.
- **archivada**: extended la deja FUERA DE SU ALCANCE -no admite mas turnos, su
  `dialog` deja de recuperarse- pero **no la da por terminada**. Sacar algo de
  tu alcance no es declararlo acabado, y extended no tiene con que declararlo.
- **cerrada**: conscience ya la desgloso y genero los engramas si procedia.
  Cerrada NO significa que produjera memoria: significa que **alguien con
  criterio ya la miro**. Un hilo del que no habia nada que extraer se cierra
  igual.

De ahi sale lo que hace util al modelo: **`archivada` es la cola de trabajo de
conscience**. No es una consulta derivada de dos campos, es el estado que dice
"esto esta pendiente de que alguien lo juzgue".

Mientras conscience no exista, NADA llega a `cerrada`. Habra un respaldo
permanente de hilos archivados sin amortizar, y eso es informacion que conviene
ver, no un bloqueo: dice cuanto material lleva el ente esperando a tener quien
lo piense.

"Activa" -lo que se lista y se continua- significa **no archivada**, y esa
transicion es solo de extended. El sistema funciona entero sin el guardian.

### 3. Estados explicitos, nunca por omision

El estado es un valor declarado, no la ausencia de una fila ni un `null`
interpretado. Modelar por ausencia es justo lo que produjo esta deuda, y ademas
no deja sitio donde poner el cuarto estado el dia que aparezca.

Las transiciones dejan TIMESTAMPS (`archivada_at`, `cerrada_at`), no banderas:
cuestan lo mismo y dicen cuando.

### 4. Un solo reloj, y es el del hilo

`dialog` vive mientras su sesion este activa, y se archiva CON ella. El valor de
arranque se queda en las **4 h de hoy**, configurable, deliberadamente sin
cambiarlo: mover el numero a la vez que el modelo haria que la siguiente medida
no supiera a cual de los dos atribuir lo que viera.

Lo que si cambia es su SIGNIFICADO, y se declara: hoy son 4 h desde que se
escribio cada turno; pasan a ser 4 h desde la ultima actividad del hilo. Una
conversacion con turnos frecuentes deja de perder su principio. El pozo
recuperable crece; el contexto inyectado no, porque `dialog_top_k` sigue
acotandolo.

### 5. El titulo sale de lo que ya existe

`thread_summary` ES la descripcion de un hilo, ya implementada y medida. El
titulo es ese resumen recortado, y ponerle nombre a lo que hay es mecanico, no
juicio: se queda en extended.

Consecuencia que hay que respetar: **el titulo no puede haberse archivado antes
que su sesion**. Es el mismo reloj del punto 4.

Cuando el cliente nombra su sesion -`cine_20260926`- el titulo automatico no
hace falta. Es para quien no la nombra.

### 6. El cliente elige el id; el servidor es dueno del ciclo de vida

Un cliente REST guarda su `session_id` y lo manda (ADR 0014). Eso NO le da
potestad sobre cuanto dura: si la sesion caduco, el servidor la archiva, y una
peticion con ese id no la resucita. Insistir no mantiene un hilo vivo.

Como la clave es usuario + sesion, que dos clientes elijan el mismo texto de id
no los mezcla: el dano medido el 2026-09-22 venia del `user_id` compartido.

### 7. Listar sesiones es por usuario

`session.list` devuelve las sesiones del `user_id` que pregunta. No hay vista
global.

Se declara lo que esto es y lo que no: **acota, no protege**. Sin autenticacion,
quien dice ser un usuario ve sus sesiones. Se elige asi porque el dia que el
`user_id` venga de un login la regla ya esta puesta y no hay que reabrirla
(`ia_nest_meta` ADR 0011).

### 8. En la CLI, el hilo se mantiene salvo caducidad o acto explicito

Cerrar un terminal no es terminar una conversacion. El default continua el
ultimo hilo activo; empezar uno nuevo es explicito. Lo que faltaba no era que el
hilo se cortara solo, sino **saber en cual estas**: la CLI lo dice al invocar.

Para hilos paralelos en terminales distintos, una variable de entorno de sesion,
que un fichero unico no permite.

## Consecuencias

- Tabla de sesiones y capacidades nuevas (`session.list`, `session.show`,
  `session.new`). Adicion de contrato: MINOR en la serie pre-1.0.
- El archivado de `dialog` deja de mirar la edad del turno y pasa a mirar la
  actividad del hilo. **Es un cambio de comportamiento**, y se declara para que
  la siguiente pasada de la puerta no lo confunda con otra cosa.
- La puerta no cubre nada de esto: siempre manda identidad y sesion explicitas.
  Hueco declarado, como en el ADR 0014.
- Habilita el ADR 0014: exigir `session_id` tiene sentido cuando hay donde
  consultarlo y crearlo. **Este trabajo va primero.**

## Lo que esta decision NO cubre

- **Autenticacion.** Ni la del listado ni la de nada. Sigue en la frontera.
- **Que hace conscience al amortizar**: que engramas genera, con que criterio y
  en que orden vacia la cola. Aqui solo se declara el estado del que parte
  (`archivada`) y el que deja (`cerrada`).
- **El borrado.** No hay borrado fisico (ADR 0002): archivar no es purgar, y una
  politica de purga es otra decision.
- **El dueno de `episodic`**, que se debate aparte y no depende de esto.
