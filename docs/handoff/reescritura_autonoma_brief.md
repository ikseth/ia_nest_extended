# Handoff de implementacion: cierre de D8 (reescritura autonoma y plan con ciclo)

Destinatario: agente codificador (Codex).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus sobre el banco y el laboratorio. NUNCA quien implementa.
Fecha: 2026-10-13. RECONCILIADO con el operador el 2026-10-13.
Base: `main`, con `v0.5.1` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PLAN.md`, deuda **D8**.
3. `docs/handoff/eco_task_run_brief.md`: lo ya entregado en `v0.5.0`.
4. En el codigo: `_task_condense_prompt` y `_condense_task_prompt`
   (`src/ianest_extended/service.py`) y sus pruebas en `tests/test_phase7b.py` y
   `tests/test_d8_postgres.py`.

## Por que existe este encargo, medido

Seis hilos reales del operador por `task.run` sobre `v0.5.1` (23 turnos): el eco
desaparece, pero en tres turnos la respuesta repite el contenido del turno
anterior. Reproducida la reescritura en el laboratorio, el texto de
instrucciones actual a veces devuelve una peticion que NO es autonoma:

    "Podrias darme una nueva lista, pero incluyendo la receta?"
       -> "¿Podrias darme una nueva lista incluyendo la receta?"

El planificador recibe eso sin saber de que lista se habla. Probado en el
laboratorio un texto mas estricto, en espanol, sobre diez turnos de esos hilos
con el modelo por defecto: nueve salen autonomas y sin arrastrar contenido de
las respuestas. Una variante con una regla mas fue PEOR; no la reintroduzcas.

Ademas, en dos pasadas de los seis hilos salio una vez en cada una HTTP 400
`PlanDependencyError: pipeline plan contains a cycle` (origen core): el
planificador del propio core (`task.plan`) emite a veces un plan con
dependencias circulares y el core lo rechaza en vez de sanearlo. Es defecto del
core (va como CR aparte), pero una vez de cada ~23 turnos basta para que el
criterio "todos los turnos terminan" no se cumpla. Repetida la misma pregunta,
pasa.

## Lo que se pide, en dos frases

1. Sustituir el texto de instrucciones de la reescritura por el de abajo, tal
   cual.
2. Cuando extended ha pedido el plan y el core responde `PlanDependencyError`,
   pedir el plan otra vez, UNA sola vez.

## El texto, literal

`_task_condense_prompt(context, prompt)` devuelve exactamente esto (las lineas
se unen con un salto de linea; `{context}` y `{prompt}` son los argumentos):

    Reescribe la PETICION del usuario como una sola peticion autonoma, que se entienda sin haber leido la conversacion.
    Reglas:
    - Si la peticion ya se entiende sola y no depende de la conversacion, devuelvela tal cual.
    - Sustituye toda referencia a la conversacion ("el plato del jueves", "esa lista", "continua", "y para...") por aquello a lo que se refiere, nombrandolo.
    - Di de que tema se habla y arrastra las condiciones que el usuario puso antes y que sigan aplicando.
    - Conserva TODO lo que la peticion pide de nuevo: no quites matices, ejemplos ni correcciones del usuario.
    - De las respuestas anteriores toma solo el NOMBRE de aquello a lo que la peticion se refiere; no copies su contenido ni anadas datos que el usuario no ha pedido.
    - No respondas, no resumas, no expliques. Devuelve solo la peticion reescrita, en el idioma del usuario, sin encabezados ni formato.
    <linea en blanco>
    MEMORIA DE LA CONVERSACION:
    {context}
    <linea en blanco>
    PETICION DEL USUARIO:
    {prompt}

Sin acentos, como el resto de textos de la capa.

## El reintento del plan

- Solo en el camino en que `task_run` pide el plan al core (`plan_payload` no
  suministrado). Con plan suministrado por el cliente, el error se propaga como
  hoy: el plan es suyo.
- Disparador: un error del core (el `DownstreamError` que ya transporta sus
  errores) cuyo `type` es `PlanDependencyError`, lanzado por `task.plan` o por
  `task.run`. Ningun otro tipo de error se reintenta.
- Reaccion: volver a pedir `task.plan` con la misma peticion autonoma y repetir
  el camino (enriquecido de subtareas y `task.run`). Una sola vez. Si vuelve a
  fallar, se propaga ese segundo error, intacto.
- La reescritura NO se repite: se reutiliza la peticion ya obtenida.
- El evento `task.run` de telemetria anade `plan_retried` (booleano).

## Lo que NO entra (y si lo haces, esta mal)

- Cuando se reescribe, el limite de longitud, la degradacion, la traza (salvo
  `plan_retried`), la clave `condense_model` o su defecto: todo queda como en
  `v0.5.0`.
- Reintentar otros errores, mas de una vez, o con plan suministrado. Sanear el
  plan en extended (quitar dependencias): eso es del core.
- Registrar o guardar el texto reescrito.
- `prompt.run`, `reasoning.run`, la sintesis, la extraccion, el core.

## Criterios de aceptacion (falsables)

1. **Texto exacto.** Una prueba compara la salida de `_task_condense_prompt`
   con el texto de arriba para un contexto y una peticion dados.
2. **Las pruebas que reconocen la llamada de reescritura por su comienzo** (por
   ejemplo los nucleos falsos que miran `prompt.startswith(...)`) se adaptan al
   comienzo nuevo, y se declara cuales.
3. **Reintento.** Con un core falso cuyo `task.plan` devuelve primero un plan
   que provoca `PlanDependencyError` y despues uno valido: la operacion termina
   bien, `task.plan` se llamo dos veces, la reescritura una, y la telemetria
   dice `plan_retried=true`. Si falla las dos veces, se propaga el segundo
   error tal cual y `task.plan` se llamo dos veces. Con plan suministrado, cero
   reintentos. Otro tipo de error del core, cero reintentos.
4. **Nada mas cambia.** Los criterios 1 a 8 de `eco_task_run_brief.md` siguen
   pasando con sus pruebas.
5. **Sin regresion.** Suite completa en verde CON PostgreSQL y sin skips.

## Lo que NO verifica este encargo

La calidad de la reescritura con modelos reales: se mide en el laboratorio
repitiendo los seis hilos del operador. Lo hace Opus.

## Impacto de version

Correccion sin cambio de contrato: **PATCH** (`0.5.2`). `plan_retried` es un
campo nuevo de telemetria, aditivo.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x, banco incluido).
