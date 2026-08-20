# Handoff de implementacion: fase 7c-1, la REST de la capa

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-20
Base: `main`, su ultimo commit.

Estado de contrato: reconciliado. Gobiernan `meta ADR 0007` (contrato uniforme),
`extended ADR 0011` y `ADR 0012` (catalogo fusionado, ya implementado).

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `ia_nest_meta/docs/ARQUITECTURA_DE_CAPAS.md`, reglas 1 a 4.
3. `ia_nest_meta/docs/FORMA_DE_ERRORES_Y_TRAZA.md` (meta ADR 0009).
4. `docs/decision_records/0012-capacidades-reflexivas.md`.
5. `docs/EXTENDED_CONTRACT.md`.
6. `core src/ianest_core/rest.py` como REFERENCIA de forma, no para copiar.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Por que existe esta fase

Hoy la unica piel de esta capa es la CLI. Sus dos consumidores declarados
-`ia_nest_core_conscience`, que escribira memorias delegadas y emitira eventos de
consolidacion, y `ia_nest_web`, que presentara memoria y conocimiento- **no
pueden consumirla**: las capacidades existen y no hay puerta.

Es ademas lo que hace posible la regla 4 de meta ADR 0007: un cliente escrito
contra el contrato apunta a una URL. Sin REST no hay URL a la que apuntar.

## Dentro de esta tarea

### 1. Un servidor REST que sirve el contrato COMPLETO

Las capacidades PROPIAS y las SOBREESCRITAS las sirve esta capa, llamando al
mismo `ExtendedService` que usa la CLI. **Ninguna logica nueva**: si una regla no
esta ya en el servicio, no se escribe aqui; se mueve al servicio.

Las capacidades REENVIADAS se proxean al core.

### 2. El reenvio por ruta NO necesita el catalogo

Decision de diseno, y es la que hay que respetar por encima de la comodidad:
**una peticion a una ruta que esta capa no sirve se proxea al core tal cual**, sin
consultar catalogo alguno. La ruta es el nombre de la capacidad
(`/prompt/stream` -> `prompt.stream`), que es el mecanismo generico que
`clients.py` ya implementa.

Consecuencia buscada: una capacidad que el core anada manana es alcanzable por la
REST de esta capa sin tocar codigo y sin refrescar nada. Es el invariante de
meta ADR 0007 en su forma mas limpia.

El catalogo sigue haciendo falta SOLO para `capability.list`, que esta
sobreescrita y devuelve la fusion.

### 3. Streaming reenviado

Una capacidad de flujo (`prompt.stream`, `reasoning.stream`, `task.stream`) se
retransmite evento a evento, sin acumular y sin convertir a JSON. El cliente ya
devuelve un flujo; la REST debe pasarlo tal cual con su tipo de contenido.

### 4. Errores que cruzan la capa

Un error del core llega al cliente **con su `type` y su `origin` originales**, sin
re-envolver (meta ADR 0009). Un error propio de esta capa lleva `origin` de esta
capa. El codigo de estado se conserva.

### 5. Configuracion

Direccion y puerto de escucha por configuracion, con el prefijo y el estilo de
las claves existentes. Por defecto, escucha SOLO en loopback: exponer memoria y
conocimiento a la red no es una decision que tome un valor por defecto.

## Fuera de esta tarea (NO implementar)

- **MCP**: es la fase 7c-2, y su problema es distinto -tiene que ENUMERAR sus
  herramientas, asi que si necesita el catalogo-. No la adelantes.
- Autenticacion. Hoy nadie autentica la identidad del request y esta registrado
  como concern en `ia_nest_meta/docs/CAPAS_FUTURAS.md`. Anadir media autenticacion
  es peor que ninguna: se declara que no hay y se escucha en loopback.
- Servicios de sistema, unidades ni despliegue: eso es la fase 8.
- Componer `runtime.health` o `config.validate` (ADR 0012 punto 3: esperan
  consumidor). Se reenvian, como en la CLI.
- Cambiar el comportamiento de ninguna capacidad. Esto anade una PIEL.
- Tocar el core o el laboratorio.

## Criterios de aceptacion (falsables)

1. **Paridad con la CLI.** Para una capacidad propia, la REST devuelve lo mismo
   que la CLI con los mismos parametros. Prueba automatizada sobre las dos.
2. **Capacidad propia servida aqui.** `memory.recall` y `knowledge.status`
   responden sin llamar al core para nada que no sea su propio trabajo.
3. **Sobreescrita enriquecida.** `prompt.run` por la REST de esta capa lleva
   memoria y RAG; el mismo `prompt.run` por la REST del core, no. La diferencia se
   observa en la respuesta o en la telemetria.
4. **Reenvio sin catalogo.** Contra un stub que sirva una ruta que esta capa NO
   conoce y que NO aparece en ningun catalogo, la peticion llega al stub y su
   respuesta vuelve intacta. Es el invariante: no se consulta catalogo.
5. **Reenvio opaco.** Campos desconocidos en la respuesta del stub llegan al
   cliente sin filtrar ni reescribir.
6. **Streaming.** Una ruta de flujo del stub se retransmite evento a evento; no se
   acumula ni se convierte.
7. **Error ajeno intacto.** Un error del stub llega con su `type` y su `origin`
   originales y su codigo de estado.
8. **Error propio.** Un error de esta capa lleva su `origin` y su tipo.
9. **`capability.list` fusionada.** Por la REST devuelve lo mismo que por la CLI:
   propias, sobreescritas y reenviadas, con procedencia.
10. **Loopback por defecto.** Sin configuracion explicita, no escucha en una
    interfaz de red.
11. **Sin logica divergente.** Ningun handler REST contiene reglas que la CLI no
    tenga; ambos llaman al mismo servicio. Verificable leyendo el diff.
12. **Sin regresion.** La suite en verde mas las pruebas nuevas.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama que ya esta activa. **No
cambies de rama, no crees rama, no commitees, no hagas push.**

Actualiza `docs/EXTENDED_CONTRACT.md` -la REST deja de ser futura- y
`CHANGELOG.md` bajo `[No publicado]`.

No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
