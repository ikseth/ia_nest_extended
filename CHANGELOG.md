# Changelog

Formato basado en Keep a Changelog; SemVer (ver core `docs/VERSIONADO.md`).
Sin acentos por convencion.

## [0.3.1] - 2026-09-21

### Corregido
- **El instalador fallaba al reejecutarse en cuanto existia una sintesis de
  hilo.** Las migraciones se reaplican todas en cada arranque, y la `0004`
  volvia a poner el `CHECK` de `memory_links` sin `summarizes`, que la `0005`
  habia anadido: la segunda ejecucion moria con `CheckViolation`. La instalacion
  inicial iba bien; la repeticion, no, de modo que rompia la idempotencia que la
  linea L6 de la puerta comprueba. Ahora ambas migraciones **solo actuan si su
  valor no esta ya admitido**, asi que reaplicarlas en cualquier orden deja el
  mismo esquema. Se escribe ademas el invariante que faltaba en
  `docs/DESPLIEGUE.md`: toda migracion debe poder reaplicarse DESPUES de las
  posteriores. Correccion compatible: PATCH.

## [0.3.0] - 2026-09-21

### Anadido
- **Fase 9, sintesis de hilo (mecanismo).** Tipo de memoria nuevo
  `thread_summary`: estricto, escrito por extended, de ambito SESION y con
  namespace propio. Al terminar el write-back de un turno, y solo con
  `thread_synthesis_enabled`, se resume la ventana de
  `thread_synthesis_window_turns` (4 de arranque) con `synthesis_model` -por
  defecto el de extraccion-, y la sintesis sustituye a la anterior del hilo.
  Ancla con enlaces `summarizes` a cada engrama que resume (migracion `0005`,
  sin tocar la `0004` publicada), hereda la procedencia del ADR 0013 -`unknown`
  cuando la ventana mezcla emisores- y en el recall ocupa el PRESUPUESTO de los
  engramas que resume, que siguen en el almacen y alcanzables por consulta.
  `maintain` la archiva con el `dialog` de su sesion y NUNCA la promociona a
  `semantic`: es estado de trabajo, no recuerdo (ADR 0007, enmienda del
  2026-09-12). **Apagada por defecto**: con la fase apagada el comportamiento es
  el de siempre. Adicion compatible: MINOR en la serie pre-1.0.

  Lo que esto NO cierra es la FASE: su criterio de salida -coherencia >= 8 de 9
  contra una linea base medida de 2 de 15- se mide en laboratorio con la puerta
  y por dos ejecutores. Aqui se entrega el mecanismo.

### Cambiado
- **Criterio de salida de la Fase 9, RECONCILIADO** (2026-09-12). Deja de ser
  una propuesta: se mide sobre un despliegue natural con la puerta de
  laboratorio y sus reglas -dos ejecutores, evidencia guardada, lo no cubierto
  declarado-, y la sintesis se conmuta por configuracion, que desde la v0.2.2
  viaja por el fichero de parametros. Cuatro lineas bloquean: coherencia
  (>= 8 de 9 con sintesis y una diferencia >= 5 sobre el brazo sin ella, con
  n = 9 por brazo, porque con n = 3 la misma linea dio 0/3, 1/3 y 3/3 sin que el
  producto cambiara), anclaje verificable por consulta, coste en tokens, y **no
  promocion a `semantic`**, que sale de la enmienda "recordar no es sostener un
  hilo" y es lo que impide que un resumen alucinado se vuelva memoria duradera.
  La linea base del brazo sin sintesis ya esta medida y no se vuelve a discutir:
  2 aciertos de 15. Impacto de version: ninguno.

## [No publicado]

### Corregido
- **La sintesis de hilo ya no tapa la procedencia que resuelve una
  contradiccion.** Al componer el recall, los dos extremos de cada enlace
  `contradicted_by` quedan fuera del conjunto que la sintesis sustituye: el
  resumen, la version del usuario y el candidato anotado del modelo coexisten,
  con sus etiquetas y orden intactos. Los demas engramas resumidos se siguen
  sustituyendo y el recorte por presupuesto no cambia. Con la sintesis apagada
  el camino es identico. No se modifica el prompt de sintesis. Correccion
  compatible: PATCH.

### Anadido
- Linea **L7** en la puerta de laboratorio, **memoria conversacional con
  referente**, derivada de una sesion real y no de una sonda: cuatro turnos con
  puntuaciones por ordinal y una pregunta final por una pieza concreta. Gatea
  sobre la pregunta estrecha -testigo correcto, prohibidos los valores de lo
  nunca puntuado- y REGISTRA aparte la variante de lista completa por lineas
  acertadas, inventadas y omitidas, que es mas informativa pero tambien mas
  ruidosa. **No bloquea todavia**: mide la deuda D6, que esta abierta y
  declarada; bloqueara cuando se cierre. Impacto de version: ninguno.
- Deuda de diseno **D6, el fragmento que pierde su referente**, observada en una
  sesion REAL del operador y no en una sonda. La destilacion guardo engramas como
  "la primera puntuacion es 6": correctos en su turno y ruido fuera de el, porque
  el ordinal perdio aquello a lo que se referia. Como `episodic` es de ambito
  usuario, esos fragmentos son candidatos en cualquier conversacion futura del
  mismo interlocutor. Efecto medido en el mismo hilo: al pedir la lista de
  peliculas valoradas, la respuesta acerto tres, invento tres y omitio dos. **No
  es lo que persigue la Fase 9** -aquello es incoherencia entre versiones; esto
  es perdida de referente-, y la sintesis lo mitiga en lo inyectado sin retirarlo
  del almacen. Impacto de version: ninguno.

## [0.2.3] - 2026-09-12

### Anadido
- Enmienda al ADR 0013 (2026-09-12): **la contradiccion no vive en un cajon**.
  Hallada al cruzar dos ejecutores en la puerta sobre el mismo despliegue
  natural, que dieron veredictos distintos. La anotacion salia 6 de 9 veces sin
  que el producto cambiara, y la causa no era la banda de similitud sino que
  `record_contradiction` comparaba dentro del mismo `namespace`, que lo elige el
  modelo de extraccion: medido, la frase del usuario cayo en `episodic/tasks` y
  la del modelo en `episodic/facts`, asi que el candidato no entraba en la
  comparacion. Era un supuesto no escrito del ADR. Se corrige comparando por
  TIPO y usuario, sin filtrar por cajon, y se recorta el papel de la anotacion:
  pasa a observacion medida, porque L4a paso 3/3 en nueve repeticiones tambien
  cuando no disparo. Encargo en
  `docs/handoff/contradiccion_entre_namespaces_brief.md`.
  Correccion compatible: PATCH en la serie pre-1.0.

