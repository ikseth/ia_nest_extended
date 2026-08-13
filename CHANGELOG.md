# Changelog

Formato basado en Keep a Changelog; SemVer (ver core `docs/VERSIONADO.md`).
Sin acentos por convencion.

## [No publicado]

### Anadido
- Aislamiento de recursos y least-privilege (ADR 0010): autoridad de escritura en
  dos niveles -principal en codigo (ADR 0002) + GRANT del motor (pared dura que no
  confia en el codigo)-. Stores segmentados por confianza con roles least-privilege;
  extended read-only sobre el yo protegido y el conocimiento; solo conscience
  escribe lo protegido; conocimiento aislado (curacion operador hoy / conscience
  guardian futuro). Separable desde el dia uno para escalar aislamiento sin
  reescribir (rol -> schema -> base -> instancia, DMZ). Con diagrama. Impacto: ninguno.
- Enmienda ADR 0007: conscience ANADE una capa reflexiva, no sustituye la mecanica
  de extended (opcion A); frontera de confianza candidato->confiable (cortafuegos
  de inyeccion), endurecida por ADR 0010.
- Enmienda ADR 0009: la incorporacion de conocimiento esta gobernada por
  supervision (operador hoy, conscience guardian futuro), sin que el conocimiento
  sea la identidad del ente; store aislado (ADR 0010).
- Modelo de datos de conocimiento por dominio (ADR 0009, Fase 5b): relacion N:M
  dominio<->corpus a nivel de corpus via tabla `rag_corpus_domains` con
  `source`/`confirmed` (auto-etiquetado como propuesta, confirmacion del operador;
  la recuperacion gatea por vinculos confirmados). Premisa: el conocimiento es
  externo (ops), no el yo del ente. Con diagramas (mermaid). Workflow y ampliacion
  del lab pendientes de reconciliar. Impacto: ninguno.

### Corregido
- H1 del e2e de Fase 5: el dominio explicito se valida una vez por ejecucion
  contra `domain.list` antes de recuperar o invocar `prompt.run`; un dominio
  desconocido produce `InvalidCoreDomainError` con el catalogo valido. El
  dominio auto-ruteado se usa para gate y ruteo, mientras ausencia o `general`
  mantienen recuperacion global y omiten el dominio de `prompt.run`. Sin
  cambios en el contrato publico; impacto de version: ninguno.

### Anadido
- Implementacion de la Fase 5, camino RAG upfront: migracion separada para
  `rag_corpora`/`rag_chunks`, ingesta idempotente de `.txt`/`.md`, recuperacion
  vectorial con gate opcional de dominio, `domain.route` configurable,
  composicion conservadora dentro del presupuesto, telemetria `rag.retrieve`,
  configuracion/instalador y pruebas con stub del core y `FakeEmbedder`.
  `task.run`/`task.plan`, el core y las tablas de memoria quedan intactos. Sin
  contrato publico cortado; impacto de version: ninguno.
- Forma del RAG operativo (ADR 0008) y brief de la Fase 5 camino upfront: RAG
  como subsistema hermano (no tier), tablas `rag_corpora`/`rag_chunks` en el mismo
  motor, ingesta curada, recuperacion con gate de dominio (D1) y dominio explicito
  o via `domain.route` (D2), presupuesto duro (D3), integracion upfront en
  `prompt.run`. Per-subtarea diferido a `task.plan` (core v0.4). Impacto: ninguno.

### Cambiado
- Compatibilidad con core v0.3.0 VERIFICADA EN VIVO en lab: redespliegue del
  core por pull (v0.2.0 -> v0.3.0), config valida, `prompt.run` con forma intacta,
  y e2e de continuidad de memoria (sesion A escribe, sesion B recupera via
  bge-m3). Pin de `DEPENDENCIAS.md` subido a `ia_nest_core >=0.2 <0.4`. Impacto de
  version: ninguno.
- Core v0.3.0 liberada: PLAN Fase 5 sale de PARADA (CR-0001 resuelto, core
  ADR 0040, REFORMULADO a `task.plan`+`task.run` con plan; objetivo core v0.4, no
  entregado). RAG upfront desbloqueado; per-subtarea espera a `task.plan`.
  `DEPENDENCIAS.md`: v0.3.0 compatible a nivel de contrato (solo la toca ADR 0043,
  que no altera `prompt.run`); el pin sube a `<0.4` tras el e2e contra un v0.3
  desplegado en lab. Impacto de version: ninguno.

