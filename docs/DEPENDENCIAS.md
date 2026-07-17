# Dependencias de ia_nest_extended

Politica: core ADR 0032 (dependencias entre capas por SemVer). Cada capa fija la
version de la que depende y versiona su propio contrato.

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

Esta capa versiona su propio contrato publico (SemVer). Su version inicial se
corta al cerrar el primer vertical de memoria (ver `docs/PLAN.md`).