### Cambiado
- La linea L3 de la puerta deja de exigir la anotacion de conflicto y pasa con
  la etiqueta de procedencia y el orden, que son mecanismo puro y salieron
  correctos en las nueve repeticiones medidas. La tasa de anotacion se sigue
  registrando en la evidencia. Motivo: exigir un refuerzo como criterio hacia
  suspender la puerta por algo que el comportamiento medido no necesita.
- La puerta emite una linea de progreso por sonda terminada, con linea,
  repeticion y veredicto parcial, antes de conservar su resumen final.

## [0.2.2] - 2026-09-12

### Anadido
- El fichero de parametros de `deploy/setup.sh` admite claves adicionales
  `IANEST_EXTENDED_*` y las conserva literalmente, en orden, en `extended.env`
  y en el snapshot efectivo. El instalador no duplica la validacion de valores
  de `config.py`; las claves desconocidas sin prefijo siguen fallando y una
  colision con una variable generada aborta con `configuration_collision`, la
  clave y la opcion equivalente. Adicion compatible: PATCH en la serie pre-1.0.
- `docs/handoff/instalador_configuracion_brief.md`: el instalador no sabe
  declarar la configuracion de la capa. Medido al ejecutar la puerta contra el
  primer despliegue natural: `ExtendedConfig` tiene 44 campos, `setup.sh` conoce
  21 claves y escribe 11 variables, y ningun umbral esta entre ellas. Afinar
  obliga hoy a editar `extended.env` a mano, y un paso a mano invalida la
  pasada, de modo que el lado de "ajuste de configuracion" de la regla de
  clasificacion no tiene canal legitimo. Se pide paso a traves de las claves
  `IANEST_EXTENDED_*` declaradas en el fichero de parametros, con colision
  tipada y sin que el instalador valide valores -el esquema vive en la capa-.
- Enmienda al ADR 0007 (2026-09-12), reconciliada al releer la Fase 9 antes de
  fijar su criterio: **recordar no es sostener un hilo**. Son dos funciones
  distintas sobre el mismo sustrato -el historico de lo que una conversacion
  genera, para tener continuidad manana, y el tratamiento del hilo argumental
  mientras ocurre, para no contradecirse ahora-. La enmienda anterior zanjaba la
  propiedad apelando a que la ventana es temporal; esta lo hace por la funcion,
  y de ahi salen cuatro limites que el alcance no tenia: la sintesis de hilo es
  ESTADO DE TRABAJO y el barrido de la Fase 4 no la promociona a `semantic`; la
  propiedad queda cerrada (andamiaje es mecanismo, elegir que se recuerda es
  juicio); lo exacto -nombres, fechas, referentes- no se resume y sigue anclado
  via `entities` (ADR 0004, declarado y sin implementar, luego dependencia
  declarada de la fase); y el combinado es en el ALMACEN mientras la sustitucion
  es en el PRESUPUESTO, que resuelve la tension entre dos puntos del alcance.
  No fija el criterio de salida: sigue pendiente de la medida limpia de L4b.
  Impacto de version: ninguno.

### Cambiado
- La linea L2 de la puerta deja de juzgar la respuesta del modelo y se juzga por
  lo que devuelve `memory.recall` (reconciliado el 2026-09-12, al medir). Dos
  pasadas mostraron al modelo respondiendo `Xanthe` a un testigo
  `Xanthe74bad8d4b3` mientras el recall lo entregaba entero y con su
  procedencia: exigir la respuesta convertia la linea en una prueba de fidelidad
  de transcripcion, y hacia suspender a la capa por algo que no gobierna. La
  respuesta sigue en la evidencia. L4a y L4b no cambian, porque ahi lo que se
  mide es si el contexto compuesto induce una contradiccion, y eso solo se ve en
  lo que el modelo dice.

### Corregido
- La puerta de laboratorio se contaminaba a si misma. Ejecutada por primera vez
  contra un despliegue natural (2026-09-12), dio NO PASA, y ninguno de sus
  fallos era de la capa: toda la pasada compartia un `user_id`, y como la
  memoria episodica es de ambito usuario, las sondas se pisaban -una linea
  llego a responder con el testigo de otra-. Ahora cada sonda usa su propia
  identidad, una por linea y por repeticion. Ademas los testigos dejan de
  llevar guion, que invitaba al modelo a truncarlos y hacia que la sonda
  midiera transcripcion en vez de memoria, y L5/L5r pasan de declararse NO
  EJECUTABLES a ejecutarse de verdad, porque la condicion que lo impedia -un
  instalador que solo admitia un corpus- caduco con la v0.2.1.
- `docs/PUERTA_LABORATORIO.md` recoge lo aprendido al ejecutarla: identidad por
  sonda y no por pasada, y que la REST no publica ni la puntuacion del RAG ni
  un campo de corpus estructurado -eso vive en la telemetria, que es fichero en
  la maquina y no superficie de consumo-, asi que la puerta lo declara en vez
  de leer ficheros por detras.
- Contradiccion interna del ADR 0013: su seccion "Consecuencia" afirmaba que
  `EngramStatus.SUPERSEDED` dejaba de ser un estado muerto, mientras el cuerpo
  del mismo ADR decia que sigue sin usarse. Verificado en el codigo: solo esta
  declarado. Venia de un borrador en el que la version del usuario retiraba la
  del modelo, forma descartada por el margen medido.
- Impacto de version: ninguno, instrumental y documentacion.

## [0.2.1] - 2026-09-12

### Anadido
- D5, dos regimenes para el suelo del RAG. La base
  `IANEST_EXTENDED_RAG_MIN_SCORE` se conserva, incluido su default `0.50`, y
  las nuevas `IANEST_EXTENDED_RAG_MIN_SCORE_DOMAIN` e
  `IANEST_EXTENDED_RAG_MIN_SCORE_NO_DOMAIN` son `float | None` con default
  `None`: cada una gana solo en su regimen y, ausente, cae a la base. Elige el
  dominio efectivo entregado al almacen, no el solicitado. La misma regla
  gobierna enriquecimiento y `memory.recall`. `rag.retrieve` declara ahora
  `score_regime` y `min_score`. Adicion compatible: PATCH en la serie pre-1.0.
- Calibracion PROVISIONAL asociada a D5, medida el 2026-08-21 sobre 19 corpus,
  57 chunks y el embebedor `bge-m3`, con n=17 consultas relevantes por regimen:
  `0.46` sin dominio (estricto) queda por encima del ruido medido, cuyo maximo
  fue `0.458`, pero pierde 2/17 consultas legitimas (`matematicas` 0.430 y
  `educacion` 0.431). Su margen es solo `0.002`, dos milesimas. `0.41` con
  dominio (laxo) queda por encima del ruido con dominio (maximo `0.402`) y del
  cruzado (maximo `0.370`), pero pierde tambien 2/17 (`codigo` 0.327 y
  `educacion` 0.392). Las bandas se solapan; estos valores no son universales
  ni pasan a ser defaults del codigo. La calibracion sigue pendiente para cada
  corpus y embebedor.
