# Handoff de implementacion: fase 7c-2, la piel MCP de la capa

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-20
Base: `main`, su ultimo commit, con la fase 7c-1 (REST) ya dentro.

Estado de contrato: reconciliado. Gobiernan `meta ADR 0007`, `extended ADR 0011`
y `ADR 0012`.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/handoff/fase_7c1_rest_brief.md` y lo ya entregado en `rest.py`: esta piel
   es hermana de aquella y comparte servicio.
3. `docs/decision_records/0012-capacidades-reflexivas.md`.
4. `core src/ianest_core/mcp_server.py` como REFERENCIA de forma, no para copiar.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## El problema que esta piel tiene y la REST no

La REST resuelve una ruta que recibe, asi que puede reenviar lo que no conoce sin
consultar nada. **MCP tiene que ENUMERAR sus herramientas** para que el cliente
las descubra. No hay forma de exponer una herramienta que no se declara.

Consecuencia: esta es la unica piel que SI depende del catalogo, y por tanto la
unica donde el catalogo ajeno puede faltar. La regla de degradacion es la misma
que en la CLI y no se relaja:

- las capacidades PROPIAS y las SOBREESCRITAS se declaran siempre, desde el
  catalogo local;
- las REENVIADAS se declaran desde el catalogo ajeno CACHEADO, si lo hay;
- sin cache y sin core, se sirve lo propio y se declara el hueco. No se aborta,
  no se inventa un catalogo vacio y no se finge exito.

Arrancar el servidor MCP NO puede exigir que el core responda.

## Dentro de esta tarea

1. **Servidor MCP** que expone el contrato de la capa como herramientas, llamando
   al mismo `ExtendedService` que usan la CLI y la REST. Ninguna logica nueva.
2. **Nombre de herramienta = nombre de capacidad.** `memory.recall` se expone como
   `memory.recall`. No se inventan alias ni se traducen nombres: el contrato es el
   mismo por las tres pieles.
3. **Parametros desde el catalogo**, igual que hizo la CLI: tipo, obligatoriedad y
   valores admitidos salen del dato, no de codigo por capacidad.
4. **Las reenviadas se invocan por el camino generico** del servicio, el mismo que
   usan CLI y REST.
5. **Errores** con la forma del ente (meta ADR 0009): los del core cruzan con su
   `type` y su `origin`; los propios llevan el de esta capa.

## Fuera de esta tarea (NO implementar)

- Streaming por MCP. El core declara que `prompt.stream` y `reasoning.stream` no
  tienen forma en MCP y deja el hueco explicito; aqui se hace igual y se declara.
- Autenticacion y despliegue como servicio: fase 8.
- Componer `runtime.health` o `config.validate`.
- Cambiar el comportamiento de ninguna capacidad, ni tocar la REST ya entregada.
- Tocar el core o el laboratorio.

## Criterios de aceptacion (falsables)

1. **Paridad de las tres pieles.** Para una capacidad propia, MCP devuelve lo
   mismo que la REST y que la CLI con los mismos parametros.
2. **Nombres iguales.** La herramienta se llama como la capacidad, sin alias.
3. **Propias siempre.** Con el core INALCANZABLE y sin cache, el servidor arranca
   y expone las capacidades propias.
4. **Reenviadas desde cache.** Con el core inalcanzable pero cache presente, las
   reenviadas aparecen como herramientas.
5. **Hueco declarado.** Sin cache y sin core, la ausencia de lo ajeno se declara;
   no se finge un catalogo completo.
6. **Arranque sin core.** Construir el servidor no exige que el core responda.
   Prueba automatizada.
7. **Reenvio real.** Invocar una herramienta reenviada llega al core y su
   respuesta vuelve intacta, con sus campos desconocidos.
8. **Errores.** Un error del core conserva `type` y `origin`; uno propio lleva el
   de esta capa.
9. **Huecos de streaming declarados.** Las capacidades de flujo no se exponen como
   herramienta y eso queda dicho, no omitido en silencio.
10. **Sin logica divergente.** Ningun handler MCP contiene reglas que CLI o REST no
    tengan.
11. **Sin regresion.** La suite en verde mas las pruebas nuevas.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama que ya esta activa. **No
cambies de rama, no crees rama, no commitees, no hagas push.**

Actualiza `docs/EXTENDED_CONTRACT.md` -las tres pieles existen ya- y
`CHANGELOG.md` bajo `[No publicado]`.

No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
