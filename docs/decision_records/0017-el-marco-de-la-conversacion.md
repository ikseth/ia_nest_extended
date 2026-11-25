# Decision 0017: el marco de la conversacion, segunda entrega del registro

Fecha: 2026-11-24
Estado: propuesta

Tanda B del hito `H12` de meta ("sabe con quien habla", meta H12P8). Dispone
`edge CR-0004` (transportar los hechos del saludo, componer y guardar el marco),
la parte de extended de meta ADR 0019 (nivel de permiso y tono, separados) y las
clases del marco que el ADR 0016 dejo anunciadas. Diseno en meta ADR 0017
(puntos 1, 4, 5, 7 y 8), meta H12P3 (D1, D3 y D6) y meta H12P5 (D2, D5 y D6).
Lo que se pide al core va en `extended CR-0006`, tramo B.

## Contexto

Extended no sabe con quien habla. La identidad trae `user_id`, `service` y
`interlocutor_profile`; el borde va a afirmar ademas cuenta, persona y
dispositivo con su origen (`frame_facts`) y el tono (`audience`), edge ADR 0004.
`MemoryIdentity` descarta lo que no conoce. La sesion (ADR 0015) no guarda
ningun marco: medido el 2026-11-21, 0 de 377 sesiones de Open WebUI y de Home
Assistant lo tienen (criterio 5 de `H12`). El registro de entidades (ADR 0016)
solo tiene la clase `provider`. Y el contexto `## interlocutor` sale del perfil
`child`, que trataba como nino a cualquiera que no se identificase.

## Decision

### 1. Identidad: nivel de permiso, tono y hechos del saludo

- `interlocutor_profile` es el nivel de permiso: `adult` o `restricted`. Se
  acepta `child` como nombre antiguo de `restricted` durante una version y se
  normaliza a `restricted` antes de cualquier llamada o escritura: hacia el core
  solo sale `restricted`.
- Campo nuevo `audience`: `child`, `adult` o `general`. Si falta (borde antiguo),
  se deduce del perfil tal como llego: `child` -> `child` (comportamiento de
  hoy), `restricted` -> `general`, `adult` -> `adult`.
- Campo nuevo `frame_facts`, con la forma de edge ADR 0004 (`account`, `person`,
  `device`, cada uno con `value` y `origin`). Se valida la forma; un valor mal
  formado es error de peticion. Si falta (borde antiguo), las partes van
  `unknown` con origen `absent`.
- Ni `audience` ni `frame_facts` son clave de memoria ni van al core como
  identidad: son procedencia, como `service` (`FORMA_ENRIQUECIMIENTO`,
  decision 1). `user_id` sigue siendo la clave.

### 2. Tono: el contexto del interlocutor sale de `audience`

| `audience` | Contexto que se compone |
|---|---|
| `child` | el de hoy (`interlocutor_context_child`) |
| `general` | nuevo `interlocutor_context_general`, configurable; por defecto: "No se sabe quien habla: puede ser cualquier persona de la casa, tambien un nino o una nina. Responde de forma apta para todos los publicos." |
| `adult` | ninguno |

Se compone en los mismos sitios que hoy (prompt, plan de tarea), con y sin
enriquecimiento. La telemetria de `interlocutor_context` dice `profile`,
`audience` y `composed`. El tono orienta y nunca concede.

### 3. Clases del marco en el registro

Por adicion a la lista del ADR 0016, con hechos curados (los siembra el
operador) y ninguno observado:

| Clase | Curado | Clave externa |
|---|---|---|
| `person` | `home` (clave de una `home`), `language` | `directory:<uid>` |
| `device` | `home`, `shared` (booleano), `language` | `account:<uid de la cuenta>` con el id que manda el consumidor; el usuario compartido, `directory:<uid>` |
| `home` | `locality` (texto), `timezone`, `provider` (clave de un `provider`) | `seed:<clave>` |

- `area` del dispositivo no entra ahora: cita un area del catalogo, que llega con
  el conector (meta `H13`). Es una adicion a la lista cuando llegue.
- Un hecho fuera de la lista (`role`, `groups`, edad) hace fallar la siembra:
  ningun hecho de entities concede (criterio 7 de `H12`).
- La siembra valida las citas: `home` apunta a una entidad `home` del mismo
  fichero o vigente; `provider` a un `provider` dentro del techo.
- El nombre de la entidad (`name`) es el que el operador siembra.

### 4. El marco de la sesion: `session_frames`

Tabla de solo anadir, colgada de la sesion (`user_id`, `session_id`) con clave
`(user_id, session_id, seq)`:

- `seq 0` es el marco de apertura, escrito en el primer turno conversacional
  (`prompt.*`, `reasoning.*`, `task.run`) que extended ve de esa sesion.
- Columnas `account`, `person`, `device` y `place` (jsonb, nunca nulas), `missing`
  (lista jsonb, nunca nula), `cause` (`open`, `edge` o `dialog`), `changed` (las
  partes que cambian respecto a la copia anterior) y fecha.
- Cada parte lleva `state` (`known`, `unresolved`, `stated` o `unknown`) y
  `origin` (`authenticated`, `validated`, `asserted`, `derived`, `dialog` o
  `absent`), y segun el estado:

  | Estado | Lleva ademas |
  |---|---|
  | `known` | `key` y, si es entidad, `entity_id` y `version` |
  | `unresolved` | `key` (clave sin entidad) |
  | `stated` | `value` (lo dicho) y `turn` (el `request_id` del turno) |
  | `unknown` | nada |