- `CORPUS_MANIFEST` permite al instalador ingerir N corpus, cada uno con sus
  dominios, desde un manifiesto validado por completo antes de la primera
  ingesta. Es excluyente con la terna antigua, que conserva exactamente su
  comportamiento; las rutas relativas parten del directorio del manifiesto y
  un fallo aborta nombrando el corpus sin revertir los anteriores. Adicion
  compatible del esquema publico de configuracion: PATCH en la serie pre-1.0.
- `docs/PUERTA_LABORATORIO.md`, reconciliado el 2026-09-12: la puerta de
  laboratorio de esta capa, que aplica meta ADR 0010. Certifica un despliegue
  NATURAL (instaladores, un tag de cada uno y ficheros de parametros declarados,
  sin pasos a mano) por la superficie REST, y separa fallo de codigo de ajuste
  de configuracion con una sola pregunta: se arregla cambiando un valor de esos
  ficheros, o no. Oraculo externo por testigos fijados antes de medir; dos
  agentes independientes. Su linea L4b -la autocorreccion del interlocutor, que
  el ADR 0013 no cubre- es el brazo sin sintesis de la Fase 9 y no bloquea la
  puerta. Se escribe ANTES de medir. Impacto de version: ninguno.
- `tools/lab/puerta.py`: el script que ejecuta la puerta de laboratorio contra
  la REST de un despliegue real y devuelve veredicto (0 PASA, 1 NO PASA,
  2 NULA). Solo biblioteca estandar, para que corra en la maquina desplegada
  sin instalar nada. Testigos fijados antes de responder -aleatorios en L2 y
  L3, par fijo en L4b- como oraculo externo, `user_id` nuevo por pasada, L4b
  registrada sin decidir el codigo de salida, y L5/L5r declaradas NO
  EJECUTABLES mientras el instalador no acepte N corpus. Ocho pruebas contra un
  stub HTTP. Instrumental: no toca contrato publico ni comportamiento de la
  capa. Impacto de version: ninguno.
- Dos briefs de implementacion para el agente codificador.
  `docs/handoff/instalador_n_corpus_brief.md`: el instalador ingiere N corpus
  desde un manifiesto declarativo (`CORPUS_MANIFEST`, excluyente con la terna
  actual, que no se retira; rutas relativas al manifiesto; validacion completa
  antes de la primera ingesta). Hoy solo admite UN corpus con un juego de
  dominios, asi que un laboratorio con muchos no se puede desplegar por el
  instalador y el corpus acaba entrando a mano, lo que invalida la puerta.
  `docs/handoff/puerta_script_brief.md`: `tools/lab/puerta.py`, solo biblioteca
  estandar, que ejecuta la puerta contra la REST y devuelve 0 PASA, 1 NO PASA y
  2 NULA, con testigos fijados en codigo como oraculo. Impacto de version:
  ninguno.

### Corregido
- Higiene documental: cinco sitios decian un estado que ya no era verdad.
  `CLAUDE.md` e `IA_NEST_EXTENDED_CONTEXT.md` copiaban el rango del core
  (`>=0.2 <0.3`, dos rangos por detras del real); ahora remiten a
  `docs/DEPENDENCIAS.md` sin copiar el numero, que es lo que dejo derivar las
  copias (hogar unico, meta ADR 0008). `IA_NEST_EXTENDED_CONTEXT.md` deja de
  declararse "semilla". `docs/PLAN.md` retira "v0.1.0 publicada" de su cabecera
  -la version la dicen el CHANGELOG y los tags- y las tres menciones a un core
  v0.4 "sin tag", que se re-verifico en vivo contra `v0.4.0` el 2026-08-20.
- Nota a la entrada `[0.2.0]`, que no se reescribe por estar publicada: su
  "la fase permanece abierta hasta su verificacion en maquina real" ya no era
  cierto al publicarla. La Fase 8 se cerro el 2026-08-21 al instalar en una
  maquina limpia (`docs/PLAN.md`), un dia antes del tag.
- Los documentos versionados dejan de nombrar maquinas concretas del
  laboratorio del operador: el PLAN y un brief de la fase 7b decian `rocinante`
  y `pitufo`. Lo medido y su fecha se conservan enteros; lo que desaparece es
  el nombre propio, que es estado de una red particular y no decision de la
  capa. Repo publico, y la regla ya vigente: la decision y su razon en git, el
  estado de una maquina en `local/`.
- Impacto de version: ninguno, solo documentacion.

## [0.2.0] - 2026-08-22

### Anadido
- Procedencia de los engramas, campo `stated_by` (ADR 0013): cada engrama
  registra si lo dijo el interlocutor (`user`), lo genero el modelo (`model`) o
  no consta (`unknown`), y esa marca viaja al contexto inyectado. La extraccion
  pide dos listas separadas por emisor y la procedencia la fija el codigo, no el
  modelo, con un anclaje lexico que degrada a `unknown` la atribucion que no se
  sostiene. Los engramas anteriores quedan en `unknown`: no se les inventa
  origen. El campo no se llama `provenance` porque ese nombre ya designa el
  origen de una entrada del catalogo. Migracion `0004_stated_by.sql`;
  `verify_schema` declara no migrado un esquema sin la columna. Adicion
  compatible sobre `memory.write` y `memory.recall`: MINOR.
- Fase 8, instalador de despliegue reproducible: `deploy/setup.sh` con fichero
  declarativo, layout externo `config/extended` y `state/extended`, almacen
  PostgreSQL+pgvector existente (incluido remoto, sin runtime local) o
  provisionado por Compose, migracion explicita, ingesta de TEXTO con vinculos
  dominio-corpus confirmados, wrappers de operador, units REST/MCP, espera a los
  puertos y verificacion ejecutable con codigo de salida. Incluye
  `docs/DESPLIEGUE.md` y pruebas aisladas de idempotencia, preservacion de
  configuracion y DSN fallido. Adicion compatible: PATCH; la fase permanece
  abierta hasta su verificacion en maquina real.

### Corregido
- Una respuesta de `task.run` que el propio core corto sin aceptar
  (`stop_reason` distinto de `task_done`) alimentaba la memoria episodica igual
  que cualquier otra. Ahora no: lo que salga de una tarea no convergida no se
  destila a `episodic` -lo que dijo el interlocutor si, y `dialog` se conserva
  entero-. El dato ya viajaba en la respuesta del core desde siempre; esta capa
  no lo leia. Contabilizado en `items_unconverged`.
