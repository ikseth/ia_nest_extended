# Decision 0011: interfaz de consumo de la capa (contrato uniforme)

Fecha: 2026-08-14

## Decision

La interfaz de consumo de esta capa (Fase 7) es el CONTRATO UNIFORME de
`ia_nest_meta/docs/ARQUITECTURA_DE_CAPAS.md` (meta ADR 0007), aplicado asi:

1. **Reenvia** sin alterar las capacidades del core que no enriquece, con un
   mecanismo GENERICO (sin codigo por capacidad).
2. **Sobreescribe** `prompt.run`, `reasoning.run` y `task.run`, conservando la
   forma de peticion y respuesta del core. Lo unico que cambia es que el prompt
   ejecutado lleva contexto recuperado.
3. **Anade** las capacidades propias `memory_type.*`, `memory.*` y
   `knowledge.*`.
4. Los nombres de las capacidades sobreescritas son los MISMOS que los del core.
   La ambiguedad de cita la resuelve la convencion vigente: `core prompt.run`
   frente a `extended prompt.run`.
5. El contrato publico de la capa se declara en `docs/VERSIONADO.md` y sus
   capacidades en `docs/EXTENDED_CONTRACT.md`. El catalogo del core NO se
   re-declara aqui: se referencia (convencion transversal 6, meta ADR 0008). Lo
   que esta capa versiona de lo ajeno es la GARANTIA de reexponerlo sin
   alterarlo, en el rango de `docs/DEPENDENCIAS.md`.

## Motivo

La Fase 7 estaba escrita como "consolidar la interfaz de consumo", sin decir que
forma tenia. La implementacion existente hasta la Fase 5c habia derivado a un
catalogo PROPIO y MENOR que el del core: esta capa solo habla `prompt.run`, de
modo que subir de capa hacia perder `reasoning.run`, `task.run` y el streaming.
Eso invierte el sentido de una capa llamada "extended" y obliga al operador a
usar dos interfaces distintas segun lo que necesite.

El invariante del ente (meta ADR 0007) resuelve la forma: anadir una capa no
debe obligar a editar ninguna capa existente ni el cliente. Un catalogo propio y
menor lo incumple por partida doble -degrada al subir, y obliga a escribir una
piel por capacidad cada vez que el core anade una-.

Sobre la alternativa de que fuera el core quien llamase hacia arriba: se estudio
y se descarta. `core ADR 0031` dejo el punto abierto y `core ADR 0035` lo cerro
por falta de consumidor, motivo hoy caducado; pero `core ADR 0040`, resolviendo
`extended CR-0001`, aporto el argumento que lo cierra de verdad: los prompts de
subtarea quedan fijados en la etapa PLAN, luego el enriquecimiento por subtarea
NO necesita ocurrir dentro del bucle de orquestacion del core. Sin esa necesidad,
un puerto solo resolveria un problema de interfaz, y para eso no se cambia el
fundamento del core.

## Consecuencia

- La Fase 7 del PLAN se reescribe en cuatro rebanadas (7a servicio uniforme y
  CLI, 7b `reasoning.run` y `task.run`, 7c REST y MCP, 7d tag).
- La Fase 7a deja de ser "consolidar los cuatro harnesses en un CLI espejo" y
  pasa a ser el servicio con reenvio generico y sobreescritura, mas el CLI como
  piel. Su criterio de salida incluye el test de conformidad de meta ADR 0007:
  contra un core stub que declare una capacidad desconocida, esa capacidad debe
  ser alcanzable a traves de esta capa SIN tocar su codigo.
- `docs/EXTENDED_CONTRACT.md` nace en estado `propuesta` y pasa a `activo` al
  cortar el primer tag: declarar activo un contrato sin implementacion seria la
  costura sin consumidor que `core ADR 0035` advierte.
- Se cierra el PENDIENTE de `docs/DEPENDENCIAS.md` ("declarar QUE cuenta como
  contrato publico"), requisito para poder cortar el primer tag.
- `task.run` sobreescrito requiere `task.plan` (core v0.4, no entregado). La
  Fase 7b espera; no bloquea a 7a.
- Riesgo abierto, a verificar antes de implementar: el reenvio generico de
  STREAMING (`prompt.stream`, `reasoning.stream`, eventos de `task.run`) puede no
  ser barato. Si lo confirma la verificacion, el streaming se declara diferido de
  forma explicita en lugar de darse por supuesto.

## Impacto de version

Ninguno todavia: no hay contrato cortado. La decision fija QUE se versionara.
