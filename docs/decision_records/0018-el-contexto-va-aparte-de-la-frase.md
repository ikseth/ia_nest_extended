# Decision 0018: el contexto va aparte de la frase

Fecha: 2026-11-25
Estado: aceptado por el usuario (2026-11-25), desde meta ADR 0020 (decidido el
2026-11-25; precisiones de meta H12P9, D1-D3, del mismo dia)

Depende de: meta ADR 0020 (el contexto va aparte de lo que dice la persona),
meta ADR 0007 (regla 3: sin el campo nuevo, como antes), core ADR 0056 (la parte
`context` de `turn_context`), ADR 0017 (marco; enmienda el punto 6),
`FORMA_ENRIQUECIMIENTO` (como envuelve la capa al core).

Meta `H12`, paso H12P9.

## Contexto

`compose_prompt` pega delante de la frase el contexto del turno dentro de
`<enrichment_context>`: el interlocutor, la memoria, el RAG y lo del hilo. Lo
hace en `prompt.run` y `prompt.stream` (con y sin enriquecimiento: sin el, solo
el interlocutor), en el plan de `task.run` (el interlocutor) y en cada subtarea
(el interlocutor o su RAG). Para enrutar, `domain.route` recibe el ultimo
intercambio pegado delante de la frase.

El core decide sobre esa mezcla lo que falta, el efecto y el dominio, y el
modelo lee el RAG como si lo dijera la persona (meta ADR 0020, contexto). El
core separa ahora la frase del contexto (core ADR 0056); a extended le toca
dejar de pegar.

## Decision

### 1. Cuando el core declara la parte, la frase va sola

Si el catalogo del core declara `turn_context` en la capacidad que se llama,
extended manda como `prompt` lo que dijo la persona y el contexto como bloques
en `turn_context.context` (core ADR 0056, D1). Si no lo declara, pega el
contexto como hoy (meta ADR 0007, regla 3). Se decide por capacidad, con la cache
del catalogo que ya decide `trusted_providers` y `frame`.

### 2. Manda aparte lo mismo que hoy pega, ni mas ni menos

No cambia que se recuerda, ni como se busca, ni que ve cada llamada. Cambia solo
por donde va. Cada nivel del recall va a un origen:

| Nivel del recall | Origen |
|---|---|
| interlocutor (tono, ADR 0017 punto 2) | `interlocutor` |
| `delegated`, `semantic` | `memory` |
| `thread_summary`, `dialog`, `thread_artifacts` | `thread` |
| `rag` | `rag` |

Un bloque por origen, con sus lineas compuestas como hoy y sin envoltorio. Un
origen sin lineas no se manda.

### 3. Por camino

- **`prompt.run` y `prompt.stream`.** Con enriquecimiento, los bloques de su
  recall. Sin el, solo el bloque `interlocutor`, si lo hay.
- **`domain.route`.** El `prompt` es la frase; el ultimo intercambio (las dos
  lineas de hoy) va como bloque `thread`. El core lo usa como pista y clasifica
  la frase (core ADR 0056, D3; meta H12P9, D2).
- **`task.run` y `task.plan`.**
  - La reescritura autonoma se mantiene (meta H12P9, D1): el `prompt` que va al
    core es la peticion reescrita con la memoria, que se entiende sola. Es una
    peticion, no contexto pegado, y es la practica habitual en RAG
    conversacional ("condense question"). La llamada de reescritura es interna
    de extended y sigue llevando la memoria en su texto, como las de extraccion
    y sintesis.
  - El bloque `interlocutor` va en `turn_context.context` de `task.plan` y de
    `task.run`, para el planificador y el combinador. La memoria no va: hoy solo
    alcanza la reescritura y asi sigue.
  - Cada subtarea lleva su `context` en el plan (core ADR 0056, D4): el
    `interlocutor` y, con RAG, su bloque `rag`, recuperado con la frase y el
    dominio de la subtarea como hoy. Su `prompt` queda tal como lo dio el
    planificador. `subtasks_enriched` cuenta las subtareas que llevan contexto.
- **`reasoning.*`.** Sin cambios: hoy no se manda contexto al core por ahi.

### 4. El presupuesto lo pone extended

Siguen `memory_budget_tokens` y el presupuesto del RAG (`rag_max_tokens`), con
los valores de hoy como primera configuracion; se ajustan segun la medida, en la
configuracion del laboratorio (meta ADR 0020, punto 7). Sin envoltorio, el
envoltorio deja de contar en el presupuesto. El interlocutor sigue fuera del
presupuesto, como hoy.

### 5. Telemetria

Los eventos de los turnos conversacionales y de `task.run` ganan
`context_sent`: `aside` (bloques en `turn_context`), `inline` (pegado, core sin
la parte) o `none`, y los caracteres por origen. Sin texto: el texto sigue la
regla que ya sigue el prompt.

### 6. `entity.unresolved` lista tambien la entidad sin casa (enmienda a ADR 0017, punto 6)

Hoy lista solo claves sin entidad. Una persona sembrada a la que le falta la
casa deja el lugar `unknown` y no aparece: el operador no sabe que sembrar.

- Cada fila gana `reason`: `no_entity` (lo de hoy) o `no_home`.
- `no_home`: la clave resuelve a una `person` o un `device` sin `home`, y el
  lugar del marco queda `unknown` (si la casa sale por la otra parte, no falta
  nada y no se lista).
- Igual que hoy: primera y ultima vez vista y cuantas veces. Solo lectura, CLI,
  principal `operator`.

El dispositivo entra por la misma causa: un satelite sembrado sin casa tampoco
da el lugar (meta H12P8, pendiente).

## Orden de despliegue

Despues del core (`v0.8.0`), que declara la parte. Con un core anterior, extended
sigue pegando el contexto en cada capacidad que no la declare.

## Consecuencias

- Contrato: ninguna forma de peticion ni de respuesta de extended cambia. Cambia
  lo que manda al core, solo cuando el core lo declara, la telemetria y
  `entity.unresolved` (campo nuevo). MINOR en la serie pre-1.0.
- `FORMA_ENRIQUECIMIENTO` y `EXTENDED_CONTRACT` (reescritura de `task.run`)
  apuntan a este ADR. Al ADR 0017 se le apendiza un puntero por la enmienda del
  punto 6.

## Criterio falsable

1. Con un core que declara la parte, el `prompt` de `prompt.run`,
   `prompt.stream` y `domain.route` es la frase tal cual, sin
   `<enrichment_context>` ni "CONVERSACION RECIENTE".
2. Con un core que no la declara, lo que se manda es identico a `v0.8.2`.
3. Los bloques llevan el mismo texto que hoy iba pegado, repartido por origen
   segun la tabla del punto 2; con el enriquecimiento apagado solo va
   `interlocutor`.
4. En `task.run`, ninguna subtarea lleva contexto pegado en su `prompt`; la
   memoria no aparece en `turn_context` del planificador.
5. Una persona sembrada sin `home`, sin dispositivo con casa, aparece en
   `entity.unresolved` con `reason: "no_home"`; con un dispositivo con casa, no.

## Lo que esta decision NO cubre

- Que se recuerda y como se busca (memoria, RAG, hilo).
- La auditoria transversal por niveles (decision aparte de meta).
- Quitar la reescritura de `task.run`: si el planificador resuelve las
  referencias con el contexto aparte, se mide aparte, mas adelante.
- La ampliacion de la lista cerrada de entities (meta, Deck #213).