- La memoria dejaba coexistir dos versiones contradictorias del mismo hecho y
  se las inyectaba juntas y mudas al modelo, que no podia sino contradecirse;
  medido en laboratorio el 2026-08-21 sobre una sesion real de cuatro turnos,
  donde una alucinacion del modelo se persistio como `episodic/facts` con
  confianza 1 y fue premisa de los turnos siguientes. Causa: el dedup detectaba
  redundancia (similitud >= 0.92 refuerza) pero no contradiccion. Ahora, cuando
  el interlocutor dice algo muy proximo a lo que el modelo afirmo, el candidato
  del modelo queda anotado con un enlace `contradicted_by`, y el recall lo
  etiqueta y lo despriorza al recortar. NO se retira: la separacion medida entre
  contradecir y compartir tema es de centesimas
  (`local/lab/2026-08-22_banda_de_conflicto.md`), y ese margen no sostiene una
  accion destructiva sobre la memoria. Banda configurable por
  `conflict_threshold` (calibrado en 0.70 con `bge-m3`).
- Retrabajo de Fase 8 tras la primera instalacion limpia: las tres migraciones
  SQL tienen una unica copia dentro de `ianest_extended`, viajan como datos del
  wheel y se resuelven con recursos del paquete tanto en instalaciones editables
  como reales. Una prueba construye e instala el wheel y falla si no puede leer
  las migraciones desde el paquete instalado.
- El PostgreSQL provisionado declara `restart: unless-stopped`, y el instalador
  comprueba el acceso de red al indice de paquetes antes de invocar la
  instalacion de `pip`, con un error propio sin volcar sus reintentos. Impacto de
  version: correccion compatible (PATCH); la fase sigue abierta hasta verificar
  el despliegue en una maquina real.

## [0.1.1] - 2026-08-20

### Anadido
- `prompt.stream` y `reasoning.stream` pasan de reenviadas a sobreescritas con el
  mismo enriquecimiento upfront de `prompt.run`: recuperan y componen antes de
  abrir el SSE, retransmiten cada evento del core sin alterar su forma y
  acumulan la respuesta en paralelo solo para el write-back. El primer evento
  no espera al cierre del flujo. CLI y REST consumen el mismo servicio; MCP las
  mantiene fuera por forma del protocolo. `task.stream` sigue reenviada porque
  el core no acepta un plan suministrado en esa capacidad. Adicion compatible:
  PATCH en la serie pre-1.0.
- El write-back de streaming se ejecuta solo tras `done` y cierre limpio. Un
  error o una desconexion no persiste una respuesta parcial y deja telemetria
  `error` o `interrupted`. En `reasoning.stream`, `source_trace_id` conserva el
  `request_id` del core. En `prompt.stream` queda a nulo como limitacion
  conocida, porque ese flujo no publica su trace; nunca se sustituye por el
  identificador propio de extended.

## [0.1.0] - 2026-08-20

Primer contrato publicado de la capa. `docs/EXTENDED_CONTRACT.md` pasa a
`activo`: lo que declara es promesa, no objetivo.

Depende de `ia_nest_core >=0.4 <0.5`, re-verificado en vivo contra el tag
`v0.4.0` con el resultado escrito en `docs/DEPENDENCIAS.md`, como exige el
deber de re-verificacion del registro de capas.

### Anadido
- Fase 7c-2: piel MCP del contrato uniforme. Registra herramientas con el nombre
  exacto de la capacidad y genera sus esquemas desde el catalogo (tipo,
  obligatoriedad y valores admitidos). Las propias y sobreescritas se enumeran
  siempre; las reenviadas, solo desde una cache valida del catalogo del core. El
  arranque no toca la red y, sin cache, sirve lo propio declarando el hueco
  ajeno. Todas las invocaciones usan `ExtendedService`; el reenvio conserva
  respuestas JSON opacas y los errores mantienen `type` y `origin`. Streaming
  queda fuera y se declara mediante la proyeccion MCP nula del catalogo y las
  instrucciones del servidor. Nuevo comando `ianest-extended-mcp` y extra
  opcional `ianest-extended[mcp]`. Impacto de version: adicion compatible
  (patch en la serie pre-1.0; el tag lo decide el usuario).
- Fase 7c-1: piel REST del contrato uniforme, con rutas declaradas para las
  capacidades propias y sobreescritas sobre el mismo `ExtendedService` de la
  CLI, y reenvio generico de cualquier otra ruta derivando la capacidad del
  path SIN consultar el catalogo. El proxy conserva campos JSON desconocidos,
  retransmite SSE evento a evento y propaga errores ajenos con su `type`,
  `origin` y codigo HTTP. Escucha configurable mediante
  `IANEST_EXTENDED_REST_HOST`/`REST_PORT`, solo en `127.0.0.1:8001` por defecto,
  sin autenticacion. MCP permanece fuera (Fase 7c-2). Impacto de version:
  adicion compatible (patch en la serie pre-1.0, docs/VERSIONADO.md).
- D4: `IANEST_EXTENDED_MEMORY_MIN_SIMILARITY` gatea por similitud la
  recuperacion de memoria, y SOLO en `episodic` (ruido reciente, alto volumen
  y vida corta). `semantic` queda fuera a proposito -lo consolidado ya paso un
  juicio de promocion episodic -> semantic, que es un filtro mejor que un
  umbral de distancia coseno-, igual que `dialog` (continuidad de la
  conversacion, no pertinencia tematica) y los delegados `identity`,
  `principles` y `safety` (inyeccion incondicional por diseno, ADR 0002). El
  suelo gatea la similitud, nunca la relevancia compuesta -que sigue
  ordenando-: son las mismas dos preguntas que separo D1 para el RAG. Su
  default conservador `0.10` es PROVISIONAL y sin medida: se eligio para no
  silenciar una memoria pertinente; su calibracion se hara junto a D5 cuando
  haya corpus y uso reales. Impacto de version: adicion compatible (patch en la serie
  pre-1.0, docs/VERSIONADO.md).
- Retrabajo de la herencia de parametros (hallado al ejercer la implementacion
  contra un core real, antes de publicar contrato): un parametro del catalogo
  cuyo nombre colisiona con una bandera que la capa ya posee -identidad,
  enriquecimiento o salida- ya NO rompe la construccion del parser; la
  bandera propia gana y no se redeclara, y su ayuda dice que la gobierna la
  capa. Regla unica derivada del dato, no una lista de excepciones. Ademas, el
  catalogo remoto que el parser usa para ofrecer banderas ahora se CACHEA como
  estado local (no versionado): `capability.list` lo refresca como efecto de
  consultar el core en vivo, y construir el parser es siempre una operacion
  local -nunca toca la red, ni siquiera con el core alcanzable-. Sin cache o
  con una cache de un core distinto del configurado, la capa degrada: lo
  propio conserva sus banderas y lo ajeno se invoca por `--param`. Impacto de
  version: ninguno, mismo contrato aun sin publicar.
