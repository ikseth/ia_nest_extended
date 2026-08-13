# Decision 0007: mecanismo de consolidacion (Fase 4)

Fecha: 2026-07-26

## Decision

La consolidacion de la fase 4 es MECANICA y opera solo sobre los tiers
estrictos experienciales. No construye contenido de conscience: las delegadas
(`identity`, `principles`, `entities`, `safety`) siguen declaradas y vacias; sus
memorias complejas las definira conscience SOBRE esta arquitectura, dentro de
los railes del registro.

Comando `maintain` (manual o cron; timer systemd al desplegar, espejo core
ADR 0026):

- Archivado de `dialog` fuera de ventana caliente: recencia bajo umbral ->
  `status = archived` (jamas DELETE; "TTL es salida de ventana, no eliminacion").
- Promocion `episodic` -> `semantic` LITERAL: candidatos con `R < 0.1` Y merito
  acumulado (`stability >= 3` O `score >= 0.8`). El engrama se promueve tal cual,
  las fuentes se archivan y el lineage se registra en `memory_links`
  (`consolidated_from`). Numeros de arranque configurables (banco del lab).

Ejecutor de `memory.consolidation` como UNICO camino de consolidacion
(dogfooding): `maintain` no tiene camino privado; emite eventos tipados
(trigger, `source_ids`, `target_type`, contenido) con principal `extended` y
trigger `decay`, y los ejecuta el mismo. La ejecucion respeta la autoridad de
escritura (ADR 0002): escribe el destino solo si el emisor es dueno del
`target_type`, y hace las transiciones de estado sobre las estrictas el propio
extended. Cuando conscience exista sera OTRO emisor -con sus triggers de juicio
y destinos delegados- sobre una costura ya rodada.

Sintesis de cluster (compresion multi-item con modelo) DIFERIDA con nombre: se
construye cuando la acumulacion real lo pida, o cuando conscience exista y se
decida con datos si es mecanica (extended) o juicio (conscience).

Test de frontera mecanismo/juicio: no lo define USAR un modelo (el write-back de
fase 3 ya usa uno, mecanicamente); lo define QUE evalua la regla. Similitud y
umbrales = mecanismo; merito, significado o etica = juicio.

## Motivo

- Frontera sustrato/juicio (ADR 0002, core ADR 0034): extended consolida su
  gradiente experiencial; conscience definira sus memorias complejas encima.
- El dogfooding del ejecutor evita la costura muerta (core ADR 0035): la
  promocion propia lo ejerce hoy; conscience se sumara como otro emisor.
- Promocion literal, no sintesis: los engramas episodicos ya son destilados de
  una linea (la compresion gruesa ocurrio en la extraccion de fase 3); la
  sintesis solo aporta con acumulacion de muchos episodicos relacionados, que
  aun no existe. No se optimiza un problema que no tenemos.

## Consecuencia

- Se anaden `maintain`, el ejecutor de eventos y su telemetria
  (`memory.maintain`, `memory.consolidation`).
- `semantic` deja de estar vacio: se puebla por promocion, con lineage.
- La sintesis de cluster queda como evolucion registrada del mecanismo.
- Impacto de version: ninguno (sin contrato publico cortado; Fase 7).

## Enmienda (2026-08-13): conscience ANADE, no sustituye; frontera de confianza

Reconciliado que conscience procesa el hilo para crear experiencias, conceptos y
valores. Resolucion (opcion A): conscience ANADE una capa reflexiva ENCIMA de la
mecanica de extended, no la sustituye. Extended conserva su funcion propia
(`dialog` + `episodic` + consolidacion literal a `semantic`), que le permite
servir SOLA (el e2e de Granada recupera cross-sesion memoria que escribio el
propio extended) y evita que F3/F4 sean codigo muerto (dogfooding, ADR 0002). La
sintesis de cluster diferida encaja como trabajo de conscience (juicio).

Frontera de confianza (cortafuegos de inyeccion): el write-back mecanico de
extended produce CANDIDATOS (operativa, no confiable); la promocion a memoria
durable-CONFIABLE que influye entre contextos es escritura supervisada, exclusiva
del guardian (conscience; operador en dev). Mismo motivo candidato->confiable que
`unresolved_mentions`->`entity_refs` y `source`/`confirmed` del conocimiento. La
inyeccion puede llenar el pozo de candidatos, pero no alcanza lo confiable sin el
guardian. Endurecido a nivel de recurso en ADR 0010 (least-privilege).
