# Handoff de implementacion: prompt.stream y reasoning.stream enriquecidos

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-20
Base: `main`, su ultimo commit, con `v0.1.0` ya publicada.

Estado de contrato: reconciliado. Cierra lo que el brief de la fase 7a dejo para
la 7b y la 7b no recogio.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/POLITICA_WRITEBACK.md`. Es la pieza que este encargo tensiona.
3. `docs/EXTENDED_CONTRACT.md`, tabla de capacidades sobreescritas.
4. `src/ianest_extended/enrichment.py`, camino de `prompt.run`: esto es lo mismo
   hasta el momento de llamar al core.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## El hueco

El brief de la fase 7a dejo para la 7b tres capacidades: `reasoning.run`,
`task.run` y **`prompt.stream`**. La 7b cubrio las dos primeras. La tercera se
quedo fuera por un olvido del disenador, no por decision.

Consecuencia hoy: pedir la respuesta en streaming **pierde memoria y RAG**. Misma
pregunta, resultado distinto segun se pida de golpe o token a token. Es la regla 3
de `meta ADR 0007` incumplida -subir de capa debe sumar siempre- y afecta a un
consumidor real y proximo: una interfaz que muestre la respuesta segun se escribe
usara `prompt.stream`, no `prompt.run`.

## Dentro de esta tarea

### 1. `prompt.stream` y `reasoning.stream` pasan a SOBREESCRITAS

El enriquecimiento ocurre ANTES de abrir el flujo, que es lo que lo hace posible:
recuperar, componer el prompt dentro del presupuesto, y entonces llamar. A partir
de ahi se retransmite.

Se reutiliza el camino de `prompt.run`. Si una regla ya existe en el servicio, NO
se reescribe aqui.

### 2. La retransmision no se retrasa

El flujo se reenvia evento a evento segun llega. **No se acumula para enviar al
final**: eso convertiria un streaming en una llamada bloqueante lenta y anularia
el motivo de la capacidad.

La respuesta se va acumulando EN PARALELO a la retransmision, solo para poder
aplicar el write-back al cerrar.

### 3. Write-back al cerrar, y solo si cerro bien

Aqui esta la decision de diseno, y es la unica que no se deduce:

- **El write-back se aplica cuando el flujo termina LIMPIAMENTE**, sobre la
  respuesta completa acumulada, con la politica de `docs/POLITICA_WRITEBACK.md`
  sin cambios: los dos turnos a `dialog` y la extraccion episodica.
- **Si el flujo se corta -error, o el cliente se desconecta- NO se persiste
  nada.** Una respuesta a medias no es la respuesta, y guardarla como si lo fuera
  envenena la memoria: manana el ente recordaria como dicho algo que nunca
  termino de decir.
- El corte se registra en telemetria con su estado, para que se vea que hubo
  recuperacion y no hubo escritura.

### 3b. El `source_trace_id` de `prompt.stream` (decidido, no inferible)

`docs/POLITICA_WRITEBACK.md` exige que cada engrama conserve el
`source_trace_id`: el request DEL CORE que lo origino. Verificado por el cable
contra `v0.4.0`:

- `reasoning.stream` emite un objeto `trace` en su evento `done`, y ese trace
  lleva `request_id`. Ahi no hay problema: se usa ese.
- **`prompt.stream` NO lo emite.** Su `done` lleva `finish_reason`, `model`,
  `reasoning`, `text` y los contadores de tokens, y ninguna cabecera lo aporta.

Decision: para los engramas que nazcan de `prompt.stream`, **`source_trace_id`
queda a NULO**, que la columna admite. Se declara en el codigo y en el CHANGELOG
como limitacion conocida, con su motivo.

**NO se usa el `request_id` de esta capa en su lugar.** Ese campo significa "el
request del core que origino esto"; meter ahi un identificador propio produce una
traza que parece completa y no lo es, y es justo la clase de dato que engana a
quien audite dentro de seis meses. Es preferible un hueco visible a un valor
plausible y falso.

La asimetria se pide corregir al core por `extended CR-0005`: que `prompt.stream`
emita su trace en `done`, como ya hace su hermana. Cuando llegue, este nulo
desaparece sin tocar la politica.

### 4. `task.stream` NO se toca

Sigue reenviada y sin enriquecer. No es un olvido: el core no acepta plan
suministrado por esa capacidad en ninguna interfaz -es el hallazgo 6 que esta
capa le reporto-, asi que el enriquecimiento por subtarea no tiene por donde
entrar. El contrato debe declararlo, no omitirlo.

### 5. Las tres pieles

CLI, REST y MCP ya existen. Las dos capacidades siguen las reglas de cada una:
por CLI y REST se retransmiten; por MCP siguen sin exponerse, porque el streaming
no tiene forma en MCP y ese hueco ya esta declarado.

## Fuera de esta tarea (NO implementar)

- `task.stream` enriquecido.
- Cambiar la politica de write-back. Se aplica la que hay.
- Tocar el presupuesto de composicion, el ranking o los suelos.
- La fase 8 (despliegue) y la deuda D5.
- Tocar el core o el laboratorio.

## Criterios de aceptacion (falsables)

1. **Enriquecido de verdad.** `prompt.stream` con conocimiento del dominio
   disponible produce una respuesta anclada al corpus; con `--no-enrich`, no.
2. **No se retrasa.** El primer evento llega al cliente ANTES de que el flujo
   termine. Prueba automatizada con un stub que emita despacio: si la piel
   acumula, la prueba falla.
3. **Forma intacta.** Los eventos que llegan al cliente son los del core, sin
   anadir, quitar ni reordenar. Esta capa no inyecta eventos propios.
4. **Write-back al cerrar bien.** Un flujo completo persiste los dos turnos de
   `dialog` y ejecuta la extraccion, igual que `prompt.run`.
5. **Sin write-back si se corta.** Un flujo interrumpido a mitad NO escribe
   memoria. Prueba automatizada.
5b. **`source_trace_id` honesto.** Un engrama nacido de `reasoning.stream` lleva
   el `request_id` del core; uno nacido de `prompt.stream` lo lleva a NULO, nunca
   el identificador de esta capa.
6. **Corte trazado.** El corte queda en telemetria con su estado.
7. **Passthrough.** Con el enriquecimiento desactivado no hay recuperacion, ni
   inyeccion, ni escritura, y se sigue emitiendo traza propia.
8. **`reasoning.stream` igual.** Los criterios 1 a 7 valen tambien para ella.
9. **`task.stream` sin tocar.** Sigue reenviada, y el contrato dice por que.
10. **Sin regresion.** La suite en verde mas las pruebas nuevas.

## Impacto de version, a declarar

Una capacidad que se reenviaba pasa a sobreescribirse: la capa promete MAS, no
menos. Por `docs/VERSIONADO.md` eso es adicion compatible y en la serie pre-1.0
sube PATCH. Declararlo en el `CHANGELOG` como `0.1.1`; el tag lo corta el usuario.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama que ya esta activa. **No
cambies de rama, no crees rama, no commitees, no hagas push.**

Actualiza `docs/EXTENDED_CONTRACT.md` (tabla de sobreescritas, y el hueco
declarado de `task.stream`) y `CHANGELOG.md`.

No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