- La CLI deriva las banderas de los parametros declarados por el catalogo,
  incluidos tipo, elecciones, defecto y metavar. Las entradas CLI declaradas
  leen un unico JSON y reparten sus campos; colisionar con una bandera explicita
  es error tipado. `task run --plan-file` acepta un plan del operador: con
  enriquecimiento activo enriquece sus subtareas sin llamar a `task.plan`, y con
  `--no-enrich` lo reenvia intacto. `--verbose` y `--quiet` de `task run`, y el
  render de lo reenviado, siguen fuera de alcance. Impacto de version: ninguno,
  porque aun no hay contrato publicado ni primer tag.
- Catalogo declarativo propio y `capability.list` sobreescrita: la capa obtiene
  el catalogo del core en ejecucion y lo fusiona sin copiarlo, sustituye las
  capacidades sobreescritas, preserva intactas las reenviadas y anade
  `provenance`, `extended_version` y `core_version`. Con el core inalcanzable
  devuelve lo local junto a un error tipado. La CLI deriva su ayuda del catalogo
  y conserva la invocacion generica sin exigir descubrimiento; construir el
  parser sigue sin red. REST y MCP permanecen nulos y las capacidades previstas
  no se anuncian. Impacto de version: ninguno, porque aun no hay contrato
  publicado ni primer tag.

### Corregido
- Defecto preexistente en el banco de pruebas de PostgreSQL, hallado al
  verificar D4: la base de pruebas no se limpiaba entre ejecuciones ni entre
  pruebas y acumulaba filas (llego a superar cien engramas de pasadas
  anteriores), asi que el resultado dependia de la historia de ejecuciones.
  `tests/conftest.py` ahora vacia las tablas de datos (`engrams`, `entities`,
  `memory_links` y, si estan migradas, las de RAG) antes de cada prueba que usa
  `postgres_store`; `memory_types` no se toca porque es esquema, no datos.
  Ejecutar la suite dos veces seguidas da el mismo resultado, y una prueba
  aislada da lo mismo que dentro de la suite. Impacto de version: ninguno, solo
  pruebas.

### Cambiado
- El suelo de relevancia del RAG (`rag_min_score`) pasa de 0.38 a **0.50**. El
  motivo es una medida, no una preferencia: al ampliar el corpus, la banda de
  puntuaciones del ruido subio y 0.38 volvia a admitirlo. El hallazgo que conviene
  no perder es que **ese umbral escala con la ANCHURA del corpus** -a mas corpus,
  mas ocasiones de un mejor-match espurio-, asi que no es una constante y se
  remide cuando el corpus crece. La evidencia de la calibracion es dato de
  laboratorio y no se versiona.

### Anadido
- Implementacion de la Fase 7b: `reasoning.run` sobreescrito con el mismo
  vertical upfront de `prompt.run`, y `task.run` enriquecido por subtarea via
  `task.plan` + `task.run(plan)`. El round-trip copia el objeto de plan, elimina
  solo `params`, preserva campos hermanos y estructurales desconocidos, y edita
  solo `plan[i].prompt`; `requirements` y `effort` viajan intactos. El RAG se
  gatea por el dominio ya resuelto de cada subtarea y aplica `rag_max_tokens`
  por subtarea; la memoria se inyecta una sola vez en el prompt superior para
  COMBINE/EVALUATE. Incluye CLI interina, telemetria `reasoning.run`/`task.run`,
  pruebas falsables y medida reproducible de tres brazos en `local/lab/`.
  `task.run --no-enrich` no planifica y conserva la re-planificacion del core.
  `task.stream` y `prompt.stream` siguen reenviados sin enriquecer. Implementado
  contra el `main` v0.4 del core (`705941e`), aun sin tag; no se mueve
  `docs/DEPENDENCIAS.md`. Impacto de version: ninguno, porque aun no hay contrato
  publicado ni primer tag.

### Corregido
- Retrabajo de la Fase 7b: `task.plan` y `task.run` usan el nuevo plazo de
  orquestacion `IANEST_EXTENDED_TASK_TIMEOUT_SECONDS` (600 s por defecto), sin
  alargar el timeout de inactividad de `prompt.run`; la telemetria RAG por
  subtarea declara `domain` y `corpora`; y la medida de tres brazos pasa de
  `local/lab/` a `tools/lab/` para viajar con el despliegue. Impacto de version:
  ninguno, porque aun no hay contrato publicado ni primer tag.
- `docs/PLAN.md` retira dos premisas caducadas: `task.plan` ya esta entregado en
  el `main` del core, y desde v0.4 `task.run` devuelve JSON mientras el SSE vive
  en `task.stream`.
- El CLI deja de exigir conocer una capacidad para poder invocarla (ADR 0011,
  punto 11). Un `GRUPO ACCION` que la piel no declara se resuelve como la
  capacidad `grupo.accion` y se reenvia por el camino generico del servicio, con
  las mismas banderas de cuerpo (`--prompt`, `--param`, `--payload`), la misma
  regla de verbo (sin cuerpo, GET; con cuerpo, POST), el mismo tratamiento de
  streaming y `--json`, y los mismos codigos de salida. Asi, una capacidad nueva
  del core es invocable sin editar esta capa, que era el invariante de meta
  ADR 0007 incumplido en la piel. Un grupo conocido se comporta exactamente como
  antes, y la ayuda de primer nivel declara la invocacion dinamica.
  `capabilities.py` se queda, pero cambia de papel: ya no habilita nada, solo
  aporta la AYUDA enriquecida de lo que conocemos, y desaparece cuando el core
  entregue `capability.list` (`extended CR-0002`). Sin cambios en el servicio, el
  sustrato, la memoria ni el RAG. Impacto de version: ninguno.

### Anadido
- Enmienda al ADR 0011 (puntos 9-11): el catalogo de capacidades se DECLARA por
  capa y se FUSIONA en tiempo de ejecucion, nunca se copia. Ninguna piel puede
  exigir conocer una capacidad para poder invocarla: conocerla solo sirve para
  dar mejor ayuda. Motivo: la Fase 7a dejo lo reenviado como lista escrita a
  mano, lo que obligaba a editar esta capa cada vez que el core anadiera una
  capacidad -aunque el servicio ya la alcanzase-, incumpliendo el invariante de
  meta ADR 0007 en la piel. La regla correcta: una feature del core puede
  REQUERIR trabajo aqui para aprovecharla, nunca obligar a COPIAR su codigo.
  `extended CR-0002` sube de comodidad a mecanismo. Impacto de version: ninguno.
