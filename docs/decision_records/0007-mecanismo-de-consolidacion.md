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

## Enmienda (2026-08-22): el motivo del diferimiento caduca; se reabre la sintesis

La sintesis de cluster se difirio con este motivo, escrito arriba: "los engramas
episodicos ya son destilados de una linea (...) la sintesis solo aporta con
acumulacion de muchos episodicos relacionados, que aun no existe. No se optimiza
un problema que no tenemos."

El razonamiento era correcto para el problema que anticipaba -VOLUMEN- y el
problema que aparecio es otro: COHERENCIA. Medido el 2026-08-21 sobre una sesion
real: con **cuatro turnos y siete engramas** el contexto ya llevaba dos hechos
incompatibles del mismo asunto, y el modelo no podia sino contradecirse. No hizo
falta acumulacion ninguna.

La razon de fondo es estructural, no de tamano: **un conjunto de engramas
atomicos no puede expresar que uno reemplaza a otro**. Solo pueden coexistir. Lo
que da DIRECCION a un hilo -"el interlocutor corrigio esto, la version anterior
era erronea"- es una frase con estructura temporal, y eso es sintesis, no
acumulacion. El ADR 0013 mitiga el sintoma marcando procedencia y anotando las
versiones en conflicto, pero no lo resuelve: sigue habiendo dos items sueltos.

Se reabre, con la forma que el usuario reconcilio el 2026-08-22: **un combinado,
no una sustitucion.** Engramas conversacionales de un hilo CON referencias a los
datos, MAS una sumarizacion del hilo. El resumen da continuidad barata y con
perdida, para hilos largos; las referencias mantienen el anclaje auditable, que
un resumen disuelve (hoy cada item conserva su `source_trace_id`; un resumen de
doce, no). Suman, no se sustituyen.

Frontera: un resumen de hilo por ventana temporal, que NO decide que merece
recordarse, es MECANISMO y cabe en extended por el test de frontera de este
mismo ADR -similitud y umbrales son mecanismo; merito, significado o etica son
juicio-. Lo que sigue siendo de conscience es que el resumen ELIJA que es
importante. La asignacion a conscience que hizo la enmienda del 2026-08-13 se
matiza aqui: le corresponde la sintesis con juicio, no toda sintesis.

Riesgo declarado: resumir con el mismo modelo que alucina produce resumenes de
alucinaciones. Por eso el resumen no sustituye a los engramas anclados, y por
eso hereda de ADR 0013 la obligacion de conservar procedencia.

Pendiente: fase propia en el PLAN, con su criterio de salida falsable. Esta
enmienda registra la decision de reabrir y por que; no fija la forma.

## Enmienda (2026-09-12): recordar no es sostener un hilo

Reconciliada con el usuario el 2026-09-12, al releer la Fase 9 antes de fijar
su criterio. No cambia lo decidido: precisa POR QUE, y de ahi salen limites que
el alcance de la fase no tenia.

La enmienda anterior zanjo la propiedad apelando a que la ventana es temporal y
mecanica. Sirve, pero es un argumento sobre el MECANISMO. Hay otro mejor, y es
sobre la FUNCION: **son dos funciones distintas sobre el mismo sustrato.**

- El **historico** de lo que una conversacion o una experiencia genera, para que
  el ente tenga continuidad manana.
- El **tratamiento del hilo argumental** mientras la conversacion ocurre, para
  que el ente no se contradiga ahora.

Recordar y sostener un argumento no son la misma funcion, aunque compartan
almacen. Cuatro consecuencias:

1. **La sintesis de hilo es ESTADO DE TRABAJO, no un recuerdo.** Vive y muere
   con el hilo, y el barrido mecanico de la Fase 4 NO la promociona a
   `semantic`. Que algo de ese hilo merezca sedimentarse es juicio, y es de
   conscience. Esto acota el riesgo ya declarado: un resumen alucinado que
   llegara a `semantic` envenenaria el yo de forma duradera, que es exactamente
   lo que no puede pasar.
2. **La propiedad queda cerrada por la funcion, no solo por la ventana.**
   Sostener la coherencia de la conversacion en curso es andamiaje, y el
   andamiaje es mecanismo: extended. Elegir que de ese hilo se recuerda es
   juicio: conscience.
3. **Lo exacto no se resume.** Nombres, fechas y referentes son hechos exactos,
   y el ADR 0004 lo prohibe expresamente: nunca aproximar lo que se conoce con
   exactitud. El resumen aporta DIRECCION; los artefactos siguen anclados y
   exactos. El mecanismo que los sostiene ya existe -`entities`, ADR 0004-, hoy
   DECLARADO Y SIN IMPLEMENTAR. La Fase 9 declara esa dependencia en vez de
   reinventarla.
4. **Combinado en el ALMACEN, sustitucion en el PRESUPUESTO.** Es la lectura
   conjunta de los dos puntos que parecian tensos: el resumen y los engramas
   anclados coexisten y ambos son direccionables, y lo que se INYECTA es el
   resumen en lugar de los items que resume.

Lo que esta enmienda NO hace: fijar el criterio de salida de la Fase 9. Sigue
pendiente de una medida limpia de su brazo de control -la linea L4b de
`docs/PUERTA_LABORATORIO.md`-, porque una fase no se justifica con la medida
que confirma lo que su disenador esperaba.
