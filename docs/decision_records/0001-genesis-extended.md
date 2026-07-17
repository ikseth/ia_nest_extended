# Decision 0001: genesis de ia_nest_extended

Fecha: 2026-07-17

## Decision

Se funda `ia_nest_extended` como la capa de enriquecimiento del ente IA_NEST
(memoria, RAG, datos web), sobre `ia_nest_core` v0.2, siguiendo las decisiones
ya reconciliadas en el core:

- Enriquecimiento EN LA CAPA (via 2): recuperar -> enriquecer prompt -> llamar
  al core -> write-back. El core no se toca (core ADR 0031/0035).
- La identidad de segmentacion del core es la clave de indexacion (core
  ADR 0011/0035).
- La memoria respeta las 3 lecciones de la cantera (core ADR 0011): tiers
  distintos, separar lectura/escritura, consistencia de namespace.
- Primera capa del ente a construir; memoria primero (la necesita conscience).

## Motivo

El ente crece por capas (core ADR 0033) y extended es la raiz de dependencias:
conscience necesita su memoria de comportamiento. Fundarla con las decisiones
del core ya escritas evita re-litigar y mantiene la coherencia del ente.

## Consecuencia

- Repo sembrado con contexto, alcance, dependencias y plan (borrador).
- El core alineara su mapa de repos al nombre `ia_nest_extended` (antes
  `ia_nest_core_extended`).
- Las fases se detallan en `docs/PLAN.md`, pendientes de reconciliacion.