### Anadido
- Proceso de Change Request entre capas (`docs/change_requests/README.md`,
  PROPUESTA a elevar como doctrina del ente en el core): canal formal
  propone/dispone para pedir cambios de contrato a una capa superior, sobre el
  grafo de dependencias SemVer (core ADR 0032).
- CR-0001 (propuesto, destino core): checkpoint de enriquecimiento por subtarea
  en `task.run`, para RAG per-subtarea token-eficiente sin reabrir la frontera
  enriquecimiento/herramienta (core ADR 0031). Impacto previsto en el core: minor.

### Cambiado
- Fase 5 (RAG) en PARADA hasta resolver CR-0001: no se construye sobre una
  decision de core no resuelta. `AGENTS.md` incluye `docs/change_requests/` en el
  orden de lectura.

### Anadido
- Implementacion de la Fase 4: evento tipado `ConsolidationEvent`, ejecutor
  transaccional con autoridad, lineage y archivo sin borrado, y CLI
  `python -m ianest_extended.maintain` con promocion literal
  `episodic` -> `semantic`, archivado de `dialog`, telemetria y `--dry-run`.
  Umbrales configurables documentados en `.env.example` y cinco criterios de
  aceptacion PostgreSQL con skip explicito sin DB local. Sin contrato publico
  cortado; impacto de version: ninguno.
- Diseno de la fase 4 (ADR 0007): consolidacion mecanica del gradiente estricto.
  `maintain` archiva `dialog` fuera de ventana y promociona `episodic` ->
  `semantic` de forma literal (umbrales de recencia y merito), con lineage y sin
  borrado, via un ejecutor de `memory.consolidation` que la capa ejerce hoy
  (dogfooding) y que conscience reusara. Sintesis multi-item con modelo diferida
  con nombre. `docs/handoff/fase_4_brief.md` para el codificador. Impacto: ninguno.

### Corregido
- Hallazgos H1/H2/H3 del e2e de Fase 3: prompt y parser de extraccion
  resistentes a valores copiados, fences y texto colgante; PostgreSQL de pytest
  aislado en `<dbname>_test`; e ID del modelo de extraccion documentado y
  mostrado desde `model.list` cuando el core local responde. Sin cambios en el
  contrato publico; impacto de version: ninguno.

### Anadido
- Vertical minimo de memoria de la Fase 3: configuracion
  `IANEST_EXTENDED_*`, clientes tipados para `prompt.run` y embeddings de
  Ollama, recall compuesto con presupuesto, write-back destilado con
  dedup-refuerzo, telemetria JSONL, CLI `ianest_extended.chat`, extension
  idempotente del instalador, reconciliacion sin borrado de la dimension
  vectorial configurada y pruebas con stub HTTP local/FakeEmbedder. Los casos
  de aceptacion PostgreSQL quedan automatizados con skip explicito cuando no
  hay DB. Sin contrato publico cortado; impacto de version: ninguno.
- Diseno de la fase 3 reconciliado: `docs/POLITICA_WRITEBACK.md` (dialog crudo
  por diseno, episodic destilado con confianza y dedup-refuerzo, menciones sin
  resolver, composicion del recall con numeros de arranque) y ADR 0006 (modelos
  de apoyo: embeddings `bge-m3` 1024d y extraccion `qwen2.5:7b`, ambos
  configurables por instalacion via instalador; mitigaciones de sesgo).
  `docs/handoff/fase_3_brief.md` para el codificador. Impacto: ninguno.
- Validacion de laboratorio de la fase 2 (openSUSE Tumbleweed, docker real):
  `install.sh` ejecutado dos veces (idempotente), pytest 16/16 sin skips contra
  postgres+pgvector (criterios A1-A5 del brief); DB solo en loopback. El
  postgres de la cantera deprecada (`ia_nest_postgres`) queda al margen: esta
  capa usa su propio contenedor.
- Instalador de desarrollo `install.sh`, idempotente y orientado primero a
  openSUSE: seleccion Docker/Podman, PostgreSQL+pgvector con espera de salud,
  `.venv` Python 3.13, instalacion editable y pytest; incluye modos
  `--assume-yes`, `--skip-db` y `--skip-tests`, documentacion de uso y handoff
  de Fase 2b. Sin cambios en el contrato publico; impacto de version: ninguno.
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
