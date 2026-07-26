# CR-0001: checkpoint de enriquecimiento por subtarea en task.run

- id: CR-0001
- fecha: 2026-07-26
- capa origen: `ia_nest_extended`
- capa destino: `ia_nest_core`
- estado: propuesto

## Caso de uso motor

El RAG operativo (Fase 5 de extended) enriquece el prompt con conocimiento por
dominio. Para `prompt.run` (una sola llamada) el enriquecimiento upfront en la
capa (via 2) basta. Para `task.run` (descomposicion multi-dominio, core ADR 0036)
NO basta:

- Enriquecer upfront obliga a meter el conocimiento de TODOS los dominios
  candidatos en el contexto de TODAS las subtareas. Con el truncado por tokens
  real observado en el laboratorio, no cabe.
- Lo eficiente y preciso es que cada subtarea reciba solo el conocimiento de SU
  dominio. Eso solo puede ocurrir en el punto donde se arma el prompt de cada
  subtarea, que esta DENTRO del bucle de orquestacion del core.

## Que se pide

Un punto de enriquecimiento por subtarea en `task.run`: una costura donde una
capa externa (extended) pueda inyectar contexto especifico del dominio de cada
subtarea ANTES de ejecutar su modelo. El core no implementa RAG ni memoria; solo
expone donde la capa enriquece (via 2 preservada: el core sigue sin saber hacer
RAG).

## Forma sugerida (no vinculante)

Un checkpoint hermano de los observables/vetables del core ADR 0034, situado
entre ROUTE y la ejecucion de cada subtarea: `subtask_enrich`, que recibe
`(subtask_prompt, domain, identity)` y admite de vuelta un bloque de contexto
opcional que se antepone al prompt de la subtarea. Opt-in: sin proveedor
registrado, no tiene efecto (preserva el determinismo y no rompe a quien no lo
use).

## Impacto

- Core: adicion compatible -> MINOR.
- Extended: bumpearia su dependencia (`DEPENDENCIAS.md`) a esa version del core
  para el RAG per-subtarea; el RAG upfront de Fase 5 no lo necesita.

## Alternativas consideradas

- RAG upfront multi-dominio: no cabe en presupuesto de tokens (motivo del CR).
- RAG como `tool_contract` que el core invoca: reversion de core ADR 0031 (RAG es
  enriquecimiento, NO herramienta). Descartada.
- RAG dentro del core: viola "No capacidades: RAG" del `CORE_CONTRACT`.

## Tension doctrinal (honesta)

Este checkpoint reabre, en parte, el patron de puerto que el core ADR 0035
retiro al eliminar `MemoryPort`. PERO el motivo de aquella retirada -"una costura
sin consumidor real se pudre"- ya no aplica: aqui HAY consumidor real (el RAG de
extended) que la ejerceria desde el dia uno. La decision es del core: si el
enriquecimiento por subtarea justifica una costura supervisada (hermana de los
checkpoints de ADR 0034) sobre el contrato de `task.run` (ADR 0036), o si prefiere
que el RAG en `task.run` quede upfront/grueso. Extended propone; el core dispone.
