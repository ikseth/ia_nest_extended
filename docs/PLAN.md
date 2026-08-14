# Plan de ia_nest_extended

Estado: fases 0-4 (memoria) reconciliadas; fases 5-7 en BORRADOR
Version: 0.1 - 2026-07-18

Misma disciplina que el core: fases con criterio de salida falsable; no se abre
una fase sin validar la anterior; diseno y prueba de aceptacion antes de
implementar. Memoria primero (la necesita conscience).

El fin de la memoria y su frontera con conscience estan en
`docs/VISION_MEMORIA.md`; el mecanismo, en ADR 0002.

## Fase 0: Semilla (esta)

Contexto, alcance, dependencias y genesis (ADR 0001). Criterio: repo fundado y
coherente con la doctrina del core.

## Fase 1: Forma del enriquecimiento (borrador endurecible)

Definir la FORMA, no congelar el contrato: recuperar -> enriquecer ->
`prompt.run`/`task.run` -> write-back. Se marca explicitamente como borrador: el
vertical de Fase 3 la endurece y el contrato publico SemVer se corta en Fase 7.
Motivo: core ADR 0035, una costura sin consumidor real se pudre.

Dos decisiones duras que si se fijan aqui:

1. Mapeo identidad -> clave de memoria: que subconjunto de la identidad del core
   (`user_id`, `service`, `session_id`, `domain_tag`, `namespace`) entra en la
   clave. Reconciliado: `service` es procedencia y no fragmenta la memoria (el
   core advierte de no fragmentar la continuidad de la entidad); `domain_tag` es
   faceta de lectura, no clave dura.
2. Politica de composicion y presupuesto: memoria, RAG y datos web compiten por
   un prompt finito (core ADR 0008). Recuperar no es volcar, es seleccionar top-k
   relevante dentro del presupuesto, con regla anti-colision entre dominios
   incompatibles (leccion de la cantera `ia_nest`).

Detalle en `docs/FORMA_ENRIQUECIMIENTO.md`. Criterio: forma y ambas decisiones
escritas y reconciliadas, marcadas como no congeladas.

## Fase 2: Memoria - registro y clases de tipos (ADR 0002)

La memoria es un REGISTRO de tipos declarados (namespace, comportamiento de tier,
read-scope, write-scope, `writer_principal`). Dos clases: estrictas (dueno
extended, utiles hoy) y delegadas (dueno otra capa; `identity`/`principles`/
`entities`/`safety` de conscience, declaradas y vacias). Extended posee los invariantes
(3 lecciones core ADR 0011) como validacion del registro y fuerza la autoridad de
escritura por capacidad. Las estrictas se implementan por el mismo contrato que
usaran las delegadas (dogfooding). Motor detras de un port intercambiable, no
casado.

Decidido: modelo de relevancia y gradiente de tiers (ADR 0003), entities y modelo
multi-espacio (ADR 0004), disolucion de historic (ADR 0005). El roster esta
RECONCILIADO en `docs/ROSTER_MEMORIA.md`: la fase es implementable (esquema,
contrato de declaracion, registro y validacion).

Criterio (falsable):

1. Continuidad: un `fact` escrito en sesion A (estricta consolidada) se recupera
   en sesion B (otro `session_id`, mismo `user_id`); las entradas conversacionales
   de A no. Prueba a la vez las 3 lecciones (tier distinto, lectura/escritura
   separadas, namespace consistente).
2. Aislamiento: una escritura del camino experiencial contra un tipo delegado se
   rechaza; una declaracion que aliasaria dos tiers la rechaza `memory_type.validate`.

## Fase 3: Memoria - vertical minimo

Recuperar por identidad/tiers e inyectar (`memory.recall`, nombre provisional; NO
se reusa `read_context`, retirado del core en ADR 0035) mas write-back
(`memory.write_back`), envolviendo `prompt.run`.

Entregables:

1. Politica de write-back explicita: que se persiste, en que namespace y tier,
   dedup y retencion. Persistir respuestas en bruto envenena la memoria; el filtro
   es parte del diseno, no algo emergente.
2. Telemetria propia (CSV/JSONL, core ADR 0010/0015) emitida por esta capa: pulse
   observa la telemetria de todos (core ADR 0037) y el modo sueno de conscience
   revisa el dia sobre ella (core ADR 0034). Un vertical sin traza los deja ciegos
   respecto a extended.