- Seccion "Deuda de diseno declarada" en `docs/PLAN.md` con tres hallazgos del
  laboratorio, cada uno con su disparador: D1, la recuperacion RAG no tiene suelo
  de relevancia y devuelve top-k por malo que sea el parecido; D2, el filtro de
  dominio excluye tambien las memorias SIN dominio, que son neutras y no
  incompatibles, de modo que preguntando con dominio el ente olvida a su
  interlocutor; y D3, la identidad como fuente conmutable para poder medir su
  efecto. Impacto de version: ninguno.
- Regla de uso de `user_id` en `docs/FORMA_ENRIQUECIMIENTO.md`: identifica al
  INTERLOCUTOR, no a la instancia; cada agente que lance prompts contra la
  instancia usa su PROPIO `user_id`, tambien al verificar o probar. Reusar el del
  operador mezcla trafico de prueba con su memoria real y anula la segmentacion.
  Se precisa ademas que `user_id` SEGMENTA pero no AUTORIZA: la autoridad la dan
  el principal (ADR 0002) y el GRANT del motor (ADR 0010).
- `docs/ALCANCE.md`: la autenticacion de los interlocutores queda FUERA de esta
  capa por ahora -no es enriquecimiento; la capa consume la identidad afirmada,
  no la prueba-. El concern y sus dos hogares candidatos, uno de ellos esta misma
  capa, quedan registrados sin decidir en `ia_nest_meta/docs/CAPAS_FUTURAS.md`.
  Impacto de version: ninguno.
- `docs/handoff/fase_7a_brief.md`: brief de implementacion de la Fase 7a para el
  agente codificador (composition-root perezoso, fachada con reenvio generico y
  sobreescritura de `prompt.run`, regla tipado/opaco, timeout de conexion mas
  inactividad, superficie de parametros, errores tipados con los codigos de
  salida del core, piel CLI instalable y retirada de los cuatro harnesses).
  Catorce criterios de aceptacion falsables, los tres primeros el test de
  conformidad de meta ADR 0007 desglosado. Impacto de version: ninguno.
- Tres decisiones de superficie de la Fase 7a (ADR 0011, puntos 6-8): migracion
  explicita en lugar de migrar en cada arranque; identidad con defaults, con
  `session_id` generado y RECORDADO si no se indica -no uno nuevo por invocacion,
  que romperia la continuidad de `dialog`-; y `--domain` unificado como
  divergencia deliberada respecto al core, que separa ruteo y etiqueta.
- `extended CR-0002` (propuesto, destino core): descubrimiento de capacidades en
  REST (`capability.list`). Motivo verificado contra el codigo del core: el
  reenvio generico del contrato uniforme lo cumplen REST (once rutas proxeables)
  y MCP (capacidades registradas con nombre), pero NO el CLI, que necesita
  enumerar subcomandos para construir su ayuda. Impacto previsto en el core:
  minor. No bloquea la Fase 7a, que arranca con lista estatica.
- Verificacion del reenvio generico y del streaming (Fase 7, paso previo al
  brief): `POST /task/run` del core es SSE siempre, luego sobreescribirlo obliga
  a hablar streaming y este no se difiere; el timeout unico pasa a conexion mas
  inactividad; y el cliente actual, que valida campo a campo la respuesta del
  core, re-declara su contrato en codigo. Regla resultante: tipado donde se
  sobreescribe, opaco donde se reenvia.
- Interfaz de consumo de la capa como CONTRATO UNIFORME (ADR 0011, aplicando
  meta ADR 0007): reenvio generico de lo que no se enriquece, sobreescritura de
  `prompt.run`/`reasoning.run`/`task.run` conservando su forma, y capacidades
  propias `memory_type.*`/`memory.*`/`knowledge.*`. Motivo: la implementacion
  hasta la Fase 5c habia derivado a un catalogo propio y MENOR que el del core
  (solo `prompt.run`), de modo que subir de capa hacia perder capacidades.
- `docs/EXTENDED_CONTRACT.md` (estado `propuesta` hasta el primer tag) y
  `docs/VERSIONADO.md`: declarado QUE cuenta como contrato publico de esta capa.
  Cierra el PENDIENTE de `docs/DEPENDENCIAS.md` que impedia cortar el primer tag.
  Lo que se versiona de lo ajeno es la GARANTIA de reexponer el contrato del core
  sin alterarlo, no su catalogo: una rotura del core mueve el rango, no la
  version de esta capa. Sin tag cortado; impacto de version: ninguno.

### Cambiado
- Fase 7 del PLAN reescrita en cuatro rebanadas: 7a servicio con contrato
  uniforme y CLI de operador (con el test de conformidad de meta ADR 0007 como
  criterio de salida falsable), 7b `reasoning.run` y `task.run` (espera a
  `task.plan`, core v0.4), 7c REST y MCP, 7d primer tag. La Fase 7a deja de ser
  "consolidar los cuatro harnesses en un CLI espejo". Riesgo declarado y no
  supuesto: el reenvio generico de streaming puede no ser barato; se verifica
  antes de implementar.
- `docs/FORMA_ENRIQUECIMIENTO.md` alineado: describe COMO se enriquece; QUE se
  expone vive en el contrato.
- `AGENTS.md` incorpora al orden de lectura la arquitectura de capas del ente
  (`ia_nest_meta/docs/ARQUITECTURA_DE_CAPAS.md`, meta ADR 0007): contrato
  uniforme entre capas, reenvio por defecto y sobreescritura por excepcion,
  extension aditiva y clientes escritos contra el contrato. Gobierna la interfaz
  de consumo de esta capa; el reencuadre de la Fase 7 se registra al reconciliar
  la Fase 7a. Sin cambios en el contrato publico; impacto de version: ninguno.

### Anadido
- Implementacion de la Fase 5c: CLI de operador `knowledge status`, `suggest`,
  `confirm` y `reject`; completitud contra `domain.list`; propuestas de corpus
  agregado via `domain.route` con umbral configurable; confirmacion que habilita
  el gate existente; y rechazo protegido de vinculos manuales o confirmados.
  Incluye configuracion, errores tipados y cuatro grupos de aceptacion PostgreSQL
  con skip explicito sin DB local. No implementa `knowledge maintain`,
  clasificacion por chunk, roles/grants ni cambios en memoria/core. Sin cambios
  en el contrato publico; impacto de version: ninguno.
- Implementacion de la Fase 5b: migracion N:M `rag_corpus_domains` con
  procedencia y confirmacion, migracion sin perdida del dominio unico anterior,
  ingesta manual opcional y mult dominio validada contra `domain.list`, y gate
  de recuperacion solo por vinculos confirmados. Incluye los cinco grupos de
  aceptacion PostgreSQL con skip explicito sin DB local. Auto-etiquetado,
  `knowledge maintain`, completitud y roles/grants siguen fuera. Sin cambios en
  el contrato publico; impacto de version: ninguno.
