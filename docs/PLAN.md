# Plan de ia_nest_extended

Estado: fases 0-5c, 7 y 8 completas; fase 6 APARCADA (2026-08-21, con su
motivo y su diseno escritos en ella); fase 9 ABIERTA (2026-08-22), con criterio
reconciliado el 2026-09-12 y sin implementar. La version publicada de la capa no
se anota aqui: la dicen `CHANGELOG.md` y los tags.
Version: 0.4 - 2026-09-12

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
core: minor, entregado en su tag v0.4.0; el rango que esta capa declara lo
recoge `docs/DEPENDENCIAS.md`.

Estado de los dos caminos:

- RAG upfront (`prompt.run`): DESBLOQUEADO. No depende de `task.plan`. El sustrato
  (ingesta, troceo, embedding, almacen, recuperacion por dominio) es agnostico de
  la version del core; la integracion usa el `prompt.run` estable. Se construye ya.
- RAG per-subtarea (`task.run`): IMPLEMENTADO en la Fase 7b contra el `main` de
  la linea v0.4 del core, y re-verificado en vivo contra su tag v0.4.0
  (`docs/DEPENDENCIAS.md`).

RAG no es un tier de memoria: es un subsistema hermano que comparte el mecanismo
de inyeccion y su presupuesto, no el modelo (`docs/VISION_MEMORIA.md`). Forma
reconciliada en ADR 0008: gate por dominio con similitud-en-todo sin dominio (D1);
dominio explicito o via `domain.route` semantico (D2, core ADR 0043); presupuesto
duro y minimo (D3). El camino upfront (`prompt.run`) se implementa ya
(`docs/handoff/fase_5_brief.md`); el per-subtarea (`task.run`) se implementa en
la Fase 7b sobre `task.plan` (core v0.4). Criterio: recuperacion relevante por
dominio inyectada en el prompt, dentro del presupuesto; sin tocar el core.

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

Estado: APARCADA (2026-08-21). No por falta de mecanismo: porque al disenarla
aparecio que lo que se quiere no es una fuente mas, es un COMPORTAMIENTO, y
merece abordarse entero y no a trozos. Se aparca con la idea escrita para que no
vuelva dentro de unos meses reducida a "buscar en internet", que es justo lo que
pierde su parte distintiva.

Criterio original, que se conserva: recuperacion de informacion actual para
enriquecer; enriquecimiento web verificable, acotado y trazable.

### Lo que se quiere de verdad: que el ente investigue

No "traer una pagina y volcarla". El ente se comporta como una persona que busca:

1. Detecta que no puede cubrir la necesidad con lo que sabe ni con su corpus.
2. **Redacta una pregunta.** No reenvia el material del interlocutor: formula una
   consulta propia.
3. La lanza a un buscador y recibe candidatos: sitios donde PODRIA estar.
4. **Abre y lee**, y busca DENTRO del contenido las referencias que queria.
5. Se queda con esas referencias, no con la pagina.

**La linea que gobierna esto, reconciliada el 2026-08-21:** lo que sale de la
maquina es una consulta que el ente REDACTA; no sale el material del
interlocutor. Consultar no es distribuir. Todo lo demas -modelos, extraccion,
indice, juicio de relevancia- es local, por directriz explicita del usuario.

### Las dos recuperaciones, que es la sustancia

El paso 4 es lo que separa esta idea de coger el primer resultado y volcarlo.
Hay DOS recuperaciones, no una:

- **localizar el documento**: la hace el buscador, fuera;
- **localizar lo relevante dentro del documento**: la hace el ente, dentro, con
  la maquinaria de similitud que ya existe.

La segunda es local y es donde aplican el suelo (D1/D5) y el presupuesto de
composicion. Sobre el suelo: la web NO tiene gate de dominio, asi que cae de
lleno en el regimen ESTRICTO de D5, y en su version extrema.

Forma frugal, coherente con la tesis de hardware del ente: primero SIMILITUD
-trocea la pagina y descarta barato, sin inferencia-, y solo despues el modelo,
que lee unicamente lo que sobrevive.

### Piezas y su cajon

