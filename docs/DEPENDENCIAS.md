# Dependencias de ia_nest_extended

Politica: `ia_nest_meta/docs/REGISTRO_CAPAS.md` (regla de vinculo entre capas por
SemVer; origen historico: core ADR 0032). Cada capa fija la version de la que
depende y versiona su propio contrato.

Este fichero es el manifiesto de esta capa y es FUENTE DE VERDAD de sus
dependencias; el registro de capas del ente es un indice que lo refleja.

## Depende de

- `ia_nest_core >=0.7.0 <0.8` (desde extended `v0.8.0`). Sube el suelo:
  extended normaliza `child` a `restricted` y lo manda en la identidad, y solo
  el core `v0.7.0` acepta `restricted` (core ADR 0055, D5). Por eso el core se
  despliega antes. `turn_context.frame` solo va cuando el catalogo del core
  declara `turn_context`, tambien en `domain.route`.

  Rango anterior, `>=0.4.2 <0.7` (desde extended `v0.7.0`). Por que se puede subir
  el techo: extended solo manda `turn_context` cuando el catalogo del core lo
  declara (core ADR 0054, `v0.6.0`); con un core anterior la peticion es
  identica a la de `v0.6.5`, y eso lo prueba la suite (cuerpo enviado sin el
  parametro declarado). El laboratorio ya corria extended `v0.6.5` contra core
  `v0.5.0`. Comprobacion en vivo contra el tag `v0.6.0`: al desplegar la tanda A
  de meta H12 (H12P7), pendiente.

  Rango anterior, `>=0.4.2 <0.5`. El campo `identity.interlocutor_profile` del
  core se reexpone como parte de la identidad del request, y el rango exige la
  version que declara ese campo y su validacion. Comprobacion en vivo contra
  `v0.4.2`, pendiente.

  Comprobacion anterior del rango `>=0.4 <0.5`. **Re-verificado en vivo contra el
  TAG `v0.4.0`**
  (commit `1fbc0e4`) el 2026-08-20, cumpliendo el deber de re-verificacion de
  `ia_nest_meta/docs/REGISTRO_CAPAS.md`: no basta subir el techo, hay que poder
  responder por que.

  **Que se comprobo y como.** Laboratorio pineado al tag y servicios REINICIADOS
  -actualizar el arbol no reinicia un proceso, y eso ya nos costo una tarde-, con
  el core declarando `core_version: 0.4.0`. Ejercidas por la CLI de esta capa las
  nueve comprobaciones que cubren todo lo que consume, 9 de 9 en verde:
  `capability.list` fusionada (27 capacidades), `prompt.run` enriquecido con
  recuperacion RAG real, reenvio generico, `task.plan` publicando `degradations`,
  `task.run` enriquecido por subtarea con `plan_attempts: 0`, y las capacidades
  propias.

  **Las tres rupturas de v0.4.0, y por que ninguna nos afecta.**
  `task.run` deja de ser SSE y devuelve JSON por `POST /task/run`: es la forma que
  esta capa ya consume desde la fase 7b, verificada de nuevo aqui. `tags` se
  retira de `domain.route`: esta capa nunca lo envio. `routing_rules` sale del
  esquema de configuracion del core: esta capa no lo conoce.

  **El cambio de significado, comprobado aparte.** Con `requirements` vacio,
  `requirements_covered` pasa de `true` a `false`. No afecta: esta capa NO
  interpreta ese campo -lo copia intacto junto al resto del plan, `core ADR
  0048`-, y se verifico que no aparece en su codigo. Observado en laboratorio con
  la degradacion `requirements_unavailable`; conviene no leerla al reves, porque
  el gate del core usa esa senal para detectar una capa que pierde campos: aqui es
  varianza del planificador, que en esa pasada no declaro requisitos, y en otras
  del mismo dia declaro tres con su `covered_by`.

  Contratos consumidos (core `CORE_CONTRACT.md`):
  - `prompt.run` y `reasoning.run` (inferencia enriquecida),
  - `task.plan` y `task.run` con plan suministrado (RAG por subtarea),
  - `domain.route` y `domain.list` (gate de dominio del conocimiento),
  - `capability.list` (catalogo que esta capa fusiona con el suyo),
  - contexto de identidad del request (clave de indexacion de memoria),
  - telemetria CSV/JSONL, `config.validate` y `runtime.health` segun necesidad.

## Es dependencia de

- `ia_nest_core_conscience` (memoria de comportamiento).
- `ia_nest_web` (presentacion de la memoria/conocimiento).

## Contrato propio

Esta capa versiona su propio contrato publico (SemVer,
`ia_nest_meta/docs/POLITICA_SEMVER.md`). QUE cuenta como contrato esta declarado
en `docs/VERSIONADO.md` y las capacidades en `docs/EXTENDED_CONTRACT.md`
(ADR 0011); con eso queda cerrado el PENDIENTE que impedia cortar el primer tag.
El tag se corta en la Fase 7d, no antes. Al cortarlo, actualizar la fila de esta
capa en el registro de capas del ente (meta ADR 0003).

Relacion con el rango de arriba: esta capa REEXPONE el contrato del core del
rango declarado, sin alterarlo, y no lo re-declara (convencion transversal 6,
meta ADR 0008). Por eso una rotura del contrato del core no es por si misma una
rotura del contrato de esta capa: mueve el rango, y la version de esta capa sube
solo si cambia lo que ELLA promete, su garantia de transparencia incluida.
