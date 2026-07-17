# Alcance de ia_nest_extended

## Dentro

- Memoria: modelo de tiers, recuperacion por identidad, write-back y
  consolidacion. Incluye la "memoria de comportamiento" que conscience
  sedimentara (core ADR 0034).
- RAG: ingesta de conocimiento acotado y recuperacion para enriquecer el prompt.
- Datos web: recuperacion de informacion actual para enriquecer el prompt.
- El contrato de enriquecimiento (como esta capa envuelve al core) y su
  interfaz de consumo, versionados.

## Fuera (anti-entropia)

- Cualquier cambio en el core (esta capa NO toca `ia_nest_core`).
- Accion sobre sistemas externos con efecto -> `tool_contracts` / `external_*`.
- Personalidad / etica / deliberacion -> conscience.
- Regulacion tecnica (limites, homeostasis) -> pulse.
- Presentacion / GUI -> `ia_nest_web`.

## Lecciones heredadas de la cantera (core ADR 0011)

La memoria debe respetar, por fallos reales de la implementacion previa:

1. Tiers realmente distintos (no aliased por leer con los mismos filtros).
2. Separar scope de lectura y de escritura.
3. Consistencia de `namespace` entre escritura y lectura.
