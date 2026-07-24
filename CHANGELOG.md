# Changelog

Formato basado en Keep a Changelog; SemVer (ver core `docs/VERSIONADO.md`).
Sin acentos por convencion.

## [No publicado]

### Anadido
- Sustrato de memoria de la Fase 2: paquete Python con ports `MemoryStore` y
  `Embedder`, registro y validacion V1-V4 con errores tipados, autoridad de
  escritura por principal, `FakeEmbedder`, adaptador postgres+pgvector,
  migracion parametrizada, semillas del roster, recuperacion multi-espacio,
  archivo sin borrado, entorno postgres local y pruebas A1-A5. Sin contrato
  publico cortado; impacto de version: ninguno.
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
- `docs/FORMA_ENRIQUECIMIENTO.md` (Fase 1): forma no congelada del enriquecimiento,
  mapeo identidad->clave y politica de composicion/presupuesto. En el orden de
  lectura de `AGENTS.md`.
- Modelo de relevancia y gradiente de tiers (ADR 0003): recuperacion por ranking
  ponderado (recencia, similitud, estabilidad, score; dominio como filtro); un
  tier se define por su vector de pesos, no por una ventana. Gradiente de tres
  tiers (conversacional / episodica / semantica); corto/medio/largo se disuelven
  en la curva de recencia y el namespace `tasks`. Motor `postgres + pgvector`.
  Numeros de arranque configurables. Impacto de version: ninguno.
- Entities y modelo multi-espacio (ADR 0004): cada espacio de cercania en su
  representacion natural (semantico denso; temporal y entidades exactos; dominio
  como filtro); entities como tercer patron (perfil mutable versionado + registro
  de `entity_id` + etiquetado `entity_refs` mecanico en write-back; perfilar es
  juicio de conscience). Asociacion graduada y temporal registradas y diferidas.
  Vocabulario: engrama. Impacto de version: ninguno.
- `docs/ROSTER_MEMORIA.md`: roster de tipos de memoria de la Fase 2 (estrictos
  `dialog`/`episodic`/`semantic`; delegados `entities`/`identity`/`principles`/
  `safety`; `ops` y RAG fuera), RECONCILIADO. En el orden de lectura de
  `AGENTS.md`.
- Disolucion de `historic` (ADR 0005, supersede parcial de la enumeracion del
  ADR 0002): personalidad = `identity` + `principles` con inyeccion permanente;
  la evidencia formativa son `evidence_refs` desde delegadas hacia engramas (el
  archivo es direccionable por no-borrado); relato formativo por relevancia
  diferido. Regla de aliasing precisada: coincidir en TODOS los ejes. Impacto de
  version: ninguno.
- `docs/handoff/fase_2_brief.md`: brief de implementacion de la fase 2 para el
  agente codificador (esquema postgres+pgvector, ports, registro y validacion
  V1-V4, autoridad de escritura, recall multi-espacio, semillas del roster,
  blanco de aceptacion A1-A5). Impacto de version: ninguno.

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
- Reconciliadas las tres senalizaciones de la entrega de fase 2:
  `FORMA_ENRIQUECIMIENTO.md` corregida (`user_id` vertebra los tipos
  experienciales, no los delegados globales/entidad; `namespace` en clave salvo
  `dialog`), namespaces homonimos de las delegadas ratificados en el roster
  (`entities`/`principles`/`safety`), e interpretacion del criterio A4 sobre
  senales ratificada.
