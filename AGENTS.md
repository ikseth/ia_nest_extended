# Instrucciones para agentes de IA en ia_nest_extended

Antes de proponer o valorar cualquier cambio de diseno, lee en este orden:

1. `IA_NEST_EXTENDED_CONTEXT.md`
2. `docs/ALCANCE.md`
3. `docs/DEPENDENCIAS.md`
4. `docs/PLAN.md`
5. ADRs en `docs/decision_records/`

Contexto del core (repo `ia_nest_core`): esta capa DEPENDE de sus contratos
publicos (`CORE_CONTRACT.md`) y de la doctrina del ente (`docs/FRONTERAS.md`,
core ADR 0031-0037). No dupliques ni modifiques el core desde aqui.

Versionado: SemVer; toda propuesta que toque contrato publico declara su impacto
(patch/minor/major) y actualiza `CHANGELOG.md`. No cortes tags por tu cuenta; el
tag se decide en la reconciliacion del usuario.

Multi-IA en modo ciego: si detectas una inconsistencia, senalala, no la corrijas
por inferencia (puede ser trabajo de otra IA); solo el resultado reconciliado
por el usuario se registra. Sin acentos en docs; repo publico sin datos internos.