- **Cuenta.** `known` por autenticacion, con `key` `account:<uid>` y sin entidad
  (las cuentas no son entidades: las dice el directorio). Sin `frame_facts`,
  `unknown`.
- **Persona.** `directory:<uid>` resuelto contra el registro: `known` si hay
  `person`, `unresolved` si no hay entidad, `unknown` si el borde la declaro
  ausente. Si la clave resuelve a un `device` con `shared` (usuario compartido),
  la persona es `unknown` y ese `device` pasa a ser el dispositivo.
- **Dispositivo.** `account:<uid de la cuenta>` con el id afirmado, resuelto
  contra el registro (`known` o `unresolved`); ausente, `unknown`. Si llega a la
  vez una cabecera de dispositivo y el usuario compartido, gana la cabecera
  (meta H12P5 D5).
- **Lugar.** `derived`: la casa del dispositivo; si no, la casa de la persona; si
  no, `unknown`. Guarda por donde se dedujo (`via`: `device` o `person`) y la
  clave y version de la casa.
- **Lo que falta.** `missing` lista las partes `person`, `device` y `place` en
  `unknown` o `unresolved`. Lo `known` o `stated` no se vuelve a preguntar.
- **Dentro de la sesion** se usan las versiones de entidad de la apertura. Si en
  un turno cambia un hecho afirmado (otro dispositivo, la persona dicha cuando
  la cuenta no trae persona) se anade una copia con `cause: "edge"`; si no cambia
  nada, no se escribe.
- **Lo que completa el dialogo.** Si el turno anterior de la sesion termino
  preguntando por una parte (resultado declarado del core, `extended CR-0006`
  tramo B), el texto del siguiente turno del interlocutor se guarda tal cual como
  esa parte en estado `stated` (`origin: "dialog"`, con su turno) y se anade una
  copia con `cause: "dialog"`. Extended no interpreta lo dicho: lo guarda. Lo que
  se pregunta esta pendiente en la sesion (`awaiting_part`, nulo si nada) hasta
  el turno siguiente. Lo que alguien dice sin que se le pregunte ("soy papa") no
  cambia el marco.
- Una parte `stated` orienta y nunca concede: no cambia el nivel de permiso.
- El marco no es memoria del usuario: nunca se escribe en `entities` ni en
  engramas (meta ADR 0017, punto 4). Vive con la sesion y se archiva con ella.
- El marco se compone siempre, con el enriquecimiento apagado tambien.

### 5. El marco hacia el core

En cada turno conversacional, dentro de `turn_context` (que el core ya acepta y
del que ignora las partes que no conoce), extended manda la parte `frame` ya
resuelta, sin claves ni ids internos:

    {"channel": <service>, "person": {"state", "name"?}, "device": {"state",
     "name"?, "shared"?}, "place": {"state", "home"?, "locality"?, "timezone"?},
     "language": <idioma de la persona o del dispositivo, o null>,
     "missing": [...], "stated": {<parte>: <lo dicho>}?}

`channel` es la clase del consumidor (`service`): el ente sabe si le habla Home
Assistant u Open WebUI. Que hace el core con el marco (pista al enrutar,
contexto al responder, preguntar lo que falta) es de su ADR (`extended CR-0006`
tramo B). Si el turno del core termina preguntando por una parte, extended la
deja en `awaiting_part`.

### 6. Interfaz y telemetria

- `entity.unresolved` (CLI, principal `operator`, solo lectura): claves en estado
  `unresolved` de los marcos, con primera y ultima vez vistas y cuantas veces.
- La CLI gana `--audience` junto a `--interlocutor-profile`.
- El evento de cada turno conversacional gana `frame`: `composed` (booleano),
  `seq` y el estado de cada parte, y `missing`. Es lo que permite contar el
  criterio 5 de `H12` tambien por telemetria; la cuenta de referencia es la
  consulta sobre `session_frames`.

## Orden de despliegue

Extended se programa despues del borde y antes del core, pero se despliega
**despues del core** (que tiene que aceptar `restricted`) y **antes del borde**
(que empieza a mandar `restricted`, `audience` y `frame_facts`). Con el borde
antiguo, extended sigue funcionando: deduce `audience` y deja las partes del
marco en `unknown`.

## Consecuencias

- Migracion nueva (`session_frames` y `sessions.awaiting_part`), clases nuevas
  en el registro, identidad ampliada, contexto `general`, `entity.unresolved`,
  parte `frame` del contexto del turno y telemetria. Adicion de contrato con un
  cambio de valor del perfil en transicion: MINOR en la serie pre-1.0.
- Toca el ADR 0015 (la sesion gana el marco y lo que espera), el 0004 (resolver
  contra entities) y el 0016 (clases del marco). Se les apendiza un puntero.

## Lo que esta decision NO cubre

- El area del dispositivo, areas y aparatos (meta `H13`).
- Que hace el core con el marco (`extended CR-0006` tramo B, ADR del core).
- Como tratar a cada interlocutor, mas alla del tono declarado: es de
  conscience.
- Autenticacion de principales entre capas: el registro se sigue escribiendo
  solo por la CLI y la siembra.

## Estado posterior

2026-11-25 (ADR 0018, meta H12P9): `entity.unresolved` (punto 6) lista tambien
la `person` o el `device` sembrados sin `home` cuando el lugar queda `unknown`,
con `reason: "no_home"`; las filas de hoy llevan `reason: "no_entity"`.