Criterio: una conversacion mantiene continuidad end-to-end con la identidad como
clave; el write-back aplica su politica (no vuelca en bruto); la capa emite traza.

## Fase 4: Memoria - consolidacion (mecanismo) (ADR 0007)

Consolidacion MECANICA del gradiente estricto: `maintain` archiva `dialog` fuera
de ventana y promociona `episodic` -> `semantic` de forma LITERAL (umbrales de
recencia y merito), con lineage y sin borrado fisico. Todo pasa por el ejecutor
del evento `memory.consolidation`, que la propia capa ejerce hoy (dogfooding) y
que conscience reusara como otro emisor.

Frontera (ADR 0002/0007): el JUICIO de que merece consolidarse, y las memorias
complejas (identidad, principios, entidades), son de conscience, que las definira
SOBRE esta arquitectura; las delegadas siguen declaradas y vacias. La sintesis
con compresion multi-item queda diferida con nombre (ADR 0007).

Criterio: una promocion verificable extremo a extremo, con lineage y sin borrado
fisico; un evento de consolidacion aplicado por extended sin que su emisor escriba
memorias estrictas.

## Fase 5: RAG

CR-0001 RESUELTO (core ADR 0040, REFORMULADO): en vez de un checkpoint, la forma
adoptada es `task.plan` (devuelve el plan con el dominio de cada subtarea) +
`task.run` que acepta un `plan` enriquecido entre las dos llamadas. Impacto en el
core: minor, objetivo v0.4. NO entregado aun (no esta en el contrato ni en el
codigo del core; el lab corre v0.2.0).

Estado de los dos caminos:

- RAG upfront (`prompt.run`): DESBLOQUEADO. No depende de `task.plan`. El sustrato
  (ingesta, troceo, embedding, almacen, recuperacion por dominio) es agnostico de
  la version del core; la integracion usa el `prompt.run` estable. Se construye ya.
- RAG per-subtarea (`task.run`): espera a que el core entregue `task.plan` (v0.4)
  y al trabajo de cliente correspondiente (hoy extended solo habla `prompt.run`).

RAG no es un tier de memoria: es un subsistema hermano que comparte el mecanismo
de inyeccion y su presupuesto, no el modelo (`docs/VISION_MEMORIA.md`). Forma
reconciliada en ADR 0008: gate por dominio con similitud-en-todo sin dominio (D1);
dominio explicito o via `domain.route` semantico (D2, core ADR 0043); presupuesto
duro y minimo (D3). El camino upfront (`prompt.run`) se implementa ya
(`docs/handoff/fase_5_brief.md`); el per-subtarea (`task.run`) espera a `task.plan`
(core v0.4). Criterio: recuperacion relevante por dominio inyectada en el prompt,
dentro del presupuesto; sin tocar el core.

## Fase 5b: Conocimiento por dominio

Relacion dominio<->conocimiento: cada dominio del core (salvo `general`) puede
tener conocimiento asociado; el mismo dominio que rutea el modelo inyecta su
conocimiento; el catalogo de conocimiento se mantiene en sincronia con el del
core. Premisa: el conocimiento es externo (ops/operador), NO el yo del ente; no
lo toca conscience.

Modelo de datos reconciliado (ADR 0009): N:M dominio<->corpus a nivel de corpus,
con `source`/`confirmed` (auto-etiquetado como propuesta; confirmacion del
operador; la recuperacion gatea solo por vinculos confirmados). Pendiente de
reconciliar: el workflow (ingesta auto-asistida con `domain.route`,
`knowledge maintain` para ciclo de vida de dominios, chequeo de completitud) y la
ampliacion del corpus del lab con conocimiento real por dominio (habilita probar
el presupuesto D3 bajo carga). Criterio: recuperacion por dominio con vinculos
confirmados, y sincronia con el catalogo del core; sin tocar el core.

## Fase 6: Datos web

Recuperacion de informacion actual para enriquecer. Criterio: enriquecimiento
web verificable, acotado y trazable.

## Fase 7: Interfaz y contrato publico de la capa

Consolidar la interfaz de consumo y cortar la primera version SemVer de extended.
Debe cubrir tres consumos, no solo el enriquecimiento:

1. el enriquecimiento en si,
2. la escritura de memorias delegadas y el evento de consolidacion (conscience),
3. la presentacion de memoria/conocimiento (`ia_nest_web`, core `FRONTERAS.md`).