- Aislamiento de recursos y least-privilege (ADR 0010): autoridad de escritura en
  dos niveles -principal en codigo (ADR 0002) + GRANT del motor (pared dura que no
  confia en el codigo)-. Stores segmentados por confianza con roles least-privilege;
  extended read-only sobre el yo protegido y el conocimiento; solo conscience
  escribe lo protegido; conocimiento aislado (curacion operador hoy / conscience
  guardian futuro). Separable desde el dia uno para escalar aislamiento sin
  reescribir (rol -> schema -> base -> instancia, DMZ). Con diagrama. Impacto: ninguno.
- Enmienda ADR 0007: conscience ANADE una capa reflexiva, no sustituye la mecanica
  de extended (opcion A); frontera de confianza candidato->confiable (cortafuegos
  de inyeccion), endurecida por ADR 0010.
- Enmienda ADR 0009: la incorporacion de conocimiento esta gobernada por
  supervision (operador hoy, conscience guardian futuro), sin que el conocimiento
  sea la identidad del ente; store aislado (ADR 0010).
- Modelo de datos de conocimiento por dominio (ADR 0009, Fase 5b): relacion N:M
  dominio<->corpus a nivel de corpus via tabla `rag_corpus_domains` con
  `source`/`confirmed` (auto-etiquetado como propuesta, confirmacion del operador;
  la recuperacion gatea por vinculos confirmados). Premisa: el conocimiento es
  externo (ops), no el yo del ente. Con diagramas (mermaid). Workflow y ampliacion
  del lab pendientes de reconciliar. Impacto: ninguno.

### Corregido
- H1 del e2e de Fase 5: el dominio explicito se valida una vez por ejecucion
  contra `domain.list` antes de recuperar o invocar `prompt.run`; un dominio
  desconocido produce `InvalidCoreDomainError` con el catalogo valido. El
  dominio auto-ruteado se usa para gate y ruteo, mientras ausencia o `general`
  mantienen recuperacion global y omiten el dominio de `prompt.run`. Sin
  cambios en el contrato publico; impacto de version: ninguno.

### Anadido
- Implementacion de la Fase 5, camino RAG upfront: migracion separada para
  `rag_corpora`/`rag_chunks`, ingesta idempotente de `.txt`/`.md`, recuperacion
  vectorial con gate opcional de dominio, `domain.route` configurable,
  composicion conservadora dentro del presupuesto, telemetria `rag.retrieve`,
  configuracion/instalador y pruebas con stub del core y `FakeEmbedder`.
  `task.run`/`task.plan`, el core y las tablas de memoria quedan intactos. Sin
  contrato publico cortado; impacto de version: ninguno.
- Forma del RAG operativo (ADR 0008) y brief de la Fase 5 camino upfront: RAG
  como subsistema hermano (no tier), tablas `rag_corpora`/`rag_chunks` en el mismo
  motor, ingesta curada, recuperacion con gate de dominio (D1) y dominio explicito
  o via `domain.route` (D2), presupuesto duro (D3), integracion upfront en
  `prompt.run`. Per-subtarea diferido a `task.plan` (core v0.4). Impacto: ninguno.

### Cambiado
- Compatibilidad con core v0.3.0 VERIFICADA EN VIVO en lab: redespliegue del
  core por pull (v0.2.0 -> v0.3.0), config valida, `prompt.run` con forma intacta,
  y e2e de continuidad de memoria (sesion A escribe, sesion B recupera via
  bge-m3). Pin de `DEPENDENCIAS.md` subido a `ia_nest_core >=0.2 <0.4`. Impacto de
  version: ninguno.
- Core v0.3.0 liberada: PLAN Fase 5 sale de PARADA (CR-0001 resuelto, core
  ADR 0040, REFORMULADO a `task.plan`+`task.run` con plan; objetivo core v0.4, no
  entregado). RAG upfront desbloqueado; per-subtarea espera a `task.plan`.
  `DEPENDENCIAS.md`: v0.3.0 compatible a nivel de contrato (solo la toca ADR 0043,
  que no altera `prompt.run`); el pin sube a `<0.4` tras el e2e contra un v0.3
  desplegado en lab. Impacto de version: ninguno.

### Anadido
- Proceso de Change Request entre capas (`docs/change_requests/README.md`,
  PROPUESTA a elevar como doctrina del ente en el core): canal formal
  propone/dispone para pedir cambios de contrato a una capa superior, sobre el
  grafo de dependencias SemVer (core ADR 0032).
- CR-0001 (propuesto, destino core): checkpoint de enriquecimiento por subtarea
  en `task.run`, para RAG per-subtarea token-eficiente sin reabrir la frontera
  enriquecimiento/herramienta (core ADR 0031). Impacto previsto en el core: minor.

### Cambiado
- Fase 5 (RAG) en PARADA hasta resolver CR-0001: no se construye sobre una
  decision de core no resuelta. `AGENTS.md` incluye `docs/change_requests/` en el
  orden de lectura.

### Anadido
- Implementacion de la Fase 4: evento tipado `ConsolidationEvent`, ejecutor
  transaccional con autoridad, lineage y archivo sin borrado, y CLI
  `python -m ianest_extended.maintain` con promocion literal
  `episodic` -> `semantic`, archivado de `dialog`, telemetria y `--dry-run`.
  Umbrales configurables documentados en `.env.example` y cinco criterios de
  aceptacion PostgreSQL con skip explicito sin DB local. Sin contrato publico
  cortado; impacto de version: ninguno.
- Diseno de la fase 4 (ADR 0007): consolidacion mecanica del gradiente estricto.
  `maintain` archiva `dialog` fuera de ventana y promociona `episodic` ->
  `semantic` de forma literal (umbrales de recencia y merito), con lineage y sin
  borrado, via un ejecutor de `memory.consolidation` que la capa ejerce hoy
  (dogfooding) y que conscience reusara. Sintesis multi-item con modelo diferida
  con nombre. `docs/handoff/fase_4_brief.md` para el codificador. Impacto: ninguno.

### Corregido
- Hallazgos H1/H2/H3 del e2e de Fase 3: prompt y parser de extraccion
  resistentes a valores copiados, fences y texto colgante; PostgreSQL de pytest
  aislado en `<dbname>_test`; e ID del modelo de extraccion documentado y
  mostrado desde `model.list` cuando el core local responde. Sin cambios en el
  contrato publico; impacto de version: ninguno.

