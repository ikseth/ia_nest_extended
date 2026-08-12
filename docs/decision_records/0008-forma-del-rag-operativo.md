# Decision 0008: forma del RAG operativo (Fase 5, camino upfront)

Fecha: 2026-08-12

## Decision

El RAG operativo es un subsistema HERMANO de la memoria, no un tier: solo
lectura, sin write-back, sin decaimiento, sin consolidacion, sin clave de
identidad. Enriquece el prompt con conocimiento por dominio. Reusa el motor
(`postgres + pgvector`) y el embedder (`bge-m3`, misma dimension que la memoria),
en tablas propias.

Modelo de datos:

- `rag_corpora`: catalogo (id, `name`, `domain`, `description`, `status`,
  `version`, timestamps).
- `rag_chunks`: (id, `corpus_id`, `content`, `embedding vector(D)`, `source_ref`,
  `ordinal`, `created_at`). Idempotente por (`corpus_id`, `source_ref`,
  `ordinal`).

Ingesta: comando que lee -> trocea -> embebe -> almacena. Curado por el operador;
no hay write-back ni ciclo de vida de memoria (no es autobiografico).

Recuperacion (D1): con dominio -> gate al dominio (anti-colision); sin dominio ->
similitud sobre todos los corpus. top-k dentro del presupuesto. El gate es
restriccion ADICIONAL para contextos especializados, no un interruptor: sin
dominio la similitud ya filtra relevancia.

Dominio (D2), dos vias: explicito (el caller pasa `--domain`, util para consultas
directas o servicios externos) y auto-route (extended llama a `domain.route` del
core -semantico desde v0.3, `core ADR 0043`- como PRE-paso). NO es el orquestador
interno del core consultando RAG: eso seria `task.plan` (futuro, `core ADR 0040`),
per-subtarea, fuera de esta fase.

Presupuesto (D3): duro y minimo, con conteo conservador de tokens (el lab sufre
truncado real). El RAG aporta poco: pocos chunks, cortos. Prioridad de recorte
bajo presupuesto: cae primero el RAG, luego `episodic`; NUNCA las delegadas ni el
prompt del usuario.

Alcance de esta fase: SOLO el camino upfront (`prompt.run`). El RAG per-subtarea
en `task.run` espera a `task.plan` (core v0.4). El RAG etico/filosofico de la
cantera es de conscience, no de esta capa.

## Motivo

`docs/VISION_MEMORIA.md` ya fija el RAG como hermano: comparte la primitiva de
recuperacion (similitud vectorial) pero no el modelo (curado, externo, sin
identidad, sin decaimiento). Reusar motor y embedder evita un segundo sistema y
una segunda dimension. El gate de dominio implementa la anti-colision de la
cantera (`chat.salud` no enriquece `linux.ops`). El presupuesto duro responde al
truncado real observado en laboratorio.

## Enmienda (2026-08-12): dominio del RAG = dominio del core

El dominio que gatea el RAG y el que rutea el modelo son el MISMO y deben ser un
dominio VALIDO del core (salvo `general`, agnostico). El e2e de lab mostro que
reenviar a `prompt.run` un dominio que el core no conoce (p.ej. `cocina`) da
HTTP 400. Se valida el dominio explicito contra `domain.list`; `domain.route`
devuelve dominios ya validos. El pipeline coherente es: prompt -> dominio (core)
-> rutea el modelo de ese dominio + inyecta su conocimiento.

La relacion completa dominio<->conocimiento (etiquetas N:M, auto-etiquetado en
ingesta, re-etiquetado por ciclo de vida de dominios, chequeo de completitud,
corpus reales del lab) es una FASE propia, con su diseno y ADR, aun sin
reconciliar.

## Consecuencia

- La Fase 5 implementa el sustrato RAG (tablas, ingesta, recuperacion) + la
  integracion upfront en el enriquecimiento, sin tocar las tablas de memoria.
- `domain.route` entra como contrato consumido (`docs/DEPENDENCIAS.md`, ya
  anotado).
- El per-subtarea queda diferido a `task.plan`; se retomara con trabajo de
  cliente (`task.plan` + `task.run` con plan).
- Impacto de version: ninguno (sin contrato publico cortado; se corta en Fase 7).
