# Politica de write-back (Fase 3)

Estado: reconciliado
Version: 0.2 - 2026-08-22

Entregable de la Fase 3 del PLAN: que se persiste tras cada respuesta del core,
donde, y con que filtros. Principio rector: persistir en bruto envenena la
memoria; el crudo solo vive donde el diseno lo declara crudo.

## Por tier

| Tier | Que se escribe | Regla |
|---|---|---|
| `dialog` | los dos turnos (prompt del usuario y respuesta), tal cual | siempre; es crudo POR DISENO (scope sesion, H=4h) |
| `episodic` | items destilados, no crudo | extraccion estructurada (abajo); solo `confidence >= 0.7` |
| `semantic` | nada | solo consolidacion (fase 4) |
| delegadas | nada | autoridad de escritura de conscience (ADR 0002) |

## Procedencia: `stated_by` (ADR 0013)

Todo engrama registra QUIEN dijo lo que guarda, en su campo `stated_by`:
`user`, `model` o `unknown`. El nombre NO es `provenance` a proposito: ese
identificador ya designa otra cosa en el contrato de esta capa (el origen de una
entrada del catalogo: `own`, `overridden`, `forwarded`).
No es cosmetica de traza; es lo que materializa la frontera de confianza de la
enmienda del ADR 0007 -el write-back produce candidatos, no verdades- y lo que
permite que una correccion del interlocutor retire lo que el modelo afirmo.

- En `dialog` es directa: el prompt es del usuario, la respuesta del modelo.
- En `episodic` la fija el CODIGO segun la lista en que vino el item, nunca el
  modelo. Sin anclaje lexico con el bloque atribuido, el item cae a `unknown`.
- `unknown` no se rellena por conveniencia (mismo criterio que `source_trace_id`
  en CR-0005).
- La procedencia viaja al contexto inyectado: `(fuente: usuario)`,
  `(fuente: modelo, sin verificar)`, `(fuente: no registrada)`.

## Extraccion estructurada

Segunda llamada a `prompt.run` (modelo de extraccion, ADR 0006) con salida JSON:
dos listas, `from_user` y `from_assistant`, de items
`{namespace: facts|preferences|tasks, content, confidence, mentions[]}`.

- Anclaje literal: el prompt de extraccion exige items fundados en lo dicho,
  no interpretaciones del modelo (mitigacion de sesgo, ADR 0006).
- Anti-ruido: smalltalk produce cero items; salida JSON invalida se descarta y
  se registra en telemetria (no se escribe nada).
- Formato antiguo: una sola lista `items` se sigue aceptando, y sus items
  quedan en `unknown`.
- Cada item escrito conserva `source_trace_id` (el request del core que lo
  origino): auditable.

## Dedup con refuerzo, y supersede por correccion

Tres bandas de similitud contra los engramas del mismo `user_id`+`namespace`:

| Banda | Que significa | Que se hace |
|---|---|---|
| `>= dedup_threshold` (0.92) | es el MISMO item | se REFUERZA el existente (`stability + 1`, `last_reinforced_at`) |
| `[conflict_threshold, dedup_threshold)` (0.75-0.92) | habla de lo mismo y dice otra cosa | si el nuevo es del `user` y el viejo del `model`, el viejo pasa a `superseded` |
| `< conflict_threshold` | habla de otro asunto | nada |

La senal E del ranking (ADR 0003) se alimenta del refuerzo. El supersede deja
lineage en `memory_links` (`superseded_by`) y no borra: el engrama retirado
sigue siendo direccionable (ADR 0002).

Lo que la banda del medio NO hace: decidir que es verdad. Aplica una precedencia
por autoridad de la fuente -entre dos candidatos, manda el interlocutor- que es
mecanismo y no juicio segun el test de frontera del ADR 0007.

## Menciones de entidades

Las menciones extraidas van a `unresolved_mentions` del engrama. Solo se
etiqueta `entity_refs` con matches inequivocos contra el registro de entidades
(hoy vacio); resolver ambiguedades es juicio del dueno (ADR 0004).

## Retencion

Sin borrado fisico (ADR 0002). La salida de ventana caliente de `dialog` y la
promocion episodica -> semantica son de la fase 4 (consolidacion); esta politica
no archiva nada por si misma.

## Composicion del recall (numeros de arranque, configurables)

Presupuesto ~1500 tokens; k = 6 `dialog` / 4 `episodic` / 3 `semantic`; orden:
delegadas siempre-inyectadas -> `semantic` -> `episodic` -> `dialog` pegado al
prompt; recorte del peor-rankeado primero. Afinado en laboratorio (decision del
usuario en reconciliacion: el lab es el banco de finetuning de estos numeros).
