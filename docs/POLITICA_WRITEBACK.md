# Politica de write-back (Fase 3)

Estado: reconciliado
Version: 0.1 - 2026-07-24

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

## Extraccion estructurada

Segunda llamada a `prompt.run` (modelo de extraccion, ADR 0006) con salida JSON:
items `{namespace: facts|preferences|tasks, content, confidence, mentions[]}`.

- Anclaje literal: el prompt de extraccion exige items fundados en lo dicho,
  no interpretaciones del modelo (mitigacion de sesgo, ADR 0006).
- Anti-ruido: smalltalk produce cero items; salida JSON invalida se descarta y
  se registra en telemetria (no se escribe nada).
- Cada item escrito conserva `source_trace_id` (el request del core que lo
  origino): auditable.

## Dedup con refuerzo

Antes de insertar un item episodico: si existe un engrama del mismo
`user_id`+`namespace` con similitud >= 0.92 (configurable), NO se inserta: se
REFUERZA el existente (`stability + 1`, `last_reinforced_at`). La senal E del
ranking (ADR 0003) se alimenta de aqui.

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