Aqui se fijan los nombres provisionales de las fases anteriores.

FORMA (ADR 0011, aplicando meta ADR 0007): la interfaz es el CONTRATO UNIFORME.
Esta capa REENVIA sin alterar lo que no enriquece, SOBREESCRIBE `prompt.run`,
`reasoning.run` y `task.run` conservando su forma, y ANADE lo propio
(`memory_type.*`, `memory.*`, `knowledge.*`). El reenvio es generico: sin codigo
por capacidad. Detalle en `docs/EXTENDED_CONTRACT.md`; que cuenta como contrato,
en `docs/VERSIONADO.md`.

Motivo del reencuadre: la implementacion hasta la Fase 5c habia derivado a un
catalogo propio y MENOR (solo `prompt.run`), de modo que subir de capa hacia
perder capacidades. Eso incumple el invariante del ente y contradice el nombre de
la capa.

### Fase 7a: servicio con contrato uniforme y CLI de operador

Un servicio unico con reenvio generico y sobreescritura de `prompt.run`, armado
por un composition-root compartido (construccion perezosa: `memory.maintain` no
debe exigir el core ni Ollama). El CLI es una piel fina sobre ese servicio, y los
cuatro harnesses (`chat`, `ingest`, `knowledge`, `maintain`) se retiran.

Superficie de parametros: config da DEFAULTS, las banderas son override POR
PETICION, y ninguna bandera de politica decide cableado (hoy `RAG_ENABLED` hace
las dos cosas y produce un no-op silencioso). Combinacion contradictoria = error
tipado, no precedencia silenciosa.

Tres decisiones de superficie, en ADR 0011: migracion explicita (deja de migrarse
en cada arranque); identidad con defaults, con `session_id` generado y RECORDADO
si no se indica (no uno nuevo por invocacion, que romperia la continuidad de
`dialog`); y `--domain` unificado -gate de conocimiento, ruteo de modelo y faceta
de memoria con un solo valor-, divergencia deliberada respecto al core, que los
separa.

Verificado contra el codigo del core (2026-08-14): la REST del core expone once
rutas para sus nueve capacidades, asi que el reenvio generico por ruta es viable;
`POST /task/run` es SSE SIEMPRE, de modo que sobreescribirlo (7b) obliga a hablar
streaming; y el cliente actual valida campo a campo la respuesta del core, que es
re-declarar su contrato en codigo. De ahi la regla: TIPADO donde se sobreescribe,
OPACO donde se reenvia. El modelo de timeout unico pasa a conexion + inactividad.

Descubrimiento: el CLI no puede reenviar lo que no puede enumerar (necesita el
catalogo para construir su ayuda). Se pide al core por `extended CR-0002`
(`capability.list` en REST); mientras no exista, el CLI arranca con lista
estatica y migra despues. No bloquea.

Criterio de salida (falsable):

1. Conformidad con meta ADR 0007: contra un core stub que declare una capacidad
   que esta capa no conoce, esa capacidad es alcanzable a traves de ella SIN
   tocar su codigo. Para el CLI, el criterio aplica en cuanto exista
   `capability.list`; hasta entonces se verifica sobre la superficie de servicio.
2. `prompt.run` enriquecido y una capacidad reenviada responden por el mismo
   servicio y el mismo composition-root.
3. Passthrough verificable: enriquecimiento desactivado no recupera, no inyecta
   y no persiste, y sigue emitiendo traza propia.

### Fase 7b: `reasoning.run` y `task.run` sobreescritos

`task.run` enriquecido por subtarea via `task.plan` + `task.run(plan)`
(`extended CR-0001`, core ADR 0040). Requiere core v0.4, no entregado: esta
rebanada espera y no bloquea a 7a.

### Fase 7c: REST y MCP

Las mismas capacidades por las tres pieles, sin logica divergente. La REST es,
ademas, lo que permite que un cliente escrito contra el contrato apunte a esta
capa sin saber cuantas hay debajo.

### Fase 7d: primer tag

Requisitos en `docs/VERSIONADO.md`. Criterio: contrato versionado y consumible
por los tres consumos de arriba.

## Fuera de este plan

- Cambios en el core.
- Accion sobre sistemas externos (tool_contracts / external_*).
- Personalidad/etica (conscience); regulacion tecnica (pulse); GUI (web).
