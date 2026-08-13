# Forma del enriquecimiento (Fase 1)

Estado: borrador endurecible (NO congelado)
Version: 0.1 - 2026-07-18

Este documento fija la FORMA en que esta capa envuelve al core, no un contrato
congelado. El vertical de la Fase 3 la endurece; el contrato publico SemVer se
corta en la Fase 7. Motivo: core ADR 0035, una costura sin consumidor real se
pudre; se congela cuando un consumidor la haya ejercido.

## El flujo

    1. recuperar   memoria / RAG / web, segun la identidad del request
    2. enriquecer  armar el prompt con lo recuperado, dentro del presupuesto
    3. ejecutar    prompt.run / task.run del core (core no conoce esta capa)
    4. write-back  persistir lo que corresponda de la respuesta (con politica)

El core recibe un prompt ya enriquecido y responde. La identidad de segmentacion
del core es la clave con la que esta capa indexa (via 2, core ADR 0031/0035).

## Arquitectura de la capa (via 2, servicio + pieles finas)

Extended ENVUELVE al core; el core NO llama a extended ni sabe que existe. El
"enganche" es al reves: el servicio de extended llama a la REST del core
(`prompt.run`, `domain.route`) - la unica costura de RED, porque el core es otro
desplegable. Para core puro, el cliente llama al core directamente (o al servicio
con `enrich=False`, passthrough).

Dentro de la capa: la logica vive en UN servicio (`MemoryEnricher`); CLI, REST y
MCP son pieles finas que lo invocan, sin logica divergente (misma disciplina que
el core, `CORE_CONTRACT`). Ni el CLI llama a la API ni al reves: ambos llaman al
servicio en proceso. El comportamiento se controla por parametros del servicio
(ver "superficie de parametros", `docs/PLAN.md` Fase 7).

## Decision 1: mapeo identidad -> clave de memoria

Campos de identidad del core: `user_id`, `service`, `session_id`, `domain_tag`,
`namespace`. Su papel en esta capa:

| Campo | Papel |
|---|---|
| `user_id` | columna vertebral de la clave de los tipos experienciales; los delegados de scope global o de entidad no lo llevan (ver roster) |
| `namespace` | parte de la clave (salvo `dialog`, turnos crudos sin namespace); una unica derivacion para lectura y escritura (Leccion 3) |
| `session_id` | entra en la clave SOLO para tipos con scope de sesion (decision por tipo, Fase 2) |
| `service` | PROCEDENCIA (metadato), no clave: segmentar por service fragmentaria la continuidad de la entidad, que el core advierte evitar |
| `domain_tag` | FACETA de lectura (recuperar lo coherente con el dominio), no clave dura |

Existe una identidad local configurada por defecto (core `CORE_CONTRACT.md`): en
uso local no hay que pasar identidad a mano ni se fragmenta la continuidad.

## Decision 2: composicion y presupuesto

Memoria (varios tipos), RAG y datos web compiten por un prompt FINITO (core
ADR 0008). Principios:

1. Recuperar no es volcar: se selecciona top-k RELEVANTE dentro del presupuesto.
   El ranking de relevancia de cada tipo vive en su declaracion (ADR 0002); la
   composicion agrega entre tipos y fuentes dentro del presupuesto total.
2. Anti-colision de dominios: dominios incompatibles no se enriquecen entre si
   por defecto (leccion de la cantera `ia_nest`: `chat.salud` no alimenta
   `linux.ops`). Se apoya en `domain_tag` como faceta.
3. Precedencia y reparto del presupuesto entre fuentes: principio fijado, cifras
   y orden concretos se reconcilian al existir cada fuente (Fase 3 memoria,
   Fase 5 RAG, Fase 6 web). Los numeros de arranque de la memoria estan en
   `docs/POLITICA_WRITEBACK.md` (composicion del recall).

## Que NO se fija aqui (endurecimiento posterior)

- Los nombres de las capacidades (`memory.recall`, `memory.write_back`, ...) son
  provisionales; se fijan en la Fase 7.
- El reparto numerico del presupuesto y el orden de fuentes: Fases 3/5/6.
- El roster de tipos de memoria y el modelo de relevancia concreto: Fase 2.

## Criterio de salida

Forma escrita y reconciliada, con las dos decisiones duras fijadas y el resto
marcado explicitamente como no congelado.