### Anadido
- Vertical minimo de memoria de la Fase 3: configuracion
  `IANEST_EXTENDED_*`, clientes tipados para `prompt.run` y embeddings de
  Ollama, recall compuesto con presupuesto, write-back destilado con
  dedup-refuerzo, telemetria JSONL, CLI `ianest_extended.chat`, extension
  idempotente del instalador, reconciliacion sin borrado de la dimension
  vectorial configurada y pruebas con stub HTTP local/FakeEmbedder. Los casos
  de aceptacion PostgreSQL quedan automatizados con skip explicito cuando no
  hay DB. Sin contrato publico cortado; impacto de version: ninguno.
- Diseno de la fase 3 reconciliado: `docs/POLITICA_WRITEBACK.md` (dialog crudo
  por diseno, episodic destilado con confianza y dedup-refuerzo, menciones sin
  resolver, composicion del recall con numeros de arranque) y ADR 0006 (modelos
  de apoyo: embeddings `bge-m3` 1024d y extraccion `qwen2.5:7b`, ambos
  configurables por instalacion via instalador; mitigaciones de sesgo).
  `docs/handoff/fase_3_brief.md` para el codificador. Impacto: ninguno.
- Validacion de laboratorio de la fase 2 (openSUSE Tumbleweed, docker real):
  `install.sh` ejecutado dos veces (idempotente), pytest 16/16 sin skips contra
  postgres+pgvector (criterios A1-A5 del brief); DB solo en loopback. El
  postgres de la cantera deprecada (`ia_nest_postgres`) queda al margen: esta
  capa usa su propio contenedor.
- Instalador de desarrollo `install.sh`, idempotente y orientado primero a
  openSUSE: seleccion Docker/Podman, PostgreSQL+pgvector con espera de salud,
  `.venv` Python 3.13, instalacion editable y pytest; incluye modos
  `--assume-yes`, `--skip-db` y `--skip-tests`, documentacion de uso y handoff
  de Fase 2b. Sin cambios en el contrato publico; impacto de version: ninguno.
- Sustrato de memoria de la Fase 2: paquete Python con ports `MemoryStore` y
  `Embedder`, registro y validacion V1-V4 con errores tipados, autoridad de
  escritura por principal, `FakeEmbedder`, adaptador postgres+pgvector,
  migracion parametrizada, semillas del roster, recuperacion multi-espacio,
  archivo sin borrado, entorno postgres local y pruebas A1-A5. Sin contrato
  publico cortado; impacto de version: ninguno.
- Semilla del repo: contexto, alcance, dependencias, genesis (ADR 0001) y plan
  inicial de fases en borrador (memoria primero).
- Clases de memoria y autoridad de escritura (ADR 0002): la memoria es un registro
  de tipos declarados; clases estrictas (dueno extended) vs delegadas (dueno otra
  capa, p. ej. conscience). Autoridad de escritura por capacidad, lectura uniforme,
  dogfooding del contrato y costura de consolidacion (`memory.consolidation`,
  conscience pide / extended ejecuta). Reescribe la Fase 2 del PLAN. Sin contrato
  publico cortado todavia (se corta en Fase 7); impacto de version: ninguno.
- `docs/VISION_MEMORIA.md`: el fin de la memoria (yo simulado, continuo y
  evolutivo), la frontera sustrato/juicio con conscience, las funciones de memoria
  deseadas heredadas de la cantera `ia_nest`, y la separacion entre memoria y
  conocimiento (RAG). Anadido al orden de lectura de `AGENTS.md`.
- `docs/FORMA_ENRIQUECIMIENTO.md` (Fase 1): forma no congelada del enriquecimiento,
  mapeo identidad->clave y politica de composicion/presupuesto. En el orden de
  lectura de `AGENTS.md`.
- Modelo de relevancia y gradiente de tiers (ADR 0003): recuperacion por ranking
  ponderado (recencia, similitud, estabilidad, score; dominio como filtro); un
  tier se define por su vector de pesos, no por una ventana. Gradiente de tres
  tiers (conversacional / episodica / semantica); corto/medio/largo se disuelven
  en la curva de recencia y el namespace `tasks`. Motor `postgres + pgvector`.
  Numeros de arranque configurables. Impacto de version: ninguno.
- Entities y modelo multi-espacio (ADR 0004): cada espacio de cercania en su
  representacion natural (semantico denso; temporal y entidades exactos; dominio
  como filtro); entities como tercer patron (perfil mutable versionado + registro
  de `entity_id` + etiquetado `entity_refs` mecanico en write-back; perfilar es
  juicio de conscience). Asociacion graduada y temporal registradas y diferidas.
  Vocabulario: engrama. Impacto de version: ninguno.
- `docs/ROSTER_MEMORIA.md`: roster de tipos de memoria de la Fase 2 (estrictos
  `dialog`/`episodic`/`semantic`; delegados `entities`/`identity`/`principles`/
  `safety`; `ops` y RAG fuera), RECONCILIADO. En el orden de lectura de
  `AGENTS.md`.
- Disolucion de `historic` (ADR 0005, supersede parcial de la enumeracion del
  ADR 0002): personalidad = `identity` + `principles` con inyeccion permanente;
  la evidencia formativa son `evidence_refs` desde delegadas hacia engramas (el
  archivo es direccionable por no-borrado); relato formativo por relevancia
  diferido. Regla de aliasing precisada: coincidir en TODOS los ejes. Impacto de
  version: ninguno.
- `docs/handoff/fase_2_brief.md`: brief de implementacion de la fase 2 para el
  agente codificador (esquema postgres+pgvector, ports, registro y validacion
  V1-V4, autoridad de escritura, recall multi-espacio, semillas del roster,
  blanco de aceptacion A1-A5). Impacto de version: ninguno.

### Cambiado
- PLAN reconciliado en sus fases de memoria: Fase 1 pasa a FORMA no congelada
  (mas mapeo identidad->clave y politica de composicion/presupuesto), Fase 3
  abandona el nombre `read_context` (retirado del core, ADR 0035) y suma politica
  de write-back y telemetria propia, Fase 4 queda como MECANISMO de consolidacion
  (el juicio es de conscience) y Fase 7 cubre tambien el consumo de la GUI.
- `ALCANCE.md`: extended hospeda y sirve la memoria de comportamiento/identidad,
  pero no la escribe (delegadas, ADR 0002); el juicio de consolidacion es de
  conscience.
- `AGENTS.md`: convencion de texto explicita (ASCII puro, sin acentos ni `n` con
  virgulilla) e identificadores en ingles snake_case (core ADR 0016).
- Reconciliadas las tres senalizaciones de la entrega de fase 2:
  `FORMA_ENRIQUECIMIENTO.md` corregida (`user_id` vertebra los tipos
  experienciales, no los delegados globales/entidad; `namespace` en clave salvo
  `dialog`), namespaces homonimos de las delegadas ratificados en el roster
  (`entities`/`principles`/`safety`), e interpretacion del criterio A4 sobre
  senales ratificada.
