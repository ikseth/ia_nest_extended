# Instrucciones para Claude Code en ia_nest_extended

Sigue el orden de lectura y las reglas de `AGENTS.md` (compartidas con Codex).

Puntos clave de esta capa:

- Enriquecimiento EN LA CAPA (via 2): esta capa envuelve al core, no lo toca.
- Depende de `ia_nest_core >=0.2 <0.3`; la doctrina del ente vive en el repo del
  core (`docs/FRONTERAS.md`, ADR 0031-0037).
- SemVer y `CHANGELOG.md` para todo lo que toque contrato publico; no cortes
  tags por tu cuenta.
- Sin acentos/tildes en docs (convencion deliberada). Repo publico: nunca
  commitees IPs/hosts/secretos internos.
