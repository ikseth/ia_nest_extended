# Handoff de correcciones: fase 5 (hallazgo del e2e de laboratorio)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus/Fable), rol disenador/verificador.
Base: rama `fase-5-rag-upfront` (commit `ae7ebf5`, impl de F5). Corrige EXACTO
esto; nada mas. La ingesta, la recuperacion, el gate y la anti-colision ya
funcionan en lab; el bug esta en la resolucion de dominio hacia `prompt.run`.

## H1: el dominio del RAG se reenvia a prompt.run sin validar (CRITICO)

Evidencia (lab, core v0.3): `chat --domain cocina ...` hace que `prompt.run`
reciba `domain=cocina`; el core (dominios: `general, humanidades, matematicas,
codigo, linux, razonamiento`) responde HTTP 400 y el chat casca con traceback.
`--domain linux` funciona porque `linux` SI es dominio del core.

Causa: se confunden dos nociones distintas -dominio de corpus RAG (etiqueta del
operador) y dominio de ruteo del core (config)-. Reconciliado con el usuario: han
de ALINEARSE. El dominio que gatea el RAG y rutea el modelo es un dominio VALIDO
del core (salvo `general`, agnostico).

Correccion:

- `CoreClient`: metodo `list_domains()` que llama a `domain.list` y devuelve los
  ids de dominio del core. Cachear el resultado por ejecucion (una sola llamada,
  no una por request).
- Resolucion de dominio en el flujo de enriquecimiento:
  - explicito: validar contra `list_domains()`. Si es un dominio del core -> se
    usa para gatear el RAG Y se pasa a `prompt.run` como dominio de ruteo. Si NO
    lo es -> error tipado claro (mensaje que incluya los dominios validos), SIN
    llamar a `prompt.run` con ese dominio.
  - auto-route (`domain.route`): el dominio devuelto ya es valido -> se usa para
    ambos (gate + ruteo).
  - sin dominio (o `general`): RAG segun D1 (similitud global) y `prompt.run` SIN
    dominio de ruteo, como se comportaba antes de F5.

- Tests de regresion (stub del core con `domain.list = [general, linux]`):
  - `--domain linux` -> `prompt.run` recibe `domain=linux`; el RAG se gatea a
    linux; sin 400.
  - `--domain cocina` -> error tipado; NUNCA se llama a `prompt.run` con `cocina`.
  - auto-route devuelve `linux` -> se usa para ambos.
  - sin dominio -> RAG global; `prompt.run` sin dominio.

## Fuera de este fix (es la fase nueva "dominio<->conocimiento", NO implementar)

Etiquetas de dominio N:M, auto-etiquetado en ingesta, validacion de dominio en la
INGESTA, re-etiquetado por ciclo de vida de dominios, chequeo de completitud,
corpus reales del lab. Todo eso es diseno aparte, aun sin reconciliar.

## Restricciones

Sin comandos git (sandbox); commits del disenador. ASCII en prosa;
identificadores en ingles; errores tipados; sin hosts remotos (stub del core en
tests). No toques el sustrato de memoria ni el core. pytest en verde (skips sin
DB). Actualiza `docs/handoff/fase_5_entrega.md` con una seccion "Correccion e2e"
y la entrada de CHANGELOG si procede.
