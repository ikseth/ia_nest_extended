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

### 2. Cerrar y amortizar no son lo mismo

Es el punto que evita un bloqueo: si cerrar dependiera de conscience, y
conscience no existe, **nada se cerraria jamas** y volveriamos al hilo eterno.

- **Cerrar** -pasar a `archivada`- es operativo: lo decide el reloj de
  inactividad o un acto explicito. Es de extended y funciona hoy.
- **Amortizar** es juicio: conscience declara que de ese hilo ya extrajo lo que
  valia. **No cierra nada**; deja su marca encima de un hilo ya archivado.

    estado        activa -> archivada        (extended, reloj o acto explicito)
    amortizada_at null -> marca de tiempo    (conscience; hoy siempre null)

"Activa" significa **no archivada**, y no depende de conscience. El dia que
exista, anade su marca sin redisenar nada.

### 3. Estados explicitos, nunca por omision

El estado es un valor declarado, no la ausencia de una fila o un `null`
interpretado. Modelar por ausencia es justo lo que produjo esta deuda, y ademas
no deja sitio donde poner el tercer estado el dia que aparezca.

Las marcas del ciclo de vida son TIMESTAMPS (`archivada_at`, `amortizada_at`),
no banderas: cuestan lo mismo y dicen cuando.

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
- **Que hace conscience al amortizar**: que engramas genera y con que criterio.
  Aqui solo se le reserva el sitio donde dejar la marca.
- **El borrado.** No hay borrado fisico (ADR 0002): archivar no es purgar, y una
  politica de purga es otra decision.
- **El dueno de `episodic`**, que se debate aparte y no depende de esto.
