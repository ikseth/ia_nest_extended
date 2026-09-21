# Politica de write-back (Fase 3)

Estado: reconciliado
Version: 0.3 - 2026-09-12

Entregable de la Fase 3 del PLAN: que se persiste tras cada respuesta del core,
donde, y con que filtros. Principio rector: persistir en bruto envenena la
memoria; el crudo solo vive donde el diseno lo declara crudo.

## Por tier

| Tier | Que se escribe | Regla |
|---|---|---|
| `dialog` | los dos turnos (prompt del usuario y respuesta), tal cual | siempre; es crudo POR DISENO (scope sesion, H=4h) |
| `episodic` | items destilados, no crudo | extraccion estructurada (abajo); solo `confidence >= 0.7` |
| `semantic` | nada | solo consolidacion (fase 4) |
| delegadas | nada | autoridad de escritura de conscience (ADR 0002) |

## Procedencia: `stated_by` (ADR 0013)

Todo engrama registra QUIEN dijo lo que guarda, en su campo `stated_by`:
`user`, `model` o `unknown`. El nombre NO es `provenance` a proposito: ese
identificador ya designa otra cosa en el contrato de esta capa (el origen de una
entrada del catalogo: `own`, `overridden`, `forwarded`).
No es cosmetica de traza; es lo que materializa la frontera de confianza de la
enmienda del ADR 0007 -el write-back produce candidatos, no verdades- y lo que
permite que una correccion del interlocutor ANOTE lo que el modelo afirmo. No lo
retira: la decision 4 del ADR 0013 lo dice expresamente, y el margen medido entre
contradecir y compartir tema no sostiene una accion destructiva.

- En `dialog` es directa: el prompt es del usuario, la respuesta del modelo.
- En `episodic` la fija el CODIGO segun la lista en que vino el item, nunca el
  modelo. Sin anclaje lexico con el bloque atribuido, el item cae a `unknown`.
- `unknown` no se rellena por conveniencia (mismo criterio que `source_trace_id`
  en CR-0005).
- La procedencia viaja al contexto inyectado: `(fuente: usuario)`,
  `(fuente: modelo, sin verificar)`, `(fuente: no registrada)`.

## Convergencia de la capacidad de origen

`task.run` publica `stop_reason` en su respuesta. Un valor distinto de
`task_done` dice que la tarea se corto SIN que el evaluador del core aceptara el
resultado -por agotar iteraciones o por no poder replanificar-, y entonces lo
que salio de esa respuesta NO alimenta `episodic`. Lo que dijo el interlocutor
si: su turno no depende de que la tarea convergiera. `dialog` se escribe entero,
como siempre, porque es crudo por diseno.

Esto NO necesito pedirselo al core: el dato ya viajaba en la respuesta y esta
capa no lo leia. Se contabiliza en `items_unconverged`. Las capacidades que no
declaran `stop_reason` (`prompt.run`) no aportan informacion en contra y pasan.

## Extraccion estructurada

Segunda llamada a `prompt.run` (modelo de extraccion, ADR 0006) con salida JSON:
dos listas, `from_user` y `from_assistant`, de items
`{namespace: facts|preferences|tasks, content, confidence, mentions[]}`.

- Anclaje literal: el prompt de extraccion exige items fundados en lo dicho,
  no interpretaciones del modelo (mitigacion de sesgo, ADR 0006).
- Anti-ruido: smalltalk produce cero items; salida JSON invalida se descarta y
  se registra en telemetria (no se escribe nada).
- Formato antiguo: una sola lista `items` se sigue aceptando, y sus items
  quedan en `unknown`.
- Cada item escrito conserva `source_trace_id` (el request del core que lo
  origino): auditable.

## Dedup con refuerzo, y anotacion de contradiccion

Tres bandas de similitud, con DOS alcances distintos y conviene no confundirlos:

- **Dedup y refuerzo** comparan contra los engramas del mismo
  `type_name`+`user_id`+`namespace`, como desde el principio.
- **La anotacion de contradiccion** compara contra el mismo
  `type_name`+`user_id`, SIN filtrar por `namespace`: una contradiccion es sobre
  el contenido, no sobre el cajon que eligio el extractor (ADR 0013, enmienda
  del 2026-09-12).

