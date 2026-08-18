# Handoff de implementacion: fase 7b (reasoning.run y task.run sobreescritos)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-18
Base: `main`, su ultimo commit (`f91abcd`).

Estado de contrato: reconciliado. Gobiernan `extended ADR 0011`, `meta ADR 0007`,
`core ADR 0040/0047/0048` y `docs/POLITICA_WRITEBACK.md`. No hay diseno abierto
en esta tarea.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/POLITICA_WRITEBACK.md`: que se persiste. Ya esta reconciliado desde
   julio y esta fase NO lo cambia.
3. `docs/handoff/fase_7a_brief.md` y `fase_7a_entrega.md`: la superficie sobre la
   que se construye.
4. `core docs/CORE_CONTRACT.md`, secciones `task.plan` y `task.run`. NO se copia
   aqui: se referencia (convencion transversal 6).

No hace falta releer el resto del corpus doctrinal para esta tarea.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Estado del core, verificado en laboratorio el 2026-08-18

El core tiene su linea v0.4 completa en `main` (`705941e`), SIN tag
(`pyproject.toml` sigue en 0.3.0). Esta fase se implementa contra ese `main`, y
eso se declara: `docs/DEPENDENCIAS.md` NO se toca todavia, porque mover el rango
a `>=0.4` apuntaria a una version que no existe. El rango se mueve cuando el core
corte v0.4.0, y hasta entonces la dependencia real queda escrita aqui.

Cambio que invalida una premisa del PLAN: `task.run` YA NO es SSE. Devuelve JSON
por `POST /task/run` y el flujo vive en `task.stream` (`core ADR 0046`, enmienda
D5-a). Sobreescribir `task.run` NO obliga a hablar streaming.

## Objetivo

Cerrar las dos sobreescrituras que faltan del contrato uniforme:
`reasoning.run` (enriquecimiento upfront, igual que `prompt.run`) y `task.run`
(enriquecimiento POR SUBTAREA via `task.plan`).

## Dentro de fase 7b

### 1. `reasoning.run` sobreescrito

Mismo camino que `prompt.run`: recall -> composicion dentro del presupuesto ->
llamada al core -> write-back. No hay diseno nuevo; se reutiliza `MemoryEnricher`.

Unica diferencia a respetar: la respuesta de `reasoning.run` tiene su propia
forma. Regla de la fase 7a sin cambios -TIPADO donde se sobreescribe-: se tipa lo
que esta capa necesita interpretar (el texto final, para el write-back, y la
traza), y el resto del payload viaja intacto al llamante.

Va primero porque es barato y porque `docs/EXTENDED_CONTRACT.md` ya promete las
tres capacidades sobreescritas: cortar el tag de la fase 7d con `reasoning.run`
sin enriquecer publicaria un contrato falso.

### 2. `task.run` sobreescrito: el flujo

    1. task.plan            se pide al core con el prompt y la identidad
    2. enriquecer           se edita SOLO plan[i].prompt, por subtarea
    3. task.run(plan, ...)  se envia de vuelta

Reglas duras, todas de `core ADR 0048`:

- `requirements` y `effort` se copian TAL CUAL. No se modelan, no se recalculan,
  no se filtran. La contabilidad de cobertura vive en `requirements[].covered_by`
  y se rompe si se tocan los indices.
- `params` NO se devuelve. Es un informe del core, no una entrada.
- Dentro de `plan[]` solo se edita `prompt`. `index`, `domain`, `depends_on` y
  cualquier campo que el core anada viajan intactos.
- Si el core anade un campo hermano nuevo a la respuesta de `task.plan`, debe
  llegar a `task.run` sin que esta capa lo conozca. Copiar por lista blanca de
  campos conocidos es exactamente lo que `ADR 0048` quiere evitar: se copia el
  objeto y se edita lo propio.

### 3. Donde va cada fuente, y por que

Verificado en el codigo del core: con plan suministrado, el `prompt` de nivel
superior NO llega a las subtareas. Alimenta COMBINE (`Task: {prompt}\nResults:
...`) y EVALUATE. Las subtareas solo ven su propio `plan[i].prompt`.

De ahi la colocacion:

| Fuente | Donde | Motivo |
|---|---|---|
| RAG | `plan[i].prompt`, gateado por el `domain` YA RESUELTO de esa subtarea | Es el motivo entero de `extended CR-0001`: cada subtarea recibe solo el conocimiento de SU dominio |
| Memoria experiencial y tipos delegados | `prompt` de nivel superior | Llega a COMBINE y EVALUATE, o sea a la respuesta que el usuario lee, sin multiplicar por N |

Consecuencia que se declara y no se disimula: **en una tarea, la memoria informa
la combinacion, no la ejecucion de cada subtarea.** Es deliberado. Meterla en
cada subtarea multiplica su coste por el numero de subtareas, que es la queja
literal de `CR-0001` contra el enriquecimiento upfront.

NO se llama a `domain.route`: el plan ya trae el dominio de cada subtarea
resuelto con la precedencia del core. Llamarlo seria pagar dos veces por el mismo
dato.

### 4. Presupuesto por subtarea: `rag_max_tokens`, sin clave nueva

Se aplica `rag_max_tokens` (hoy 500) POR SUBTAREA en el camino de tarea. No se
anade clave de configuracion: la medida valida la que ya existe.

Medido en laboratorio el 2026-08-18 contra `705941e`, un factor controlado y tres
repeticiones por tamano:

    ctx/subtarea   gasto real   concesion del core   respuesta
         0            2.570           8.000          1.187-1.585 chars
       500            4.330           8.000          1.071-1.523
     1.500            7.960           8.000          1.090-1.839
     3.000           10.640           8.000            112-479     <- desplome

Dos hechos que gobiernan el numero:

1. La concesion del core es fija (`base + per_subtask * n`) y NO crece porque
   esta capa inyecte. A 1.500 por subtarea se gasta el 100% de lo concedido; a
   3.000, el 133%. Cada token inyectado por subtarea cuesta ~3 tokens de gasto
   total, porque entra en la subtarea y ademas viaja al combinador.
2. A 3.000 la respuesta se desploma a una decima parte, y el core lo reporta como
   `task_done`, `requirements_covered: True`, `degradations: []`. El fallo es
   INVISIBLE a la telemetria del core.

500 es el unico punto medido que cumple las dos condiciones: 54% de la concesion
y calidad indistinguible del control. El precipicio esta entre 1.500 y 3.000 y no
se acota: el punto de operacion se elige con margen.

Este numero es un punto de partida afinable en laboratorio, no una constante
(`docs/POLITICA_WRITEBACK.md`: el lab es el banco de finetuning de estos numeros).

El presupuesto de memoria en el `prompt` de nivel superior (`memory_budget_tokens`,
hoy 1500) NO esta medido para el camino de tarea. Se deja como esta y se mide en
el criterio de aceptacion 6.

### 5. Costes declarados del camino enriquecido

Con plan suministrado el core NO re-planifica. Medido en 18 ejecuciones: 16
terminaron en `task_done`, 1 en `replan_unavailable` y 1 en `max_iterations`. En
las 18, `degradations` vacio y `requirements_covered: True`.

Se declara en `docs/EXTENDED_CONTRACT.md`, en la garantia de transparencia: una
`task.run` enriquecida pierde la capacidad de re-planificar, y `--no-enrich` la
recupera porque entonces la peticion viaja sin plan. No se intenta mitigarlo en
codigo: reintentar sin plan seria no determinista y gastaria el doble.

### 6. Write-back de una tarea

Se aplica `docs/POLITICA_WRITEBACK.md` sin cambios: `dialog` recibe los dos
turnos -el prompt ORIGINAL de la tarea y la respuesta COMBINADA final-, y la
extraccion episodica corre sobre ese mismo par.

NO se persisten las subtareas ni sus respuestas parciales. Son maquinaria de
orquestacion, no conversacion.

### 7. Piel CLI: minima y declarada interina

`task run` y `reasoning run` con las mismas banderas de enriquecimiento que
`prompt run`. Superficie escrita a mano y marcada INTERINA en el docstring: la
rebanada siguiente la deriva del catalogo fusionado (`ADR 0011`, puntos 9-11),
y entonces se retira.

`--domain` en `task run` NO viaja al core como dominio de tarea: el core no lo
acepta y no lo aceptara (`core ADR 0043`). Queda solo como faceta de lectura de
la memoria. Documentarlo en la ayuda del subcomando.

### 8. Documentos que se corrigen (y solo estos)

- `docs/PLAN.md`: la premisa de la fase 7a "POST /task/run es SSE SIEMPRE, de modo
  que sobreescribirlo (7b) obliga a hablar streaming" es FALSA desde v0.4.
  Corregir la frase y el estado de la fase 7b. En la fase 5, la linea que dice que
  `task.plan` "NO esta entregado aun" tambien caduco.
- `docs/EXTENDED_CONTRACT.md`: los costes declarados del punto 5, y que
  `task.stream` se reenvia SIN enriquecer (hueco conocido: el core no acepta plan
  suministrado por `task.stream`).
- `CHANGELOG.md` bajo `[No publicado]`.

No se abren ADR nuevos en esta fase.

## Fuera de fase 7b (NO implementar)

- `capability.list` sobreescrita y el catalogo propio fusionado. Es la rebanada
  siguiente, y la superficie CLI de esta fase se apoya en ella cuando llegue.
- `task.stream` sobreescrito. El core no acepta `plan` ni `requirements` por esa
  capacidad en ninguna interfaz, asi que no es implementable aqui. Se reenvia
  crudo y se declara. El CR al core se emite cuando `ia_nest_web` lo pida, no
  antes (`core ADR 0035`: una costura sin consumidor real se pudre).
- `prompt.stream` sobreescrito. Sigue reenviado, como en la fase 7a.
- Mover `docs/DEPENDENCIAS.md` a `>=0.4`. Espera al tag del core.
- REST y MCP (fase 7c). Cortar tag (fase 7d).
- Tocar el core, el esquema de memoria, la politica de write-back, el ranking o
  la consolidacion.
- Las deudas D1, D2 y D3 del PLAN. La medida de esta fase alimenta D1, pero no la
  cierra.

## Criterios de aceptacion (falsables)

1. **Copia fiel.** Contra un stub que devuelva en `task.plan` un campo hermano
   desconocido, ese campo llega intacto a `task.run`. Prueba automatizada.
2. **`params` no vuelve.** La peticion a `task.run` no contiene `params`.
3. **Solo se edita `prompt`.** Para cada subtarea, `index`, `domain` y
   `depends_on` de la peticion son identicos a los de la respuesta de `task.plan`.
4. **RAG por dominio de subtarea.** Con dos subtareas de dominios distintos, cada
   una recibe contexto de SU dominio y no del otro. Prueba automatizada con stub.
5. **Tope por subtarea.** Ninguna subtarea sale con mas de `rag_max_tokens`
   inyectados, medido con la misma estimacion que ya usa la capa
   (`estimate_tokens`).
6. **Medida contra control, no narracion.** Un script reproducible en
   `local/lab/` que ejecute la misma tarea en tres brazos -sin plan, plan en eco,
   plan enriquecido- con 3 repeticiones, y emita la tabla de `stop_reason`,
   `requirements_covered`, `degradations`, gasto y longitud de respuesta. El
   criterio NO es "pasa el gate": es que el brazo enriquecido no degrade la
   longitud de respuesta frente al control. El gate del core da verde sobre
   respuestas de 112 caracteres, asi que no sirve solo.
7. **Passthrough.** `task run --no-enrich` no llama a `task.plan`, envia la
   peticion sin `plan` y conserva la capacidad de re-planificar del core.
8. **Write-back.** Una tarea escribe DOS engramas `dialog` -prompt original y
   respuesta combinada- y ninguno por subtarea.
9. **`reasoning.run` transparente.** Devuelve la misma forma que la del core, con
   el payload ajeno intacto.
10. **Telemetria.** El evento propio de `task.run` lleva `request_id` propio y el
    `downstream_request_id` del core, y cuenta subtareas enriquecidas.
11. **Perezoso.** `memory maintain` sigue ejecutandose con el core inalcanzable.
12. Las pruebas existentes siguen en verde, con los skips esperados de PostgreSQL.

## Entrega

Deja el trabajo STAGED sobre `main`, con `git add` por ruta explicita de los
ficheros de tu alcance. **No crees rama, no commitees, no hagas push.** La rama y
el commit los hace el revisor tras verificar; tu sandbox tampoco puede escribir
en `.git/refs`.

Incluye en lo staged `docs/handoff/fase_7b_entrega.md` con: que se implemento,
decisiones que hubo que tomar y por que, criterios cubiertos uno a uno, lo que
quedo fuera, e inconsistencias detectadas SIN corregirlas por inferencia (se
senalan).

No cortes tags. No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia: eso
introduce diseno no reconciliado, y esta capa se construye en modo ciego.
