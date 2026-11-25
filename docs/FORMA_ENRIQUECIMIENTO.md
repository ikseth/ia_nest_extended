# Forma del enriquecimiento (Fase 1)

Estado: borrador endurecible (NO congelado)
Version: 0.1 - 2026-07-18

Este documento fija la FORMA en que esta capa envuelve al core, no un contrato
congelado. El vertical de la Fase 3 la endurece; el contrato publico SemVer se
corta en la Fase 7. Motivo: core ADR 0035, una costura sin consumidor real se
pudre; se congela cuando un consumidor la haya ejercido.

## El flujo

    1. recuperar   memoria / RAG / web, segun la identidad del request
    2. enriquecer  componer el contexto recuperado, dentro del presupuesto
    3. ejecutar    prompt.run / task.run del core (core no conoce esta capa)
    4. write-back  persistir lo que corresponda de la respuesta (con politica)

Cuando la capacidad del core declara `turn_context`, recibe la frase como
`prompt` y el contexto en bloques por origen dentro de `turn_context.context`.
Si no declara la parte, recibe el prompt enriquecido anterior, delimitado por
`<enrichment_context>`. La decision es por capacidad y conserva la regla 3 de
meta ADR 0007. La identidad de segmentacion del core es la clave con la que
esta capa indexa (via 2, core ADR 0031/0035). Ver ADR 0018.

## Arquitectura de la capa (via 2, servicio + pieles finas)

Extended ENVUELVE al core; el core NO llama a extended ni sabe que existe. El
"enganche" es al reves: el servicio de extended llama a la REST del core
(`prompt.run`, `domain.route`) - la unica costura de RED, porque el core es otro
desplegable. Para core puro, el cliente llama al core directamente (o al servicio
con `enrich=False`, passthrough).

Dentro de la capa: la logica vive en UN servicio (`MemoryEnricher`); CLI, REST y
MCP son pieles finas que lo invocan, sin logica divergente (misma disciplina que
el core, `CORE_CONTRACT`). Ni el CLI llama a la API ni al reves: ambos llaman al
servicio en proceso. El comportamiento se controla por parametros del servicio
(ver "superficie de parametros", `docs/PLAN.md` Fase 7).

Hacia AFUERA, la capa no expone un catalogo propio y menor: expone el contrato
uniforme (ADR 0011, aplicando meta ADR 0007). Reenvia sin alterar lo que no
enriquece, sobreescribe conservando la forma, y anade lo suyo. Este documento
describe COMO se enriquece; QUE se expone esta en `docs/EXTENDED_CONTRACT.md`.

## Decision 1: mapeo identidad -> clave de memoria

Campos de identidad del core: `user_id`, `service`, `session_id`, `domain_tag`,
`namespace` e `interlocutor_profile`. Extended recibe ademas `audience` y
`frame_facts`. Su papel en esta capa:

| Campo | Papel |
|---|---|
| `user_id` | columna vertebral de la clave de los tipos experienciales; los delegados de scope global o de entidad no lo llevan (ver roster) |
| `namespace` | parte de la clave (salvo `dialog`, turnos crudos sin namespace); una unica derivacion para lectura y escritura (Leccion 3) |
| `session_id` | entra en la clave SOLO para tipos con scope de sesion (decision por tipo, Fase 2) |
| `service` | PROCEDENCIA (metadato), no clave: segmentar por service fragmentaria la continuidad de la entidad, que el core advierte evitar |
| `domain_tag` | FACETA de lectura (recuperar lo coherente con el dominio), no clave dura |
| `interlocutor_profile` | nivel de permiso y procedencia; nunca clave; `child` se normaliza a `restricted` |
| `audience` | tono para el bloque permanente `interlocutor`; nunca concede ni entra en la clave |
| `frame_facts` | hechos del borde para el marco versionado de la sesion; no son memoria ni clave |

Existe una identidad local configurada por defecto (core `CORE_CONTRACT.md`): en
uso local no hay que pasar identidad a mano ni se fragmenta la continuidad.

Regla de uso de `user_id`: identifica al INTERLOCUTOR, no a la instancia del ente
-la base entera es la memoria de esta instancia; no hace falta escribirlo en cada
fila-. De ahi que **cada agente que lance prompts contra la instancia use su
PROPIO `user_id`**, tambien cuando lo haga para verificar o probar. Reusar el del
operador mezcla el trafico de prueba con su memoria real, y entonces la
segmentacion deja de existir: el ente empieza a "recordar" de su operador cosas
que dijo un agente en una bateria de pruebas.

