# Handoff de retrabajo: fase 7b (tres defectos hallados en laboratorio)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-18
Base: rama `fase-7b-task-run-por-subtarea`, commit `5f58430`.

La fase 7b esta implementada y sus doce criterios cubiertos. Este retrabajo
corrige tres defectos que solo apareceron al ejercerla contra modelos reales en
laboratorio. NO reabre el diseno: el brief que manda sigue siendo
`docs/handoff/fase_7b_brief.md`.

## 1. Bloqueante: `task.run` expira con la configuracion de fabrica

`connect_timeout_seconds` e `inactivity_timeout_seconds` valen 30 y se aplican
por igual a todas las capacidades. Ese modelo se fijo en la fase 7a, cuando
`POST /task/run` era SSE y la "inactividad" medida era el HUECO ENTRE EVENTOS.

Desde la linea v0.4 del core, `task.run` es una llamada JSON BLOQUEANTE: no
emite nada hasta terminar, y la orquestacion tarda entre 30 y 90 segundos, con
picos observados de ~150 s. La consecuencia, medida en pitufo el 2026-08-18:

    CoreConnectionError: no se pudo conectar con http://127.0.0.1:8000/task/run:
    timed out

Es decir, con valores por defecto la capacidad principal de la fase NO FUNCIONA.
Ninguna prueba con stub lo detecta, porque un stub responde al instante.

**Que se pide.** Que las capacidades que ORQUESTAN -`task.plan` y `task.run`-
usen un plazo propio, mas largo, en vez del de inactividad general. Clave de
configuracion nueva, aditiva, con el prefijo y el estilo de las existentes
(`config.py`), y un valor por defecto que cubra una orquestacion real con margen;
600 segundos es razonable y queda acotado.

La distincion de fondo, para que no se resuelva subiendo el timeout global:

    respuesta en flujo (SSE)   -> guarda la INACTIVIDAD entre eventos
    respuesta bloqueante lenta -> guarda el PLAZO de la operacion entera

Subir el valor global haria que un `prompt.run` colgado esperase diez minutos.
No lo hagas.

No rehagas el modelo de timeout entero: eso se revisa en la fase 7c, cuando REST
y MCP obliguen a mirarlo de nuevo. Aqui basta con que las dos capacidades lentas
dejen de usar el plazo equivocado.

## 2. Menor: la traza del RAG por subtarea no dice de que corpus

En el camino de `prompt.run`, el evento `rag.retrieve` rellena
`details.domain` y `details.corpora`. En el camino de tarea no: se ve
`k_returned` pero no de que dominio ni de que corpus salio el chunk.

Comprobado en la telemetria de pitufo: cuatro eventos `rag.retrieve` con
`domain=None` y `corpora=None`.

Eso deja sin traza precisamente lo que la fase 7b promete -que cada subtarea
recibe el conocimiento de SU dominio-, y obliga a deducirlo del numero de
subtareas enriquecidas. Igualar la traza de los dos caminos.

## 3. Menor: el script de verificacion no viaja al despliegue

`local/lab/fase_7b_tres_brazos.py` esta en un directorio ignorado por git, asi
que no llega a la maquina donde debe ejecutarse: hubo que copiarlo a mano. Un
script de verificacion que depende de que alguien se acuerde de copiarlo no
verifica nada de forma fiable.

**Que se pide.** Moverlo a una ruta VERSIONADA, `tools/lab/`, y anadir un
`tools/README.md` de una linea diciendo que hay ahi. No contiene secretos: recibe
`--env-file` y lee la configuracion, que es donde viven las direcciones.

`local/` se reserva para lo que de verdad es contexto de maquina -direcciones,
credenciales y datos crudos de una pasada-.

Actualiza en `docs/handoff/fase_7b_entrega.md` la referencia a su nueva ruta.

## Fuera de este retrabajo

- Rehacer el modelo de timeout completo (fase 7c).
- Tocar el diseno de la fase 7b: colocacion de fuentes, presupuesto por subtarea,
  costes declarados o write-back. Estan reconciliados y medidos.
- Mover `docs/DEPENDENCIAS.md`, cortar tag, REST/MCP, catalogo fusionado.
- Tocar el core o el laboratorio.

## Criterios de aceptacion (falsables)

1. Una llamada a `task.run` cuyo backend tarda mas que el timeout de inactividad
   general, y menos que el plazo nuevo, COMPLETA. Prueba automatizada con un
   stub lento; no vale un stub instantaneo.
2. Un `prompt.run` contra un backend que no responde sigue fallando con el
   timeout corto, no con el largo. Es la prueba de que no se subio el global.
3. La clave nueva aparece en el esquema de configuracion con el resto, se puede
   fijar por entorno y su ausencia toma el default.
4. Un evento `rag.retrieve` emitido desde el camino de tarea lleva `domain` y
   `corpora` rellenos, igual que el de `prompt.run`.
5. El script vive en `tools/lab/`, `local/lab/` ya no lo contiene, y
   `docs/handoff/fase_7b_entrega.md` apunta a la ruta nueva.
6. La suite sigue en verde (81 passed, 26 skipped sin DSN de PostgreSQL) mas las
   pruebas nuevas.

## Entrega

Deja el trabajo STAGED sobre la rama `fase-7b-task-run-por-subtarea`, con
`git add` por ruta explicita. **No crees rama, no commitees, no hagas push.**

Anade a `CHANGELOG.md` bajo `[No publicado]` lo corregido, y a
`docs/handoff/fase_7b_entrega.md` una seccion con los tres defectos y su
correccion.

No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
