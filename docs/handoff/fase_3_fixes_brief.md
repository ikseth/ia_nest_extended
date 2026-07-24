# Handoff de correcciones: fase 3 (hallazgos del e2e de laboratorio)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus/Fable), rol disenador/verificador.
Base: rama `fase-3-vertical-minimo` (commit c1099a5). El vertical funciona
(27/27 en lab con DB) pero el e2e real contra core+qwen fallo la continuidad.
Evidencia de cada hallazgo abajo; corrige exactamente esto, nada mas.

## H1: prompt de extraccion — sesgo de ejemplo (CRITICO)

Salida real de qwen_tech ante "Mi color favorito es el verde y trabajo con
openSUSE":

    {"items":[{"namespace":"facts|preferences","content":"mi color favorito es
    el verde","confidence":0.0,"mentions":["verde"]}, ...]}```

Tres defectos inducidos por `_extraction_prompt`:
1. `confidence: 0.0` copiado literal del ejemplo de forma -> todo se descarta
   por umbral.
2. `namespace: "facts|preferences"` copiado del enum -> rechazado por
   `_validate_item`.
3. Fence markdown de cierre pegado al JSON.

Correccion:
- Reescribir el prompt de extraccion: exigir UN namespace exacto de
  `facts`/`preferences`/`tasks` por item; `confidence` como certeza real 0..1;
  incluir UN ejemplo realista completo (p.ej. confidence 0.9) y un ejemplo de
  smalltalk con `{"items":[]}`; prohibir fences y texto fuera del JSON.
  Mantener el anclaje literal y el resto de la politica.
- Endurecer `_parse_extraction`: quitar fences markdown si existen y extraer el
  primer objeto JSON valido de la respuesta (tolerante a texto colgante),
  manteniendo el descarte trazado si aun asi no parsea.
- Test unitario nuevo con estas tres salidas reales de qwen como casos.

## H2: aislamiento de la DB de tests (CRITICO)

Los tests de aceptacion corren contra la misma base que el runtime: las
fixtures de delegadas ("soy una entidad en evolucion", "principio uno <uuid>")
quedaron activas y, al ser de inyeccion permanente, contaminan TODAS las
conversaciones del chat (verificado con --show-context en el lab).

Correccion:
- Los tests usan una base PROPIA: el fixture de conftest deriva del DSN una DB
  `<dbname>_test` (la crea si no existe, con la extension pgvector) y ejecuta
  ahi `migrate()`. La DB de runtime (`IANEST_EXTENDED_DATABASE_DSN`) nunca es
  tocada por pytest.
- El instalador crea ambas bases en el postgres del compose (runtime y test) o
  documenta que el fixture las crea; decide y documenta.
- Los tests siguen limpiando o tolerando sus propios datos entre ejecuciones
  (idempotencia de la suite en su propia DB).

## H3: id de modelo de extraccion (documentacion)

El valor de `IANEST_EXTENDED_EXTRACTION_MODEL` es el ID DEL MODELO EN EL CORE
(precedencia ADR 0019), no el tag de Ollama. En el lab: `qwen_tech`, no
`qwen2.5:7b`. El core lo rechazo con `unknown model 'qwen2.5:7b'` (HTTP 400).

Correccion:
- Comentario en `.env.example` y en la seccion del README: el valor debe
  existir en `models[]` de la config del core de la instalacion (se consulta
  con `model.list`); el default `qwen2.5:7b` se mantiene como sugerencia, con
  la nota.
- El instalador, al preguntar el modelo de extraccion, muestra esa aclaracion
  (y si el core esta alcanzable, lista los ids disponibles via `model.list`).

## Restricciones

Las de siempre: sin git, ASCII, ingles snake_case, sin hosts remotos, errores
tipados. No toques nada fuera de estos tres hallazgos. pytest en verde
(skips sin DB). Actualiza `docs/handoff/fase_3_entrega.md` con una seccion
"Correcciones e2e" y la entrada de CHANGELOG si procede.