`user_id` SEGMENTA, no AUTORIZA: la autoridad la dan el principal (ADR 0002) y el
GRANT del motor (ADR 0010). Nadie autentica esa afirmacion hoy; cuando haga falta,
el concern esta registrado en `ia_nest_meta/docs/CAPAS_FUTURAS.md`.

El bloque `interlocutor` se compone por `audience`: `child` usa el contexto
infantil, `general` el contexto apto para cualquier persona de la casa y
`adult` no anade bloque. Se aplica con o sin las fuentes de enriquecimiento y
queda fuera de write-back. El marco de `frame_facts` vive en `session_frames`,
se resuelve contra `entities` y solo se proyecta al core dentro de
`turn_context.frame`; nunca se convierte en un engrama. Cuando la capacidad
declara `turn_context.context`, `interlocutor` viaja como bloque separado; en
el fallback se conserva la seccion inline anterior.

## Decision 2: composicion y presupuesto

Memoria (varios tipos), RAG y datos web compiten por un contexto FINITO (core
ADR 0008). Principios:

1. Recuperar no es volcar: se selecciona top-k RELEVANTE dentro del presupuesto.
   El ranking de relevancia de cada tipo vive en su declaracion (ADR 0002); la
   composicion agrega entre tipos y fuentes dentro del presupuesto total.
2. Anti-colision de dominios: dominios incompatibles no se enriquecen entre si
   por defecto (leccion de la cantera `ia_nest`: `chat.salud` no alimenta
   `linux.ops`). Se apoya en `domain_tag` como faceta.
3. Precedencia y reparto del presupuesto entre fuentes: principio fijado, cifras
   y orden concretos se reconcilian al existir cada fuente (Fase 3 memoria,
   Fase 5 RAG, Fase 6 web). Los numeros de arranque de la memoria estan en
   `docs/POLITICA_WRITEBACK.md` (composicion del recall).

Los mismos limites y el mismo recorte gobiernan los dos caminos. El coste fijo
de `<enrichment_context>` cuenta solo en el fallback inline; el interlocutor
sigue fuera del presupuesto. Los bloques aparte se agrupan por origen en este
orden: `interlocutor`, `memory`, `rag`, `thread` (ADR 0018).

## Que puede y que no puede el enriquecimiento

Frontera observada al ejercer la capa contra modelos reales (2026-08-19), y que
conviene tener presente antes de esperar de un corpus lo que un corpus no da:

**El enriquecimiento cubre huecos de CONOCIMIENTO, no de COMPOSICION.**

- Si al modelo le falta un dato -una sintaxis, una cifra, un procedimiento-, el
  corpus se lo pone delante y lo aplica. Medido: un modelo que inventaba la
  sintaxis de una herramienta la escribio correcta en cuanto el corpus la
  contenia.
- Si al modelo le falta capacidad para ESTRUCTURAR una respuesta -encadenar
  pasos, ensamblar piezas que dependen unas de otras, sostener un razonamiento-,
  el corpus no lo suple. Medido: con el mismo corpus delante, un modelo pequeno
  copio fragmentos correctos y los ensamblo mal.

Consecuencia para el reparto de modelos del ente: un experto pequeno con corpus
alcanza a uno grande donde el cuello de botella es el conocimiento, y no lo
alcanza donde el cuello de botella es el razonamiento. No es una limitacion de
esta capa: es lo que un contexto anadido puede hacer.

Consecuencia para esta capa: cuando una respuesta salga mal, la primera pregunta
es cual de los dos huecos era. Ampliar el corpus no arregla el segundo, y cambiar
de modelo no arregla el primero.

## Que NO se fija aqui (endurecimiento posterior)

- Los nombres de las capacidades (`memory.recall`, `memory.write_back`, ...) son
  provisionales; se fijan en la Fase 7.
- El reparto numerico del presupuesto y el orden de fuentes: Fases 3/5/6.
- El roster de tipos de memoria y el modelo de relevancia concreto: Fase 2.

## Criterio de salida

Forma escrita y reconciliada, con las dos decisiones duras fijadas y el resto
marcado explicitamente como no congelado.