La asimetria es deliberada por ahora y esta sin decidir del todo: el mismo
argumento -la redundancia tambien es sobre el contenido- valdria para el dedup,
pero ahi la accion MUTA el engrama existente (refuerzo, orden en el ranking),
mientras que anotar no. Ampliar el alcance de una accion que muta pide su propia
medida, y no se hace de paso.

| Banda | Que significa | Que se hace |
|---|---|---|
| `>= dedup_threshold` (0.92) | es el MISMO item | se REFUERZA el existente (`stability + 1`, `last_reinforced_at`) |
| `[conflict_threshold, dedup_threshold)` (0.70-0.92) | habla de lo mismo | si el nuevo es del `user` y el viejo del `model`, el viejo recibe un enlace `contradicted_by` |
| `< conflict_threshold` | habla de otro asunto | nada |

La senal E del ranking (ADR 0003) se alimenta del refuerzo.

La anotacion **no cambia el estado** del engrama: sigue activo y recuperable.
Lo que cambia es el recall, que al verlo anotado (a) lo etiqueta -"hay una
version del usuario sobre esto"- y (b) lo despriorza al recortar por
presupuesto, de modo que cae antes que sus hermanos no anotados.

Por que anotar y no retirar: la separacion medida entre "contradice" y "comparte
tema" es de centesimas con el embedder del lab
(`local/lab/2026-08-22_banda_de_conflicto.md`), y ese margen no sostiene una
accion destructiva. Con el coste de error asi repartido, el umbral puede ser
permisivo. Por lo mismo la etiqueta dice solo lo que el mecanismo sabe y nunca
"esto es falso": marcar de mas es barato, mentir al modelo no.

Lo que la banda del medio NO hace: decidir que es verdad. Senala que hay dos
versiones y quien dijo cada una; el veredicto es de quien lee el contexto. Eso
la mantiene en mecanismo y fuera del juicio (test de frontera del ADR 0007).

## Menciones de entidades

Las menciones extraidas van a `unresolved_mentions` del engrama. Solo se
etiqueta `entity_refs` con matches inequivocos contra el registro de entidades
(hoy vacio); resolver ambiguedades es juicio del dueno (ADR 0004).

## Sintesis de hilo (Fase 9)

Con `thread_synthesis_enabled` -apagado por defecto-, al terminar el write-back
de un turno se cuenta cuantos turnos lleva el hilo desde la ultima sintesis. Al
cumplirse `thread_synthesis_window_turns` (4 de arranque), se genera un
`thread_summary` de esa ventana con `synthesis_model`, y sustituye al anterior
de ese hilo.

Tres reglas que no son detalles:

- **Anclaje**: la sintesis enlaza con `summarizes` a CADA engrama de su ventana.
  Un resumen sin enlaces es un resumen sin origen direccionable, y no vale.
- **Procedencia**: si la ventana mezcla emisores, la sintesis queda `unknown`.
  Una sintesis que mezcla emisores no puede presentarse como dicha por ninguno.
- **Sustitucion en el presupuesto, no en el almacen**: el recall compone la
  sintesis EN LUGAR DE los engramas que resume, y esos engramas siguen ahi,
  recuperables por consulta directa.

Por que existe: un conjunto de engramas atomicos no puede expresar que uno
reemplaza a otro, solo coexistir. Lo que da direccion a un hilo es una frase con
estructura temporal.

## Retencion

Sin borrado fisico (ADR 0002). La salida de ventana caliente de `dialog` y la
promocion episodica -> semantica son de la fase 4 (consolidacion); esta politica
no archiva nada por si misma.

## Composicion del recall (numeros de arranque, configurables)

Presupuesto ~1500 tokens; k = 6 `dialog` / 4 `episodic` / 3 `semantic`; orden:
delegadas siempre-inyectadas -> `semantic` -> `episodic` -> `dialog` pegado al
prompt; recorte del peor-rankeado primero. Afinado en laboratorio (decision del
usuario en reconciliacion: el lab es el banco de finetuning de estos numeros).
