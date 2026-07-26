# Handoff de implementacion: fase 4 (consolidacion mecanica)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus/Fable), rol disenador.
Verificacion: Opus (e2e final en laboratorio).
Base: `main` con fases 2-3 integradas (PR #1, #2).

Lee antes: `AGENTS.md` (orden completo), ADR 0007, ADR 0002, ADR 0003.
Ante ambiguedad: PARA y pregunta.

## Objetivo

Consolidacion mecanica del gradiente estricto via un ejecutor de eventos que la
propia capa ejerce hoy (dogfooding) y que conscience reusara. Sin sintesis con
modelo (diferida). El core no se toca.

## Dentro de fase 4

1. **`ConsolidationEvent`** (tipo): `trigger` (`decay|manual|<futuros>`),
   `principal`, `source_ids` (uuid[]), `target_type` (str|null), `content`
   (str|null), `target_namespace` (str|null), `reason`.

2. **Ejecutor** en el store/servicio, UNICO camino de consolidacion:
   - Comprueba autoridad: solo escribe `target_type` si `principal` es su
     `writer_principal` (ADR 0002). Rechazo tipado si no.
   - Si hay `target_type`+`content`: crea el engrama destino (embebido si es
     ranked) y enlaza cada `source_id` con `link_kind='consolidated_from'`.
   - Archiva cada `source_id` (`status='archived'`, `archived_reason`), sin
     DELETE. Las transiciones sobre estrictas las hace extended aunque el emisor
     sea otro (conscience pide, extended actua).
   - Emite telemetria `memory.consolidation`.

3. **`maintain`** (`python -m ianest_extended.maintain`, idempotente, con
   `--dry-run`):
   - Archiva `dialog` con recencia < umbral de ventana (config
     `DIALOG_HOT_WINDOW` o derivado de su half_life; propone y documenta).
   - Selecciona candidatos `episodic` con `R < 0.1` (usa half_life del tipo) Y
     (`stability >= PROMOTE_MIN_STABILITY` O `score >= PROMOTE_MIN_SCORE`);
     defaults 3 y 0.8, configurables.
   - Por cada candidato emite un `ConsolidationEvent` (principal `extended`,
     trigger `decay`, `target_type='semantic'`, `content` = contenido del
     episodico, `source_ids=[ese]`) y lo pasa por el ejecutor: promocion
     LITERAL. NO fusiona varios (sintesis diferida, ADR 0007).
   - Emite telemetria `memory.maintain` (resumen: dialog archivados, episodicos
     promovidos, candidatos vistos).

4. **Config**: `DIALOG_HOT_WINDOW`, `PROMOTE_MIN_STABILITY`, `PROMOTE_MIN_SCORE`,
   `PROMOTE_RECENCY_MAX` (0.1) con defaults; en `.env.example`.

5. **Tests** (patron de fase 2/3: DB `<dbname>_test` propia, skip sin DB):
   - Promocion: un `episodic` con edad alta (fija `created_at`/`last_reinforced_at`
     hacia atras) y stability>=3 -> tras `maintain` existe un `semantic` con su
     contenido, la fuente queda `archived`, hay `memory_links.consolidated_from`,
     y NINGUNA fila se borro (cuenta total no decrece).
   - No candidato: un `episodic` reciente o sin merito NO se promociona.
   - Archivado dialog: `dialog` viejo -> `archived`; reciente -> `active`.
   - Autoridad via ejecutor: `ConsolidationEvent` con `target_type` delegado y
     principal `extended` -> rechazo tipado; con principal `conscience` ->
     aceptado (crea el engrama delegado y archiva/enlaza fuentes). Esto ejerce
     la costura que conscience usara.
   - `--dry-run` no muta nada (cuentas/estados iguales antes y despues).

## Fuera de fase 4 (NO implementar)

- Sintesis de cluster con modelo (diferida, ADR 0007).
- Construir contenido de conscience o resolucion de entidades.
- Timer systemd / despliegue (llega con el despliegue).
- RAG, web, contrato publico (fases 5/6/7). Cambios en el core.

## Restricciones

Sin comandos git (sandbox); commits del disenador. ASCII en prosa;
identificadores en ingles; errores tipados; repo publico sin datos internos;
sin hosts remotos (tests con DB local `_test`). No conectes a Ollama ni core
reales: `maintain` no necesita modelo (promocion literal).

## Blanco de aceptacion

- pytest en verde con DB local (skips sin DB); los cinco casos de arriba
  pasando.
- `./install.sh --skip-db --assume-yes` sigue verde e idempotente.
- `bash -n install.sh` y ASCII limpios.

## Entrega

Ficheros en la rama activa; nota en `docs/handoff/fase_4_entrega.md`
(decisiones, dudas, inconsistencias, estado de pytest, entrada de CHANGELOG bajo
No publicado).
