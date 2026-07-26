# Instrucciones para agentes de IA en ia_nest_extended

Antes de proponer o valorar cualquier cambio de diseno, lee en este orden:

1. `IA_NEST_EXTENDED_CONTEXT.md`
2. `docs/ALCANCE.md`
3. `docs/DEPENDENCIAS.md`
4. `docs/VISION_MEMORIA.md` (el fin de la memoria y su frontera con conscience)
5. `docs/FORMA_ENRIQUECIMIENTO.md` (la forma en que la capa envuelve al core)
6. `docs/ROSTER_MEMORIA.md` (los tipos de memoria declarados)
7. `docs/POLITICA_WRITEBACK.md` (que se persiste y la composicion del recall)
8. `docs/PLAN.md`
9. ADRs en `docs/decision_records/`
10. Los CR emitidos por esta capa, en el repo de gobernanza `ia_nest_meta`
    (`docs/change_requests/from-ia_nest_extended/`; el proceso, en su README)

Contexto del core (repo `ia_nest_core`): esta capa DEPENDE de sus contratos
publicos (`CORE_CONTRACT.md`) y de la costura que el core expone a cada capa
(`docs/FRONTERAS.md`, core ADR 0031-0037). No dupliques ni modifiques el core
desde aqui.

Versionado: politica comun del ente en
`ia_nest_meta/docs/POLITICA_SEMVER.md`. Toda propuesta que toque contrato
publico declara su impacto (patch/minor/major) y actualiza `CHANGELOG.md`. No
cortes tags por tu cuenta; el tag se decide en la reconciliacion del usuario.

Pendiente de esta capa: declarar QUE cuenta como su contrato publico, requisito
de la politica para poder versionarse (`docs/DEPENDENCIAS.md`, seccion "Contrato
propio").

Doctrina transversal del ente (repo de gobernanza `ia_nest_meta`), que aplica
aqui y no se duplica en este repo:

- `docs/DOCTRINA_MULTI_IA.md`: roles, modo ciego, regla de la inconsistencia,
  regla del registro, handoff.
- `docs/CONVENCIONES_TRANSVERSALES.md`: docs en ASCII puro (sin acentos ni
  enye), identificadores en ingles snake_case, citas `<repo> ADR NNNN`, repo
  publico sin datos internos.
- `docs/REGISTRO_CAPAS.md`: quien existe en el ente, quien depende de quien y la
  regla de vinculo por SemVer. El manifiesto de esta capa
  (`docs/DEPENDENCIAS.md`) es la fuente de verdad; el registro lo refleja.

Lo esencial, para no leer dos ficheros: modo ciego; una inconsistencia se
senala, no se corrige por inferencia; solo el resultado reconciliado por el
usuario se registra; docs sin acentos.
