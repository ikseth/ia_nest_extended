# Decision 0006: modelos de apoyo de la capa (embeddings y extraccion)

Fecha: 2026-07-24

## Decision

La capa usa dos modelos de apoyo, ambos CONFIGURABLES POR INSTALACION (el
instalador los pregunta o acepta por flag y los registra en la configuracion;
`--assume-yes` toma los recomendados):

- **Embeddings**: `bge-m3` (1024 dimensiones) como recomendado. Servido por el
  Ollama de la instalacion; adaptador via API de embeddings. La dimension del
  vector de la migracion se fija en la configuracion (1024 con el recomendado).
- **Extraccion del write-back**: `qwen2.5:7b` como recomendado, invocado a
  traves de `prompt.run` del core con modelo declarado directamente
  (precedencia core ADR 0019); configurable via la config de extended, sin
  tocar la configuracion del core.

## Motivo

- Embeddings: el ente vive en espanol; `nomic-embed-text` (el unico presente en
  el lab) es English-centric. `bge-m3` es multilingue fuerte, disponible en
  Ollama y de coste moderado (~1.2GB). Cambiar de dimension despues obliga a
  re-embeber toda la memoria: mejor decidir bien al fundar.
- Extraccion: `qwen2.5:7b` sigue bien esquemas JSON con coste moderado; ya esta
  en el lab.
- Sesgo de extraccion (pregunta del usuario en reconciliacion): riesgo bajo y
  acotado, no cero. Mitigaciones de diseno: el prompt de extraccion exige items
  anclados a lo dicho literalmente; umbral de confianza; dedup que impide
  amplificacion; `source_trace_id` en cada item (auditable); modelo
  reemplazable por configuracion. Frontera de fondo: la extraccion es mecanica
  y solo escribe tiers experienciales; las delegadas (el caracter) le son
  inalcanzables por autoridad de escritura (ADR 0002).

## Consecuencia

- El instalador (fase 2b) gana la configuracion de ambos modelos y de las URLs
  de core y Ollama; escribe la config de la instalacion. Pull de modelos solo
  bajo flag explicito y con Ollama alcanzable.
- La migracion de fase 2 se instancia con dimension 1024 en instalaciones con
  el recomendado.
- Ambas elecciones son por instalacion, no contrato: cambiarlas es operacion
  local (re-embebido aparte), impacto de version ninguno.
