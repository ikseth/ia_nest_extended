# IA_NEST Extended - Contexto

Estado: semilla
Version: 0.0 - 2026-07-17

## Que es

`ia_nest_extended` es la capa de ENRIQUECIMIENTO de contexto del ente IA_NEST:
memoria (continuidad de conversacion y de comportamiento), RAG (conocimiento
acotado) y datos web (informacion actual). Es "la memoria/conocimiento" del
ente en el mapa de repos del core.

## Principio: via 2 (enriquecimiento en la capa)

El enriquecimiento ocurre AQUI, encima del core, no dentro. Flujo:

1. recuperar (memoria / RAG / web) segun la identidad del request,
2. armar el prompt enriquecido,
3. llamar al core (`prompt.run` / `task.run`),
4. write-back (persistir lo que corresponda de la respuesta).

El core NO conoce esta capa: recibe un prompt ya enriquecido y responde. La
identidad de segmentacion del core (`user_id`, `session_id`, `namespace`, ...)
es la CLAVE con la que esta capa indexa su memoria (core ADR 0031/0035;
`MemoryPort` fue retirado del core).

## Relacion con el ente

- Depende del core (`ia_nest_core >=0.2 <0.3`, ver `docs/DEPENDENCIAS.md`).
- Es dependencia de conscience (memoria de comportamiento) y de la GUI.
- No absorbe logica del core; no actua sobre sistemas externos (eso es
  `tool_contracts`/`external_*`, no enriquecimiento).

## Disciplina (heredada del core)

Contratos pequenos y versionados (SemVer, core ADR 0030/0032); documentos
pequenos y normativos; ADRs para decisiones estructurales; modo ciego multi-IA
con reconciliacion del usuario; sin acentos en docs; repo publico sin datos
internos.
