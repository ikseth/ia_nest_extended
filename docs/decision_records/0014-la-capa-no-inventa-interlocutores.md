# Decision 0014: la capa no inventa interlocutores

Fecha: 2026-09-22

## Contexto: un default de CLI heredado por un servidor

El ADR 0011, punto 7, hizo opcional la identidad del request: `user_id`,
`service`, `session_id` y `namespace` toman defaults de configuracion, y si no
se indica `session_id` se GENERA UNO Y SE RECUERDA en un fichero local. Su
justificacion esta escrita y es explicita:

> "con un aleatorio por comando, el tier `dialog` dejaria de encadenar dos
> invocaciones seguidas y la memoria conversacional del CLI no funcionaria."

Ese razonamiento es correcto **para una CLI**: un humano, un terminal, un hilo.
Quien invoca dos veces seguidas es la misma persona continuando la misma
conversacion, y suponerlo no es suponer nada.

El problema es donde se aplica. `_request_identity`, el camino que usan REST y
MCP, llama a la misma `resolve_identity` sin desactivar ese recuerdo. Un
servidor que puede atender a varios interlocutores usa un default disenado para
cuando solo hay uno.

## Lo medido en rocinante el 2026-09-22

- `default_user_id` vale `local_operator`. Toda llamada sin identidad es ese
  usuario, sea quien sea quien llame.
- El fichero de sesion del servicio, con fecha del 2026-09-21, contiene un solo
  uuid y NO rota nunca.
- Dentro de esa sesion: **18 engramas, de las 10:58 a las 21:07 UTC** -diez
  horas-, todos bajo `local_operator`, mezclando la conversacion de cine del
  operador con los prompts de un addon de Kodi conectado ese mismo dia.
- Y un `thread_summary` de esa sesion, que resume las dos conversaciones como si
  fueran un hilo.

El roster no es lo que falla: dice que `dialog` es de ambito sesion y `episodic`
de ambito usuario, y eso sigue siendo lo correcto. Lo que falla es que a un
llamante anonimo se le adjudica una identidad que no es suya y un hilo que no es
suyo.

La capa se publico mas alla de loopback el 2026-09-21, el mismo dia en que
empieza el fichero de sesion. **El default dejo de ser inocuo en el momento en
que la superficie dejo de ser personal**, y nadie lo reviso entonces.

## Decision

### 1. El criterio

**Una superficie que puede atender a mas de un interlocutor no suministra
defaults de identidad.** Inventar una identidad es cosa del cliente, que sabe a
quien tiene delante; no de la capa, que no lo sabe.

La CLI puede seguir recordando su sesion. REST y MCP no pueden suponerla.

### 2. En REST y MCP, `user_id` y `session_id` son obligatorios

Una peticion sin ellos se rechaza con error tipado que nombra el campo, como
cualquier otra entrada invalida. `service` y `namespace` conservan sus defaults:
describen el origen de la llamada, no quien habla.

### 3. El servidor no recuerda sesiones

`remember_session=False` en el camino de peticion. El fichero de estado de
sesion sigue siendo estado local de la CLI, que es para quien se penso.

## Consecuencias

- **Rompe a los clientes REST/MCP que hoy no mandan nada**, que en el laboratorio
  es el addon de Kodi. Serie pre-1.0: MINOR, con nota de migracion en el
  CHANGELOG.
- `default_user_id` deja de alcanzar las superficies de servidor. Conserva su
  sentido para la CLI.
- **La puerta nunca ejercito esto**, porque siempre manda identidad explicita.
  Es un hueco de cobertura del instrumento, y se declara aqui: lo encontro el
  operador usando el sistema, no la medida.

## Lo que esta decision NO cubre

No es autenticacion. La capa se niega a inventar una identidad; no verifica la
que recibe. Verificarla es trabajo de la frontera (`ia_nest_meta` ADR 0011), y
esta decision no mueve esa frontera: solo deja de taparle el hueco con una
suposicion.

Tampoco decide la **frontera del hilo** -cuanto dura una sesion, quien la
cierra-. Queda abierta, y conviene saber que hoy no esta modelada: `dialog` se
archiva por reloj a las 4 h sin mirar si su sesion sigue viva, de modo que una
conversacion larga pierde su principio mientras una sesion anonima no termina
nunca. Las dos cosas son la misma ausencia.
