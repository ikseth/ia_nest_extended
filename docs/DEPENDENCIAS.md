# Dependencias de ia_nest_extended

Politica: `ia_nest_meta/docs/REGISTRO_CAPAS.md` (regla de vinculo entre capas por
SemVer; origen historico: core ADR 0032). Cada capa fija la version de la que
depende y versiona su propio contrato.

Este fichero es el manifiesto de esta capa y es FUENTE DE VERDAD de sus
dependencias; el registro de capas del ente es un indice que lo refleja.

## Depende de

- `ia_nest_core >=0.2 <0.3`. Contratos consumidos (core `CORE_CONTRACT.md`):
  - `prompt.run` y `task.run` (inferencia enriquecida),
  - contexto de identidad del request (clave de indexacion de memoria),
  - telemetria CSV/JSONL (incluye `finish_reason`, core ficha v0.2/0002),
  - `config.validate`, `runtime.health` segun necesidad.

## Es dependencia de

- `ia_nest_core_conscience` (memoria de comportamiento).
- `ia_nest_web` (presentacion de la memoria/conocimiento).

## Contrato propio

Esta capa versiona su propio contrato publico (SemVer,
`ia_nest_meta/docs/POLITICA_SEMVER.md`). Su version inicial se corta al cerrar
el primer vertical de memoria (ver `docs/PLAN.md`). Al cortar tag, actualizar la
fila de esta capa en el registro de capas del ente (meta ADR 0003).

PENDIENTE: declarar QUE cuenta como contrato publico de esta capa (que expone y
que puede romperse). La politica lo exige para poder versionarse y deja la lista
a cada capa. Sin ella no se puede cortar el primer tag.
