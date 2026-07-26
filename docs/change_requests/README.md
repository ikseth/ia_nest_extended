# Change Requests (CR) entre capas del ente

Estado: PROPUESTA (a elevar como doctrina del ente en el core)
Version: 0.1 - 2026-07-26

Canal formal para que una capa solicite un cambio en el contrato de otra capa de
la que depende (tipicamente hacia el core). Complementa el grafo de dependencias
por SemVer (core ADR 0032), que define de QUIEN depende cada capa pero no COMO se
pide un cambio de vuelta.

## Regla de oro

La capa de abajo PROPONE; la capa de arriba DISPONE. La capa origen justifica la
NECESIDAD y sugiere una forma; la capa destino decide su contrato, su forma y su
version. La forma sugerida no es vinculante. Solo el resultado reconciliado por
el usuario se registra (coherente con el modo multi-IA).

## Cuando se usa un CR

Cuando una capa necesita una capacidad o un cambio de contrato de una capa de la
que depende, y NO puede resolverlo en su propia capa. Si se puede resolver en la
propia capa (p.ej. enriquecimiento sobre el core, via 2), no es un CR.

## Anatomia de un CR

Un fichero `CR-NNNN-<slug>.md` con:

- `id`, `fecha`, `capa origen`, `capa destino`, `estado`.
- Caso de uso motor (por que se necesita, con evidencia).
- Que se pide (la capacidad o cambio).
- Forma sugerida (contrato propuesto; NO vinculante).
- Impacto SemVer previsto en la capa destino y version que necesitaria la origen.
- Alternativas consideradas y por que no bastan.
- Tension doctrinal, si la hay (que ADRs toca).

## Estados

    propuesto -> aceptado | reformulado | rechazado -> entregado

## Flujo

1. La capa origen redacta el CR en su repo (`docs/change_requests/`), estado
   `propuesto`, y lo comunica a la capa destino (issue en el repo destino).
2. La capa destino DISPONE: si acepta (o reformula), lo convierte en un ADR
   propio + item de su PLAN, con su forma y su version objetivo. Si rechaza, con
   motivo. El CR de la origen refleja el resultado.
3. Al entregarse (nueva version publicada de la capa destino), la origen
   actualiza su dependencia (`DEPENDENCIAS.md`) y marca el CR `entregado`.

## Donde vive la doctrina

Esta definicion es doctrina del ente: su version autoritativa se eleva al core
(`docs/FRONTERAS.md` / ADR), donde vive el registro de capas (core ADR 0032).
Cada repo mantiene en `docs/change_requests/` los CR que emite y su estado.

## Indice de CR emitidos por esta capa

- [CR-0001](CR-0001-checkpoint-enriquecimiento-por-subtarea.md) - checkpoint de
  enriquecimiento por subtarea en `task.run` (destino: core). Estado: propuesto.
