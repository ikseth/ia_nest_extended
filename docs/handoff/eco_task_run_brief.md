# Handoff de implementacion: D8, `task.run` deja de re-responder el historial

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus sobre el banco y el laboratorio. NUNCA quien implementa.
Fecha: 2026-09-29.
Base: `main`, su ultimo commit, con `v0.4.0` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PLAN.md`, deuda **D8** entera, y la Fase 7b (`task.run` sobreescrito).
3. `docs/FORMA_ENRIQUECIMIENTO.md`.
4. `docs/decision_records/0013-...md` (procedencia): por que `dialog` guarda las
   palabras literales del interlocutor y que depende de ello.
5. En el codigo: `ExtendedService.task_run` (`src/ianest_extended/service.py`) y
   como la sintesis de hilo invoca su modelo de apoyo
   (`enrichment.py`, `resolved_synthesis_model` y `core.prompt_run`).

## Por que existe este encargo, medido

Seis hilos reales del operador por `task.run`, 2026-09-29: en cinco la respuesta
de un turno reproduce respuestas anteriores y se corta. Reproducido en dos
sesiones limpias con las mismas tres preguntas: por `task.run`, eco en los turnos
2 y 3; por `prompt.run`, respuestas limpias.

Causa, en `task_run` hoy:

1. `task.plan` recibe la pregunta sola: el plan ignora el hilo.
2. `compose_prompt(memory_bundle.context, prompt)` se envia como el prompt de
   `task.run` del core, que lo usa como `objective` de cada subtarea y como
   `Task:` del combinador. El combinador reproduce lo que ve en la tarea.

## Lo que se pide, en una frase

Que, cuando hay contexto de memoria, `task.run` enriquecido **reescriba la
pregunta como peticion autonoma** a partir de ese contexto antes de planificar,
y que todo lo que va al core -plan, subtareas, combinacion- use esa peticion y
**nunca el contexto de memoria crudo**.

## Decisiones de diseno (reconciliadas el 2026-09-29; no las reabras)

### 1. La reescritura: entrada, salida y cuando ocurre

- Entrada: el contexto que hoy compone `enricher.recall(memory_identity,
  prompt, include_memory=plan.use_memory)` y la pregunta literal.
- Salida: UNA peticion en texto, autonoma -entendible sin el hilo-, en el
  idioma de la pregunta, que resuelve referencias ("continua", "el plato del
  jueves", "y para 13 anos?") e incorpora las restricciones del hilo que
  apliquen (por ejemplo "dieta mediterranea, economicas"). No responde la
  pregunta ni resume el hilo.
- Solo si el contexto de memoria NO esta vacio. Si esta vacio, la pregunta pasa
  tal cual y no hay llamada: comportamiento identico al actual.
- Se invoca como la sintesis de hilo: `core.prompt_run` con modelo explicito.

### 2. Una clave, opcional

`condense_model` (`IANEST_EXTENDED_CONDENSE_MODEL`), opcional; sin valor usa el
modelo de extraccion, igual que `synthesis_model`. Vacia es error de
configuracion. No hay clave de activacion: es la correccion de un defecto, no
una funcion opcional.

### 3. Que recibe cada pieza

    pieza                         hoy                          tras el cambio
    task.plan                     pregunta literal             peticion autonoma
    RAG por subtarea              prompt de la subtarea        igual (ya sale del plan nuevo)
    task.run del core (objective) contexto + pregunta          peticion autonoma, SIN contexto
    write-back                    pregunta literal             pregunta literal (sin cambio)

Con `plan_payload` suministrado no se planifica, pero el `objective` tambien es
la peticion autonoma.

### 4. Si la reescritura falla, se degrada hacia la pregunta, no hacia el eco

Error de la llamada, respuesta vacia, o respuesta mas larga que un limite
acotado (4 veces la longitud de la pregunta mas 400 caracteres): se usa la pregunta
literal SIN contexto y se registra la degradacion en la traza. Nunca se vuelve a
anteponer el contexto crudo. El turno sigue adelante.

### 5. Procedencia intacta

La peticion reescrita es efimera: no se escribe en ningun tipo de memoria. El
`dialog` del turno guarda la pregunta literal, `stated_by=user`, como hoy. La
extraccion del write-back trabaja sobre la pregunta y la respuesta, no sobre la
reescritura.

### 6. Traza

El evento `task.run` declara si hubo reescritura, su modelo, su latencia y, si la
hubo, el motivo de degradacion. Sin el texto de la pregunta ni de la
reescritura: la telemetria no lleva contenido.

## Lo que NO entra (y si lo haces, esta mal)

- `prompt.run`, `prompt.stream` y `reasoning.run`: componen el contexto para un
  solo modelo, sin combinador. `prompt.run` se midio limpio; los otros dos no se
  han medido y, si mostraran algo parecido, sera otro encargo. No se tocan.
- La sintesis de hilo, la extraccion, los umbrales o el roster.
- El core. Si para cumplir algo hiciera falta cambiar el core, PARA: es un CR.
- Guardar la reescritura, mostrarla como memoria o usarla en el write-back.

## Criterios de aceptacion (falsables)

Los de PostgreSQL se ejecutan; hay banco. No los declares "no ejecutados" sin
intentarlo.

1. **Sin memoria, nada cambia.** Con contexto de memoria vacio, o con
   `--no-use-memory`, no hay llamada de reescritura y lo que recibe el core es
   identico al actual, bit a bit.
2. **Plan con la peticion.** Con contexto no vacio, `task.plan` recibe la
   peticion reescrita, no la literal (core falso que registra lo recibido).
3. **El core nunca ve el contexto crudo.** El prompt de `task.run` del core es la
   peticion reescrita y no contiene el bloque de contexto de memoria; tambien con
   `plan_payload` suministrado.
4. **Degradacion.** Error, vacio y exceso de longitud de la reescritura caen a
   la pregunta literal sin contexto, y la traza declara el motivo.
5. **Procedencia.** El `dialog` del turno guarda la pregunta literal con
   `stated_by=user`; ningun engrama contiene la reescritura (comprobado por
   CONSULTA).
6. **Sin enriquecimiento, sin cambio.** Con `--no-enrich` el camino es identico.
7. **Clave en el esquema**, con su defecto al modelo de extraccion, fijable por
   entorno y rechazando el valor vacio.
8. **Traza** con los campos del punto 6.
9. **Sin regresion.** Suite completa en verde CON PostgreSQL y sin skips.

## Lo que NO verifica este encargo

La calidad de la reescritura y la desaparicion del eco se miden en el
laboratorio, repitiendo los seis hilos del operador del 2026-09-29 tal cual:
ningun turno reproduce una respuesta anterior, todos terminan con
`finish_reason=stop`, y las referencias al hilo se resuelven. Esa medida la hace
Opus y NO forma parte de esta entrega.

## Impacto de version

Cambio de comportamiento de `task.run` enriquecido que corrige un defecto, mas
una clave de configuracion opcional nueva: **MINOR** en la serie pre-1.0, por la
clave. El contrato de la capacidad no cambia.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x, banco incluido).