- **Leer dentro del documento** no es un dominio: no es una materia y no tiene
  corpus (el corpus es la pagina traida, y se descarta). Es un tercer MODELO DE
  APOYO de la capa, hermano de los de ADR 0006 (embeddings y extraccion),
  configurable por instalacion. El dominio de la MATERIA sigue sirviendo para
  juzgar relevancia, pero como refinamiento, no como mecanismo.
- **El buscador va detras de un puerto**, con su adaptador, como el almacen y los
  modelos de apoyo. Configurable por instalacion y sustituible sin tocar codigo:
  no es trabajo extra, es la forma que la capa ya usa. Necesario ademas porque
  los proveedores limitan y bloquean.
- **Extraccion de texto**: hay herramienta madura y local para esto y no hay que
  escribirla (`trafilatura`, Apache-2.0, sin navegador). Solo haria falta un
  navegador headless si se demuestra por medida que las paginas de interes
  montan el texto con JavaScript.

### El disparador: un hecho, no un juicio

Cuando salir a investigar NO se decide clasificando la pregunta -eso es juicio, y
el juicio no vive aqui-. Se decide por **fracaso observado**: las fuentes locales
no devolvieron nada. Es un hecho, es barato y ya esta instrumentado ("cero
resultados es valido" desde D1; la telemetria emite `k_returned`).

Limite declarado: "no devolvio nada" no es el unico fracaso. El corpus puede
devolver algo irrelevante, o el modelo responder mal con aplomo. Como PRIMER
disparador es limpio y falsable; los demas, si hacen falta, despues.

### Lo que bloquea, y por donde se desbloquea

Investigar exige **iterar**: buscar, leer, comprobar si sirve, y si no, reformular
y volver a buscar. Eso choca de frente con un coste ya declarado en la Fase 7b:
un plan suministrado NO se puede re-planificar, y es `--no-enrich` lo que
conserva la re-planificacion. Hoy, por tanto, **enriquecer y re-planificar son
mutuamente excluyentes**, y una investigacion necesita las dos a la vez.

El camino de desbloqueo no es local: pasa por pedirselo al core por el canal CR,
igual que CR-0001 pidio un checkpoint y volvio como `task.plan` (core ADR 0040).

### Que queda fuera de esta capa

**Quien decide que el ente salga a investigar, y quien orquesta el bucle**, no es
de extended. Tiene la misma forma que la seleccion de capacidad (ver "Fuera de
este plan"): una funcion sin dueno. Registrada en
`ia_nest_meta/docs/CAPAS_FUTURAS.md`, que es su hogar, y no se duplica aqui.

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

Verificado contra el codigo del core: la REST expone un catalogo derivado de una
fuente unica, asi que el reenvio generico por ruta es viable. Desde la linea v0.4,
`POST /task/run` devuelve JSON y el flujo vive en `POST /task/stream` (core
ADR 0046, enmienda D5-a). El cliente valida campo a campo solo lo que esta capa
necesita interpretar: TIPADO donde se sobreescribe, OPACO donde se reenvia. El
modelo de timeout unico pasa a conexion + inactividad.

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

IMPLEMENTADA. `reasoning.run` reusa el vertical upfront de `prompt.run`.
`task.run` pide `task.plan`, copia el objeto sin `params`, edita solo cada
`plan[i].prompt` con RAG de su dominio resuelto y devuelve el plan al core
(`extended CR-0001`, core ADR 0040/0047/0048). La memoria experiencial y
delegada se inyecta una sola vez en el prompt superior para COMBINE/EVALUATE;
el write-back conserva solo el prompt original y la respuesta combinada.

Coste declarado: el plan suministrado no puede re-planificarse; `--no-enrich`
conserva el camino sin plan y su capacidad de re-planificacion. `task.stream`
sigue reenviado sin enriquecer porque el core no admite plan suministrado en esa
capacidad. Implementado contra el `main` de la linea v0.4 del core (`705941e`),
antes de su tag, y re-verificado en vivo contra el tag v0.4.0
(`docs/DEPENDENCIAS.md`).

### Fase 7c: REST y MCP

Las mismas capacidades por las tres pieles, sin logica divergente. La REST es,
ademas, lo que permite que un cliente escrito contra el contrato apunte a esta
capa sin saber cuantas hay debajo.

### Fase 7d: primer tag

Requisitos en `docs/VERSIONADO.md`. Criterio: contrato versionado y consumible
por los tres consumos de arriba.

## Fase 8: Despliegue reproducible de la capa

Estado: CERRADA (verificada el 2026-08-21 instalando en una maquina limpia del
laboratorio, desde su snapshot de sistema operativo: un solo comando con su
fichero de parametros dejo la capa utilizable por un operador desde su
directorio personal, sin activar venv).

Esta capa NO tiene instalador de despliegue. Tiene `install.sh`, que prepara un
entorno de DESARROLLO -venv, PostgreSQL en docker, pytest- y eso es otra cosa.

Consecuencia comprobada al desplegarla por primera vez en un laboratorio real
(2026-08-18/19): el venv, la configuracion, el almacen en otro anfitrion, el
corpus y la disponibilidad de los comandos se resolvieron A MANO. Nada de eso lo
reproduce un comando, de modo que la capa funciona en la maquina donde se monto y
no se sabe desplegar en otra.

El core si lo tiene, y marca la forma: layout declarativo (`config/`, `state/`,
`repositories/`), servicios, y verificacion al terminar.

Alcance:

1. Instalador hermano del del core, con el MISMO layout. La configuracion vive
   fuera del repositorio; hoy el `.env` de esta capa vivia dentro.
2. Los comandos quedan disponibles para el OPERADOR, no solo para los servicios.
   Hoy ninguna de las dos capas deja su CLI en el PATH: hay que activar un venv y
   recordar rutas, y el tabulador no ayuda porque el binario no esta donde mira.
3. Permisos utilizables: la configuracion que la CLI necesita debe poder leerla
   el usuario que la ejecuta.
4. El almacen de esta capa como parte declarada del despliegue, no como paso
   manual previo.

Criterio de salida (falsable): un despliegue desde cero en una maquina limpia,
con un solo comando y su fichero de parametros, deja la capa utilizable por un
operador que no haya visto el repositorio; y el mismo comando repetido no rompe
lo ya instalado.

Nota de frontera: la fase 7c (REST y MCP) anade servicios que este instalador
tendra que levantar. Conviene que 8 llegue despues de 7c, o que se disene
sabiendo que llegan.

## Fase 9: Sintesis de hilo (ADR 0007, enmienda del 2026-08-22)

Estado: ABIERTA (2026-08-22), con su criterio RECONCILIADO el 2026-09-12 y su
brazo de control ya medido. Sin implementar.

Reabre la sintesis de cluster que el ADR 0007 habia diferido con nombre. El
motivo del diferimiento -"solo aporta con acumulacion de muchos episodicos
relacionados, que aun no existe"- era correcto para el problema que anticipaba,
VOLUMEN, y ajeno al que aparecio: COHERENCIA. Medido el 2026-08-21 sobre una
sesion real, con **cuatro turnos y siete engramas** el contexto ya llevaba dos
hechos incompatibles del mismo asunto.

La razon es estructural y no de tamano: **un conjunto de engramas atomicos no
puede expresar que uno reemplaza a otro**, solo coexistir. El ADR 0013 mitiga el
sintoma -marca procedencia, anota las versiones en conflicto y las despriorza-
pero no lo resuelve: siguen siendo items sueltos. Lo que da DIRECCION a un hilo
es una frase con estructura temporal, y eso es sintesis.

### Alcance

1. **Sintesis por hilo**, no por cluster tematico: resumen del hilo de una
   sesion, generado por ventana temporal.
2. **Combinado, no sustitucion** (forma reconciliada el 2026-08-22): los
   engramas del hilo CON sus referencias a los datos, MAS el resumen. El resumen
   da continuidad barata y con perdida; las referencias mantienen el anclaje
   auditable que un resumen disuelve -hoy cada item conserva su
   `source_trace_id`; un resumen de doce, no-.
3. **Procedencia heredada del ADR 0013**: la sintesis registra `stated_by` de lo
   que resume, y una sintesis que mezcla emisores no puede presentarse como
   dicha por ninguno.
4. Composicion en el recall: cuando el hilo tiene sintesis, esta sustituye en el
   presupuesto a los engramas que resume, no se suma a ellos. Leido junto al
   punto 2: **combinado en el ALMACEN, sustitucion en el PRESUPUESTO**.
5. **Estado de trabajo, no recuerdo** (ADR 0007, enmienda del 2026-09-12): la
   sintesis vive y muere con el hilo, y el barrido de la Fase 4 no la
   promociona a `semantic`; sedimentar algo del hilo es juicio de conscience.
6. **Lo exacto no se resume**: nombres, fechas y referentes siguen anclados y
   exactos via `entities` (ADR 0004), que hoy esta declarado y SIN implementar.
   Es una dependencia de esta fase, no algo que ella reinvente.

### Lo que NO entra

Que la sintesis ELIJA que merece recordarse. Eso es juicio y es de conscience
(ADR 0002; test de frontera del ADR 0007). Aqui la ventana es temporal y
mecanica: resume lo que hay, no lo que importa.

### Criterio de salida (falsable), RECONCILIADO el 2026-09-12

Se mide sobre un despliegue NATURAL con la puerta de laboratorio
(`docs/PUERTA_LABORATORIO.md`) y sus reglas: dos ejecutores independientes,
evidencia en `local/lab/`, y lo no cubierto declarado. La sintesis se conmuta
por configuracion, que desde la v0.2.2 viaja por el fichero de parametros del
instalador.

**Linea base ya medida, y no se vuelve a discutir.** El brazo SIN sintesis es la
linea L4b de la puerta: el interlocutor se corrige a si mismo y se le pregunta
despues. Acumulado limpio a 2026-09-12: **2 aciertos de 15**.

Las cuatro lineas bloquean.

1. **Coherencia.** El mismo hilo de L4b, medido con la sintesis ACTIVADA y
   DESACTIVADA en la misma instalacion y con el resto de la configuracion igual.

       PASA si   con sintesis >= 8 de 9
       y ademas  la diferencia sobre el brazo sin sintesis es >= 5 aciertos

   n = 9 por brazo, en tres ejecuciones de tres repeticiones, cruzado por dos
   ejecutores. El 9 no es capricho: con n = 3 la misma linea dio 0/3, 1/3 y 3/3
   sin que el producto cambiara. Si el brazo sin sintesis subiera solo, la fase
   no ha demostrado nada y se replantea en vez de darse por buena.
2. **Anclaje.** Toda sintesis conserva enlaces a TODOS los engramas de su
   ventana, verificable por consulta -contando enlaces contra items- y no por
   lectura. Un resumen sin enlaces es un resumen sin origen direccionable.
3. **Coste.** Para el mismo hilo, el contexto compuesto con sintesis no ocupa
   mas tokens que sin ella, y un hilo que antes no cabia en el presupuesto cabe.
4. **No promocion.** Tras `maintain`, ninguna sintesis aparece en `semantic`.
   Verificable por consulta. Sale de la enmienda del ADR 0007 del 2026-09-12: la
   sintesis es estado de trabajo, no recuerdo, y esta es la linea que impide que
   un resumen alucinado se vuelva memoria duradera.

Y una heredada del ADR 0013, que tambien bloquea: **una sintesis que mezcla
emisores no se presenta como dicha por ninguno**.

Riesgo declarado: resumir con el mismo modelo que alucina produce resumenes de
alucinaciones. No se elimina; se acota con las lineas 2 y 4, y por eso son
criterio y no deseo.

Lo que este criterio NO cubre, declarado: que la sintesis sea BUENA. Se mide que
sostiene el hilo, no su calidad. Y no exige `entities` (ADR 0004): los artefactos
exactos siguen anclados como hoy, en engramas atomicos.

## Deuda de diseno declarada

Hallazgos reconciliados que NO son de la fase en curso. Se registran con su
disparador para que no se pierdan ni se cuelen sin decidir.

### D1. Suelo de relevancia en la recuperacion RAG

Estado: CERRADA (implementada 2026-08-18, `docs/handoff/deudas_d1_d2_brief.md`).

Hoy la recuperacion devuelve `rag_top_k` chunks SIEMPRE, por poco que se parezcan
al prompt: hay top-k y presupuesto de tokens, pero ningun umbral minimo de
similitud. Observado en laboratorio (2026-08-14): a un "que recuerdas de mi?" sin
dominio se le inyectaron primeros auxilios y critica literaria.

Es un defecto mecanico y barato de corregir; no requiere juicio ni conscience.
Distinto es saber que una pregunta NO necesita conocimiento: eso si es juicio, y
es de conscience. Disparador: antes de crecer el corpus, porque el ruido escala
con el.

Cierre: suelo configurable `rag_min_score` (default `0.38` al cerrarse esta
deuda; subido a `0.50` al crecer el corpus, ver CHANGELOG, y convertido en la
BASE de los dos regimenes de D5), aplicado en
`RagStore.retrieve` y hecho llegar explicitamente desde `ExtendedConfig` a los
dos caminos que recuperan RAG (`prompt.run`/`reasoning.run` via
`MemoryEnricher.enrich` y `task.run` per-subtarea via
`MemoryEnricher.retrieve_rag`), y tambien a `memory.recall`. Margen declarado
entre 0.350 (ruido) y 0.406 (acierto): punto de partida afinable en laboratorio,
no una constante (`docs/POLITICA_WRITEBACK.md`).

### D2. El filtro de dominio excluye las memorias sin dominio

Estado: CERRADA (implementada 2026-08-18, `docs/handoff/deudas_d1_d2_brief.md`).

Con `--domain` se filtran tambien los tiers experienciales (`semantic`,
`episodic`), de modo que una memoria SIN `domain_tag` queda fuera. Efecto
observado: preguntando con dominio, el ente "olvida" lo que sabe de su
interlocutor.

La regla anti-colision (`docs/FORMA_ENRIQUECIMIENTO.md`, decision 2) esta pensada
para dominios INCOMPATIBLES; una memoria sin dominio no es incompatible, es
neutra. Propuesta a reconciliar: que las memorias sin `domain_tag` sean siempre
candidatas y el filtro excluya solo las de un dominio distinto. Toca ranking y
recall, fuera del alcance de la Fase 7. Nota: los tipos delegados
(`identity`, `principles`, `safety`) ya se inyectan de forma incondicional y no
estan afectados.

Cierre: reconciliado por el usuario en los terminos de arriba (una memoria sin
`domain_tag` es SIEMPRE candidata; el filtro excluye solo un dominio DISTINTO).
Implementado en el filtro de tipos `RANKED` (`dialog`/`episodic`/`semantic`) del
adaptador PostgreSQL. El filtro de los tipos `ALWAYS_INJECT` (delegados) queda
sin tocar a proposito: nunca recibe `domain_tag` desde `MemoryEnricher.recall`,
con o sin `--domain` en la peticion, asi que su inyeccion incondicional no
cambia.

### D4. La memoria no tiene suelo de relevancia

Estado: CERRADA (implementada 2026-08-19, `docs/handoff/deuda_d4_brief.md`).

D1 puso un suelo de similitud al RAG y NO a los tiers de memoria. El efecto se
observo en laboratorio (2026-08-18): a una pregunta sobre guardado de semillas se
le inyecto un engrama con el color favorito del interlocutor.

Es el mismo defecto que D1 -recuperar no es volcar- en el otro lado del
enriquecimiento. Hay top-k y presupuesto, pero ningun umbral minimo.

Matiz que lo separa de D1, y por el que no se resuelve copiando la solucion: los
tipos delegados (`identity`, `principles`, `safety`) se inyectan de forma
incondicional por diseno, y un suelo no debe alcanzarlos. Disparador: antes de que
`conscience` escriba en los delegados, porque a partir de ahi el contexto
permanente crece y el ruido con el.

Implementado con `IANEST_EXTENDED_MEMORY_MIN_SIMILARITY`: gatea la similitud
solo de `episodic`; la relevancia compuesta conserva su funcion de orden.
`semantic`, `dialog` y los delegados quedan fuera del mecanismo. Reconciliado
2026-08-19: el brief original tambien aplicaba el suelo a `semantic`; se
descarto porque la promocion `episodic -> semantic` ya es un filtro, y es un
filtro por JUICIO en vez de por distancia coseno -usar el gradiente que ya
existe es mejor que un umbral que no distingue una alergia de un color
favorito-. Consecuencia declarada: hoy la Fase 4 apenas consolida, asi que a
corto plazo esto se parece a no tener suelo; no invalida la decision, senala que
el trabajo siguiente esta en la consolidacion. El default 0.10 es PROVISIONAL y
sin medida.

Su calibracion se anuncio "junto a D5", y eso ya no se cumplio: D5 quedo
cerrada el 2026-09-12 y este suelo sigue sin medir. No es la misma medida -uno
gatea conocimiento y el otro memoria episodica, y sus poblaciones no son
comparables-, asi que se separa aqui en vez de arrastrar una promesa vencida.
Disparador vigente: cuando haya uso real acumulado en un despliegue, o antes si
`conscience` empieza a escribir en los delegados.

### D5. Un umbral global puede no separar ruido de acierto

Estado: CERRADA (implementada 2026-09-12,
`docs/handoff/deuda_d5_brief.md`).

Al calibrar el suelo del RAG con preguntas formuladas como las hace una persona
-y no reformulando el texto del corpus, que fue el error de la primera
calibracion- las dos bandas casi se tocan: el ruido llega mas arriba y el acierto
empieza mas abajo de lo que sugerian las primeras medidas.

Mientras las bandas se solapen, ningun valor unico las separa: subirlo silencia
respuestas correctas y bajarlo admite ruido. Eso deja de ser calibrar y pasa a ser
diseno.

**MEDIDO el 2026-08-19, con el corpus ya crecido y sondas escritas como preguntas
reales**: el solape existe. La sonda de ruido mas alta supera al acierto mas bajo,
de modo que el umbral vigente pierde una consulta legitima para no admitir una
formula de cortesia. El disparador de esta deuda se ha cumplido y deja de ser un
riesgo declarado.

**REMEDIDO el 2026-08-21 en las cuatro combinaciones de relevancia y dominio**
(19 corpus, 57 chunks, embebedor `bge-m3`; tablas en `local/lab/`, no
versionadas). La medida del 08-19 solo cubria dos esquinas opuestas y por eso
apuntalaba una causa equivocada:

    relevante CON dominio  0.327-0.783 (n=17)   relevante SIN dominio  0.430-0.783 (n=17)
    ruido     CON dominio  0.310-0.402 (n=8)    ruido     SIN dominio  0.357-0.458 (n=8)
    cruzado   CON dominio  0.248-0.370 (n=5)

La causa NO es que el umbral mezcle dos poblaciones incomparables. Es mas simple y
mas dura: **el gate de dominio busca en un subconjunto, asi que la puntuacion con
dominio es siempre menor o igual que sin dominio para la misma sonda** (verificado
sonda a sonda, ni un contraejemplo). Un umbral global castiga por tanto a las
consultas CON dominio, que son las mas fiables, porque el gate les ha quitado de
la baraja el mejor resultado global.

Diseno reconciliado el 2026-08-21: **dos regimenes en vez de uno**, elegidos por
el dominio EFECTIVO que llega al almacen. El suelo con dominio puede ser mas bajo
que el suelo sin dominio.

Lo que el diseno no hace, declarado para no venderlo de mas: **no separa las
bandas**. El solape sobrevive en los dos regimenes y es peor en el laxo (-0.075)
que en el estricto (-0.028). Dos regimenes dan dos puntos de operacion mejores que
uno; no vuelven separable el problema.

Ademas, parte del solape del regimen laxo NO es de umbral: los tres aciertos mas
bajos con dominio (`codigo` 0.327, `educacion` 0.392, `matematicas` 0.411) son
corpus de uno o pocos chunks que no contienen la respuesta. Sin ellos la banda
arranca en 0.464. Eso es **deuda de corpus**, y devolver cero es ahi el
comportamiento correcto.

Alternativas descartables si esa no basta: umbral por dominio, o umbral relativo
al mejor resultado de cada consulta en vez de absoluto.

Cierre: dos claves opcionales, `rag_min_score_domain` y
`rag_min_score_no_domain`, sobrescriben por regimen la base `rag_min_score` sin
retirarla ni cambiar su default `0.50`. El dominio EFECTIVO que llega al almacen
elige el regimen; `general` y un auto-ruteo sin confianza suficiente siguen en
el regimen sin dominio. La regla se aplica tanto al enriquecimiento como a
`memory.recall`, y `rag.retrieve` declara `score_regime` y `min_score`.

La CALIBRACION sigue pendiente por instalacion: los puntos medidos `0.41` con
dominio y `0.46` sin dominio proceden de un unico corpus y un unico embebedor,
las bandas aun se solapan y el margen del regimen estricto sobre el ruido es
solo `0.002`. Son recomendacion documentada, no defaults del codigo.

### D6. El fragmento que pierde su referente

Observado el 2026-09-21 en una sesion REAL del operador, no en una sonda. En un
hilo de recomendaciones de cine, la destilacion guardo estos engramas:

    episodic/facts  la primera puntuacion es 6
    episodic/facts  la segunda puntuacion es 8

En su turno significaban algo. Fuera de el, nada: el ordinal perdio aquello a lo
que se referia. Y `episodic` es de ambito USUARIO, asi que esos fragmentos son
candidatos a inyectarse en cualquier conversacion futura del mismo interlocutor,
donde no existe ninguna "primera puntuacion".

Efecto medido en ese mismo hilo: al pedir "dame la lista de peliculas que has
valorado y su puntuacion", la respuesta acerto tres lineas, **invento tres** -las
pego a la lista que el propio modelo habia recomendado DESPUES- y omitio dos.

**No es lo mismo que la Fase 9 persigue, y conviene no confundirlo.** La Fase 9
ataca la INCOHERENCIA -dos versiones del mismo hecho que no pueden ordenarse
entre si-. Esto es PERDIDA DE REFERENTE: un item que era correcto cuando se
escribio y es ruido fuera de su contexto.

La sintesis de hilo lo MITIGA en lo que se inyecta, porque sustituye los
fragmentos por una frase con los referentes puestos. Pero **no los retira del
almacen**, asi que el problema sobrevive a la fase.

Candidatos, sin decidir: que la extraccion resuelva ordinales contra el turno al
que pertenecen antes de escribir; o que un item sin referente resoluble no se
escriba, al modo del anclaje lexico del ADR 0013. Lo primero pide juicio y roza
la frontera de conscience; lo segundo es mecanico y mas barato.

Disparador: antes de que la memoria del usuario crezca, porque cada fragmento
roto es ruido permanente. Material de referencia en `local/lab/`, hilo
`cine_20260921`.

### D3. La identidad como fuente conmutable

Las fuentes de enriquecimiento son declaradas por la capa y desactivables por
nombre (`docs/EXTENDED_CONTRACT.md`). La identidad del ente debe ser una de
ellas, con su switch (`--personality` o equivalente), para poder comparar
respuestas con y sin la capa de personalidad.

Motivo: la personalidad no es neutra ni siquiera en una pregunta tecnica -puede
mejorar o empeorar la respuesta-, y sin switch no hay forma de medir cual de las
dos cosas hace. No se implementa en la Fase 7a. Disparador: cuando conscience
escriba en los tipos delegados y haya algo que conmutar.

## Fuera de este plan

- **La seleccion de capacidad.** Hoy nadie decide si una peticion es atomica
  (`prompt.run`) o descomponible (`task.run`): el core no lo hace por diseno y
  esta capa reexpone ambas sin elegir, de modo que el operador tiene que saberlo.
  Observado en uso real. No es un fallo de ninguna de las dos capas: es una
  funcion sin dueno, candidata a capa nueva.
- Cambios en el core.
- Accion sobre sistemas externos (tool_contracts / external_*).
- Personalidad/etica (conscience); regulacion tecnica (pulse); GUI (web).
