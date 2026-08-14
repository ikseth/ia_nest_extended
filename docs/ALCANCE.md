# Alcance de ia_nest_extended

## Dentro

- Memoria: registro de tipos, recuperacion por identidad, write-back y el
  MECANISMO de consolidacion (ADR 0002). Extended HOSPEDA y sirve la memoria de
  comportamiento e identidad que conscience sedimentara (core ADR 0034), pero no
  la escribe: son memorias delegadas cuyo dueno de escritura es conscience.
  El fin de la memoria esta en `docs/VISION_MEMORIA.md`.
- RAG: ingesta de conocimiento acotado y recuperacion para enriquecer el prompt.
- Datos web: recuperacion de informacion actual para enriquecer el prompt.
- El contrato de enriquecimiento (como esta capa envuelve al core) y su
  interfaz de consumo, versionados.

## Fuera (anti-entropia)

- Cualquier cambio en el core (esta capa NO toca `ia_nest_core`).
- Accion sobre sistemas externos con efecto -> `tool_contracts` / `external_*`.
- Personalidad / etica / deliberacion, y el JUICIO de que merece consolidarse
  -> conscience (ADR 0002). Aqui vive el mecanismo, no el juicio.
- Regulacion tecnica (limites, homeostasis) -> pulse.
- Presentacion / GUI -> `ia_nest_web`.
- Autenticacion de los interlocutores: no es enriquecimiento. Esta capa CONSUME
  la identidad afirmada del request y la usa como clave; no la prueba. El concern
  y sus hogares candidatos -esta capa es uno de ellos- estan registrados en
  `ia_nest_meta/docs/CAPAS_FUTURAS.md`, sin decidir.

## Lecciones heredadas de la cantera (core ADR 0011)

La memoria debe respetar, por fallos reales de la implementacion previa:

1. Tiers realmente distintos (no aliased por leer con los mismos filtros).
2. Separar scope de lectura y de escritura.
3. Consistencia de `namespace` entre escritura y lectura.
