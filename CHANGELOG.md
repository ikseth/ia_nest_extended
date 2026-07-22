# Changelog

Formato basado en Keep a Changelog; SemVer (ver core `docs/VERSIONADO.md`).
Sin acentos por convencion.

## [No publicado]

### Anadido
- Semilla del repo: contexto, alcance, dependencias, genesis (ADR 0001) y plan
  inicial de fases en borrador (memoria primero).
- Clases de memoria y autoridad de escritura (ADR 0002): la memoria es un registro
  de tipos declarados; clases estrictas (dueno extended) vs delegadas (dueno otra
  capa, p. ej. conscience). Autoridad de escritura por capacidad, lectura uniforme,
  dogfooding del contrato y costura de consolidacion (`memory.consolidation`,
  conscience pide / extended ejecuta). Reescribe la Fase 2 del PLAN. Sin contrato
  publico cortado todavia (se corta en Fase 7); impacto de version: ninguno.
- `docs/VISION_MEMORIA.md`: el fin de la memoria (yo simulado, continuo y
  evolutivo), la frontera sustrato/juicio con conscience, las funciones de memoria
  deseadas heredadas de la cantera `ia_nest`, y la separacion entre memoria y
  conocimiento (RAG). Anadido al orden de lectura de `AGENTS.md`.

### Cambiado
- PLAN reconciliado en sus fases de memoria: Fase 1 pasa a FORMA no congelada
  (mas mapeo identidad->clave y politica de composicion/presupuesto), Fase 3
  abandona el nombre `read_context` (retirado del core, ADR 0035) y suma politica
  de write-back y telemetria propia, Fase 4 queda como MECANISMO de consolidacion
  (el juicio es de conscience) y Fase 7 cubre tambien el consumo de la GUI.
- `ALCANCE.md`: extended hospeda y sirve la memoria de comportamiento/identidad,
  pero no la escribe (delegadas, ADR 0002); el juicio de consolidacion es de
  conscience.
- `AGENTS.md`: convencion de texto explicita (ASCII puro, sin acentos ni `n` con
  virgulilla) e identificadores en ingles snake_case (core ADR 0016).
