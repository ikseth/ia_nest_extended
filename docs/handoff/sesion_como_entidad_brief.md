# Handoff A: la sesion pasa a existir (modelo y reloj)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, banco y laboratorio. NUNCA quien implementa.
Fecha: 2026-09-22.
Base: `main` con las PR #55 y #56 mergeadas (ADR 0014 y ADR 0015 presentes).

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `docs/decision_records/0015-la-sesion-es-una-entidad.md` ENTERO. Es el
   encargo; esto solo lo acota.
2. `docs/PLAN.md`, deuda D7.
3. `docs/ROSTER_MEMORIA.md`, filas `dialog` y `thread_summary`.
4. `docs/DESPLIEGUE.md`, el invariante de migraciones: **toda migracion debe
   poder reaplicarse DESPUES de las posteriores**, porque se reaplican todas en
   cada arranque.

## Alcance: SOLO el modelo y el reloj

Esta entrega no anade superficie. Nadie ve un comando nuevo ni una capacidad
nueva. Lo que cambia es que el hilo pasa a existir como entidad y que el
archivado deja de mirar la edad del turno.

**NO entra en este encargo** -es la entrega B y se hace aparte-:

- capacidades `session.list`, `session.show`, `session.new`,
- subcomandos de sesion en la CLI y el aviso de en que hilo estas,
- el titulo derivado de `thread_summary`,
- exigir identidad en REST/MCP (ADR 0014, entrega C).

Si algo de esto te parece necesario para que A funcione, PARA y pregunta: es
senal de que el corte esta mal hecho, y eso lo decide el disenador.

## Lo que se pide

### 1. Tabla de sesiones y migracion

Migracion nueva (`0006_sessions.sql`), con el invariante de reaplicacion.

Columnas minimas: identificador de sesion, `user_id`, `created_at`,
`last_activity_at`, `estado`, `archivada_at`, `cerrada_at`. La clave es
**usuario + sesion**: dos usuarios pueden usar el mismo texto de id sin
mezclarse.

`estado` es un valor declarado con tres posibles -`activa`, `archivada`,
`cerrada`-, nunca inferido de un `null` (ADR 0015, punto 3). Las transiciones
dejan su timestamp.

**Backfill obligatorio en la migracion.** Hoy hay engramas con sesiones que no
existen en ninguna tabla. La migracion crea una fila por cada
`(user_id, session_id)` distinto de `engrams`, con `created_at` = el minimo y
`last_activity_at` = el maximo de sus engramas. El estado se deriva del reloj
del punto 3. Sin backfill, un despliegue existente queda con sesiones huerfanas.

### 2. Alta y latido

- Al escribir el primer turno de una sesion, se crea su fila.
- En cada turno, `last_activity_at` se actualiza.
- **Escribir en una sesion `archivada` o `cerrada` es un error tipado** que
  nombra la sesion y su estado. No se resucita ni se crea otra por su cuenta:
  el servidor es dueno del ciclo de vida (ADR 0015, punto 6).

### 3. Un solo reloj, y es el del hilo

Una sesion pasa a `archivada` cuando lleva mas de `session_inactivity_seconds`
sin actividad. Lo hace el barrido de `maintain`, no una consulta perezosa.

**El valor es el de hoy, 4 horas, y NO se toca.** El ADR lo dice y el motivo
importa: si movieramos el numero a la vez que el modelo, la siguiente medida no
sabria a cual de los dos atribuir lo que viera.

Cambio de clave de configuracion: `dialog_hot_window_seconds` pasa a
`session_inactivity_seconds`, con el mismo valor por defecto. **No crees un
alias de compatibilidad**: la clave vieja desaparece, y se anota en el CHANGELOG
como cambio de configuracion. Ningun despliegue conocido la fija.

### 4. `dialog` y `thread_summary` viajan con su sesion

`find_dialogs_to_archive` **deja de mirar la edad del turno**. Al archivarse una
sesion se archivan con ella sus `dialog` y su `thread_summary`.

Esto es un CAMBIO DE COMPORTAMIENTO declarado: una conversacion con turnos
frecuentes deja de perder su principio. El pozo recuperable de un hilo largo
crece; el contexto inyectado no, porque `dialog_top_k` lo sigue acotando.

### 5. La CLI no puede quedar rota entre A y B

Hoy la CLI recuerda una sesion en un fichero. Con el punto 2, en cuanto esa
sesion se archive, la CLI empezaria a dar error y no tendria como salir hasta
que llegue la entrega B.

Lo minimo para evitarlo, y NADA mas: al resolver la sesion recordada, si esta
archivada o cerrada, se genera una nueva, se persiste y **se informa por una
linea** de que se empezo un hilo nuevo. Sin listados, sin nombres, sin
subcomandos: eso es B.

## Criterios de aceptacion, falsables

1. Una sesion con actividad cada menos de 4 h **no se archiva**, por larga que
   sea, y sus primeros turnos siguen siendo recuperables.
2. Una sesion sin actividad durante mas de 4 h queda `archivada`, con su
   `archivada_at`, y sus `dialog` y `thread_summary` archivados con ella.
3. Escribir en una sesion archivada devuelve error tipado que la nombra.
4. Dos usuarios con el mismo texto de `session_id` no se mezclan.
5. La migracion **backfillea** las sesiones existentes y **se puede reaplicar**
   despues de si misma sin error.
6. Ningun estado se infiere de un `null`.
7. La CLI, con su sesion recordada ya archivada, arranca un hilo nuevo e informa.
8. Sin regresion: `python -m pytest -q` con `IANEST_EXTENDED_TEST_DSN` definido,
   **verde y sin skips**.

## Un cambio, una medida

No aproveches para arreglar el prompt de sintesis, ni para tocar L4a de la
puerta, ni para mover umbrales. Los dos primeros estan abiertos y decididos
aparte; el tercero se calibra con medida propia.

## Que entregar

Rama nueva desde `main`, commits con mensaje en el estilo del repo -que cuentan
POR QUE, no que ficheros se tocaron-, `CHANGELOG.md` actualizado bajo
`[No publicado]` con el cambio de clave de configuracion y el cambio de
comportamiento del archivado, y el resultado EXACTO de pytest. Sin push, sin
tags, sin tocar el laboratorio.
