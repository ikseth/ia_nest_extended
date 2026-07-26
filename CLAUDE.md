# Instrucciones para Claude Code en ia_nest_extended

Sigue el orden de lectura y las reglas de `AGENTS.md` (compartidas con Codex).

Puntos clave de esta capa:

- Enriquecimiento EN LA CAPA (via 2): esta capa envuelve al core, no lo toca.
- Depende de `ia_nest_core >=0.2 <0.3` (manifiesto: `docs/DEPENDENCIAS.md`). La
  costura con el core vive en el repo del core (`docs/FRONTERAS.md`,
  ADR 0031-0037); el registro de capas del ente, en `ia_nest_meta`.
- SemVer y `CHANGELOG.md` para todo lo que toque contrato publico; no cortes
  tags por tu cuenta. Politica comun del ente:
  `ia_nest_meta/docs/POLITICA_SEMVER.md`.
- Sin acentos/tildes en docs (convencion deliberada, no un error a corregir).
  Repo publico: nunca commitees IPs/hosts/secretos internos.
- Doctrina transversal del ente en el repo de gobernanza `ia_nest_meta`:
  `docs/CONVENCIONES_TRANSVERSALES.md` y `docs/DOCTRINA_MULTI_IA.md`.
