# Cierre operativo de core + extended: que funciona y que falta

Fecha: 2026-08-18
Autor: Claude (Opus), rol disenador. Reconciliacion del usuario pendiente.

Instantanea del estado tras cerrar la fase 7b y las deudas D1 y D2. Su proposito
es UNO: que se pueda decidir lineas nuevas de desarrollo sin volver a auditar la
pila. No es un plan ni una promesa.

Es una instantanea con fecha, no un documento vivo. Cuando caduque, se escribe
otra; no se parchea esta.

**Que ha cambiado desde que se escribio** (no se parchea el resto; esta es la
unica nota): `capability.list` ya NO es un bug -se sobreescribio y compone, ADR
0012-. Y aparecieron tres carencias que no estaban: la memoria sin suelo de
relevancia, el solape entre ruido y acierto al calibrar, y que esta capa no tiene
instalador de despliegue. Las tres viven ya en `docs/PLAN.md` (fase 8, deudas D4 y
D5), que es donde se sigue el trabajo pendiente.

Cada carencia esta clasificada en uno de tres cajones, y esa clasificacion es lo
que se pide reconciliar:

    FUTURO    falta por diseno, no por fallo. Nadie lo implemento aun
    BUG       esta mal y hay que arreglarlo
    OTRA CAPA no es de extended y no debe resolverse aqui

## 1. Lo que funciona hoy

Verificado en laboratorio contra modelos reales, no deducido:

| Capacidad | Estado |
|---|---|
| `prompt.run` enriquecido | memoria + RAG, con presupuesto y suelo de relevancia |
| `reasoning.run` enriquecido | mismo vertical upfront |
| `task.run` enriquecido por subtarea | `task.plan` -> RAG por dominio de cada subtarea -> `task.run(plan)` |
| Reenvio generico | cualquier capacidad del core es alcanzable sin tocar esta capa |
| Passthrough | enriquecimiento desactivado no recupera, no inyecta y no persiste |
| Memoria | continuidad por identidad, write-back con politica, consolidacion mecanica |
| Conocimiento por dominio | ingesta, vinculos propuestos y confirmados, gate por dominio |
| Telemetria propia | con encadenado de `request_id` entre capas |

Suite: 120 pruebas en verde con PostgreSQL real, incluidas las que normalmente se
omiten sin base de datos.

**La frontera honesta de "operativo": operativo por CLI, en laboratorio, con un
solo consumidor, que somos nosotros.** Nada de esto se ha ejercido desde otra
capa, porque todavia no hay otra capa. La leccion del `core ADR 0035` -una costura
sin consumidor real se pudre- nos aplica a nosotros: la primera vez que
`conscience` escriba una memoria delegada apareceran cosas. Eso no sera una
regresion.

## 2. Carencias de extended

### FUTURO: REST y MCP (fase 7c)

La carencia mas grande, con diferencia. Hoy la unica piel es la CLI.

Consecuencia: **los dos consumidores declarados de esta capa no pueden
consumirla.** `conscience` necesita escribir memorias delegadas y emitir eventos
de consolidacion; `ia_nest_web` necesita presentar memoria y conocimiento. Las
capacidades EXISTEN en el servicio; lo que falta es la puerta.

Se arrastra con ella un detalle menor: `memory.write`, `memory.consolidate` y
`memory_type.validate` tampoco tienen subcomando de CLI. Se dejo fuera de la fase
7a a proposito, y se resuelve solo cuando esten las tres pieles.

### BUG: `capability.list` se reenvia, y por tanto miente

Verificado: pedir el catalogo a traves de esta capa devuelve dieciseis
capacidades, **ninguna de ellas propia**. Un cliente que descubra por catalogo
concluye que `memory.recall` y `knowledge.ingest` no existen.

Incumple la regla 3 de `meta ADR 0007` (extension aditiva: subir de capa siempre
suma) por la via mas tonta, que es reenviar correctamente.

Es pequeno y acotado, y no se arregla solo: exige que esta capa declare su propio
catalogo y lo FUSIONE con el de abajo, que es el mecanismo del `ADR 0011`, puntos
9 a 11. De ese catalogo fusionado salen despues las tres pieles, asi que es
prerequisito de 7c y conviene hacerlo antes.

Generaliza a una clase que conviene nombrar: las capacidades REFLEXIVAS, las que
describen la pila y no el mundo. `capability.list` es la unica que miente hoy;
`runtime.health` y `config.validate` responden solo por el core, lo que es
defendible mientras el contrato lo declare, y deja de serlo cuando haya que
responder por la pila entera.

### FUTURO: fase 6, datos web

Declarada en el PLAN, nunca empezada. La tercera fuente de enriquecimiento -junto
a memoria y conocimiento- no existe. No bloquea nada.

### FUTURO: D3, la identidad como fuente conmutable

La personalidad del ente deberia ser una fuente desactivable por nombre, como
`memory` y `rag`, para poder medir si mejora o empeora una respuesta. Su
disparador declarado es que `conscience` escriba en los tipos delegados, y aun no
hay nada que conmutar.

