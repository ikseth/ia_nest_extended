# Handoff de implementacion: fase 2 (memoria - registro y clases de tipos)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus/Fable), rol disenador.
Verificacion: Opus. Reconciliacion: usuario.
Base: `main` (solo docs; este es el primer codigo del repo).

Lee antes, en este orden: `AGENTS.md` (orden de lectura completo), ADR 0002,
0003, 0004, 0005 y `docs/ROSTER_MEMORIA.md`. Este brief no repite la doctrina;
la instancia. Ante ambiguedad o contradiccion entre docs: PARA y pregunta, no
corrijas por inferencia.

## Objetivo

El sustrato de memoria: registro de tipos declarados con validacion, almacen de
engramas sobre postgres+pgvector detras de un port, autoridad de escritura por
principal, y recuperacion por ranking multi-espacio. Sin integracion con el core
todavia (eso es fase 3).

## Dentro de fase 2

1. **Esqueleto del paquete**: layout src (`src/ianest_extended/`), `pyproject.toml`
   (PEP 621, `pip install -e .`), pytest en `tests/`. Python 3.13, venv+pip, sin
   linter/formatter (espejo de core ADR 0012).

2. **Esquema postgres** (migracion SQL versionada en `db/migrations/`):
   - `memory_types`: `name` (pk), `class` (`strict|delegated`),
     `writer_principal` (`extended|conscience`), `retrieval_mode`
     (`ranked|always_inject|profile_lookup`), `scope`
     (`session|user|entity|global`), `namespaces` (text[]), `w_recency`,
     `w_similarity`, `w_stability`, `w_score` (numeric; null si no ranked),
     `half_life_seconds` (null = sin decaimiento), `status`, `version`,
     `created_at`.
   - `engrams`: `id` (uuid), `type_name` (fk), `user_id`, `session_id` (null
     salvo scope session), `namespace` (null solo para `dialog`), `content`,
     `embedding` (vector(D)), `score` (0..1), `stability` (int, refuerzos),
     `service` (procedencia, metadato), `domain_tag`, `entity_refs` (uuid[]),
     `unresolved_mentions` (text[]), `status` (`active|archived|superseded`),
     `archived_at`, `archived_reason`, `source_trace_id`, `version`,
     `created_at`, `last_reinforced_at`.
   - `entities`: `id` (uuid), `kind`, `name`, `aliases` (text[]), `profile`
     (jsonb), `status`, `version`, timestamps. Nace vacia (delegada).
   - `memory_links`: `id`, `source_kind`, `source_id`, `target_engram_id`,
     `link_kind` (`evidence|consolidated_from`), `created_at`.
   - La dimension D del vector es parametro de la migracion (la fija config;
     el modelo real de embeddings se decide en fase 3).
   - Sin DELETE en flujo normal: el ciclo de vida es por `status` (ADR 0002).

3. **Ports y adaptadores**:
   - `MemoryStore` (port) + `PostgresMemoryStore` (adaptador de referencia).
   - `Embedder` (port) + `FakeEmbedder` determinista (hash del texto -> vector
     normalizado de dimension configurable; mismo texto, mismo vector). El
     adaptador real (Ollama) es fase 3.

4. **Registro y validacion** (`memory_type.validate`, espejo conceptual del
   `config.validate` del core). Reglas, todas con error tipado propio:
   - V1: no se admite una declaracion coincidente con otra en TODOS los ejes
     (modo, dueno, scope, namespaces) - aliasing (ADR 0005).
   - V2: dos tipos `ranked` no pueden tener identico vector de pesos e identica
     `half_life` con el mismo scope (Leccion 1, ADR 0003).
   - V3: al escribir, el `namespace` del engrama debe estar en los permitidos
     del tipo; la derivacion de clave es UNA funcion compartida por lectura y
     escritura (Leccion 3).
   - V4: coherencia de scope: `session` exige `session_id`; `user` exige
     `user_id` y prohibe `session_id` en la clave; etc. (Leccion 2).

