# Plan de ia_nest_extended

Estado: BORRADOR (reconciliacion pendiente con el usuario)
Version: 0.0 - 2026-07-17

Misma disciplina que el core: fases con criterio de salida falsable; no se abre
una fase sin validar la anterior; diseno y prueba de aceptacion antes de
implementar. Memoria primero (la necesita conscience).

## Fase 0: Semilla (esta)

Contexto, alcance, dependencias y genesis (ADR 0001). Criterio: repo fundado y
coherente con la doctrina del core.

## Fase 1: Contrato de enriquecimiento

Definir COMO esta capa envuelve al core: flujo recuperar -> enriquecer ->
`prompt.run`/`task.run` -> write-back; su interfaz de consumo y su contrato
versionado. Criterio: contrato escrito y reconciliado.

## Fase 2: Memoria - modelo de datos

Tiers, `namespace`, scopes de lectura/escritura (3 lecciones core ADR 0011);
motor de almacenamiento. Criterio: esquema definido con las 3 lecciones
cubiertas y prueba de aceptacion.

## Fase 3: Memoria - vertical minimo

`read_context` (recuperar por identidad/tiers -> inyectar) + write-back
(persistir respuesta), envolviendo `prompt.run`. Criterio: una conversacion
mantiene continuidad end-to-end, con la identidad como clave.

## Fase 4: Memoria - consolidacion

Promocion entre tiers e hitos (milestone); base de la memoria de comportamiento
que conscience sedimentara (core ADR 0034). Criterio: consolidacion verificable.

## Fase 5: RAG

Ingesta de conocimiento acotado + recuperacion para enriquecer. Criterio:
recuperacion relevante inyectada en el prompt; sin tocar el core.

## Fase 6: Datos web

Recuperacion de informacion actual para enriquecer. Criterio: enriquecimiento
web verificable, acotado y trazable.

## Fase 7: Interfaz y contrato publico de la capa

Consolidar la interfaz de consumo (para GUI/conscience) y cortar la primera
version SemVer de extended. Criterio: contrato versionado y consumible.

## Fuera de este plan

- Cambios en el core.
- Accion sobre sistemas externos (tool_contracts / external_*).
- Personalidad/etica (conscience); regulacion tecnica (pulse); GUI (web).