### FUTURO: `knowledge.retrieve` y `knowledge.corpus.list`

Nombres reservados en el contrato, sin implementacion. Es deliberado: existen para
el consumo de `ia_nest_web` y no se construyen hasta que ese consumidor las
ejerza. No es deuda; es la politica del `ADR 0035` aplicada bien.

### FUTURO: sintesis con compresion multi-item en la consolidacion

Diferida con nombre en el `ADR 0007`. Hoy la promocion es LITERAL.

### FUTURO: primer tag de la capa (fase 7d)

Requisitos: `EXTENDED_CONTRACT.md` en estado activo y el contrato ejercido por un
consumidor real. Bloqueado ademas por algo ajeno, ver mas abajo.

## 3. Carencias del core, ya reportadas

Las seis salieron del ejercicio de la fase 7b y estan entregadas en el repo de
gobernanza (`docs/handoff/avisos_al_core_desde_extended_2026-08-18.md`); la unica
que cambia contrato va como `extended CR-0003`.

| Hallazgo | Cajon |
|---|---|
| Al gate de su fase B3 le falta mirar como termino la tarea | BUG de verificacion, no de producto |
| Una respuesta vaciada por exceso de contexto pasa el gate en verde | FUTURO: no sabe declarar esa degradacion |
| El smoke por REST de su linea v0.4 conviene rehacerlo | BUG de metodo |
| Su CLI ignora la variable de configuracion que su REST respeta | BUG |
| Un endpoint sin resolver se reporta como modelo no disponible | BUG de diagnostico |
| `task.stream` no acepta plan por ninguna interfaz, y su funcion si | BUG (parametros muertos) |

Ninguna bloquea a extended. La cuarta y la quinta son las que cuestan tiempo a
quien opere la pila a mano.

## 4. OTRA CAPA: lo que no debe resolverse aqui

| Asunto | De quien |
|---|---|
| Juicio de que merece consolidarse; identidad, principios y entidades | `conscience`. Los tipos delegados estan declarados y VACIOS |
| Presentacion de memoria y conocimiento | `ia_nest_web` |
| Regulacion tecnica y observacion de la telemetria de todos | `pulse` |
| Accion con efecto sobre sistemas externos | `tool_contracts` / `external_*` |
| Que el ente provisione su propio backend de modelos | Decision del core; aviso duradero abierto en gobernanza |
| Autenticar la identidad del request | Nadie hoy. `user_id` SEGMENTA, no AUTORIZA; registrado en `CAPAS_FUTURAS.md` |

## 5. Riesgos que no son carencias, y conviene no olvidar

1. **El corpus del laboratorio es de juguete**: dos dominios con un fragmento cada
   uno. Decir "RAG operativo" con propiedad exige crecerlo, y eso es CONTENIDO, no
   codigo. Al crecerlo hay que **recalibrar el suelo de relevancia**: se midio con
   un corpus pequeno y el margen entre la banda de ruido y la de acierto era
   estrecho. Ya se comprobo que ese umbral escala con la anchura del corpus.
2. **Sin tag en el core no hay tag aqui.** La linea v0.4 del core vive en su rama
   principal sin cortar, asi que `docs/DEPENDENCIAS.md` no puede declarar
   honestamente su rango, y sin eso no se corta el primer tag de esta capa. Es
   decision del usuario, no trabajo pendiente.
3. **El backend de modelos es ajeno y esta marcado para retirar.** No es una
   dependencia de una capa: es del ente entero. El dia que se retire, core y
   extended se quedan sin modelos a la vez.
4. **El gate del core no basta como senal de calidad.** Da verde sobre respuestas
   de cien caracteres. Cualquier verificacion futura de esta capa debe comparar
   contra un control, no mirar el gate.
5. **Actualizar el codigo de un despliegue no reinicia sus servicios.** Costo una
   tarde de medidas invalidas. Hasta que exista el identificador de build del
   `CR-0003`, comprobarlo a mano antes de medir por red.

## 6. Lectura de conjunto, para decidir lineas

Con lo anterior, hay tres lineas posibles y no compiten por lo mismo:

- **Consumible por otras capas**: catalogo fusionado -que arregla el bug de
  `capability.list`- y despues REST y MCP. Es lo unico que desbloquea a
  `conscience` y a `ia_nest_web`. Si la siguiente prioridad del ente es otra capa,
  esta linea es obligatoria y va primera.
- **Utilidad real del conocimiento**: crecer el corpus con conocimiento de verdad
  por dominio y recalibrar. No es codigo, y hace que lo que ya existe valga mas.
  Es la unica linea que mejora el producto sin escribir una funcion.
- **Cerrar el ciclo de version**: tag del core, rango de dependencias, contrato a
  activo y primer tag de esta capa. Es barata y quita ambiguedad a todo lo demas,
  pero no anade capacidad.

La recomendacion, si se busca avanzar el ENTE y no solo esta capa, es la primera:
hoy la capa de enriquecimiento funciona y nadie puede usarla salvo un operador con
una terminal.
