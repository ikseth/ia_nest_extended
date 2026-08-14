# Dependencias de ia_nest_extended

Politica: `ia_nest_meta/docs/REGISTRO_CAPAS.md` (regla de vinculo entre capas por
SemVer; origen historico: core ADR 0032). Cada capa fija la version de la que
depende y versiona su propio contrato.

Este fichero es el manifiesto de esta capa y es FUENTE DE VERDAD de sus
dependencias; el registro de capas del ente es un indice que lo refleja.

## Depende de

- `ia_nest_core >=0.2 <0.4`. Verificada EN VIVO en lab contra v0.2.0 y v0.3.0
  (redespliegue por pull + e2e de continuidad de memoria: sesion A escribe,
  sesion B recupera). El unico cambio de v0.3 que toca lo que extended consume es
  `core ADR 0043` (router semantico), que NO altera la peticion/respuesta de
  `prompt.run` (la rama "sin modelo ni dominio" resuelve al dominio por defecto
  `general`, como ya ocurria); ADR 0044/0045 tocan `task.run`, que extended no
  consume aun. El techo `<0.4` se reevalua al entregarse `task.plan` (core v0.4).
  Contratos consumidos (core `CORE_CONTRACT.md`):
  - `prompt.run` (inferencia enriquecida); `task.run` cuando se consuma,
  - `domain.route` (semantico desde v0.3, `core ADR 0043`) para el gate de dominio
    del RAG (Fase 5),
  - `task.plan` (futuro, core v0.4, `core ADR 0040`) para el RAG per-subtarea,
  - contexto de identidad del request (clave de indexacion de memoria),
  - telemetria CSV/JSONL (incluye `finish_reason`, core ficha v0.2/0002),
  - `config.validate`, `runtime.health` segun necesidad.

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