5. **Autoridad de escritura**: toda escritura lleva `principal`; si no coincide
   con `writer_principal` del tipo, rechazo con error tipado (ADR 0002). El
   principal es un parametro del contrato: `conscience` es valido aunque la capa
   no exista aun.

6. **Recuperacion** (`recall`): para tipos `ranked`,
   `ranking = wR*R + wS*S + wE*E + wC*C` con `R = 0.5^(edad/half_life)`,
   `S = 1 - distancia_coseno`, `E = min(stability,10)/10`, `C = score`
   (normalizaciones de arranque, configurables). Gates previos al ranking:
   scope/identidad, `status = active`, `domain_tag` (si se pasa), `entity_ref`
   (si se pasa). Devuelve top-k. `always_inject` devuelve todo lo activo del
   tipo; `profile_lookup` busca por `entity_id`. En una sola query SQL cuando
   sea razonable.

7. **Declaraciones semilla**: las filas de `docs/ROSTER_MEMORIA.md` (3 estrictas
   con los numeros del ADR 0003, 4 delegadas) como datos iniciales de la
   migracion o bootstrap del registro.

8. **Entorno de desarrollo**: `docker-compose.dev.yml` con imagen
   `pgvector/pgvector` para el postgres local de dev/tests. Tests que requieren
   DB se saltan con aviso si no esta disponible (patron skipped del core).

## Blanco de aceptacion (criterios falsables del PLAN, fase 2)

- A1 continuidad: engrama `episodic` (ns `facts`) escrito bajo user u1 en sesion
  A se recupera con identidad (u1, sesion B); los engramas `dialog` de la sesion
  A NO aparecen. Prueba L1+L2+L3 a la vez.
- A2 aislamiento: `write` con principal `extended` sobre un tipo delegado ->
  error tipado; la misma escritura con principal `conscience` -> aceptada.
- A3 validacion: declaracion que viola V1 o V2 -> rechazada con su error.
- A4 tiers distintos: mismo conjunto de engramas, ranking con los pesos de
  `dialog` vs `semantic` -> ordenaciones distintas (falsa la Leccion 1 si
  salieran iguales).
- A5 sin borrado: `archive` cambia `status` y conserva la fila; no hay DELETE.
- `pytest` en verde (con DB dev levantada) y en verde-con-skips sin DB.

## Fuera de fase 2 (NO implementar)

- Integracion con el core (`prompt.run`, write-back, composicion/presupuesto,
  telemetria propia): fase 3.
- Consolidacion/promocion entre tiers y evento `memory.consolidation`: fase 4.
- Adaptador real de embeddings (Ollama), eleccion de modelo y dimension: fase 3.
- Etiquetado automatico de `entity_refs` (extraccion de menciones): fase 3
  (write-back); aqui solo la columna y el gate.
- Grafo de asociacion entre entidades y asociacion temporal: diferidas
  (ADR 0004/0005).
- CLI/REST/MCP y contrato publico: fase 7.

## Restricciones y convenciones

- Identificadores y claves en ingles snake_case (core ADR 0016); prosa y
  comentarios en espanol ASCII puro (sin tildes ni enes con virgulilla).
- Errores tipados propios (espejo del espiritu de core ADR 0020), no strings.
- Repo PUBLICO: nada interno versionado; endpoints/credenciales por env var
  (`.env.example` si hace falta). NO conectes al laboratorio: todo local.
- No cortes tags ni toques version; anota tu entrada en `CHANGELOG.md` bajo
  "No publicado" (impacto: ninguno, sin contrato publico).
- No modifiques los docs de diseno; si encuentras una inconsistencia, senalala
  en la nota de entrega.

## Entrega y handoff de vuelta

Rama nueva desde `main` (p.ej. `fase-2-memoria-registro`), tests en verde, y una
nota breve de decisiones tomadas y dudas. Opus verifica contra el blanco de
aceptacion (A1-A5) con la DB dev; el usuario reconcilia e integra.
