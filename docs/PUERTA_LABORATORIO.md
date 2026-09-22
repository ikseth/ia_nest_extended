# Puerta de laboratorio de ia_nest_extended

Estado: reconciliado 2026-09-12. Declarado ANTES de medir.
Version: 1.2 - 2026-09-21 (anade L7, memoria conversacional con referente,
derivada de un hilo real; L1 y L3 se precisaron el 2026-09-12 al implementar el
script). Observacion del 2026-09-22 sobre L4a al final, SIN reconciliar: el
criterio vigente sigue siendo el de 1.2.

Aplica `ia_nest_meta` ADR 0010 (regla de la puerta de laboratorio): la regla
dice que la puerta existe y que forma tiene; este documento fija el
procedimiento de ESTA capa. El script que la ejecuta es codigo y se versiona;
sus resultados son evidencia y viven en `local/lab/`, fuera de git.

## Que certifica

Que un despliegue NATURAL de la capa se comporta como promete su contrato,
medido por la superficie que consumen las capas de encima (REST).

Natural significa: el instalador del core y el de esta capa, un tag de cada
uno y sus ficheros de parametros declarados. Ningun paso a mano.

## Regla de clasificacion

Todo fallo que la puerta encuentre se clasifica con una sola pregunta:

- **se arregla cambiando un valor de los ficheros de parametros**: es AJUSTE DE
  CONFIGURACION. Se decide, se anota en el fichero y no mueve version;
- **exige tocar codigo, instalador o hacer un paso a mano**: es FALLO DE CODIGO.
  Va por PR y tag. Nunca se parchea en la maquina.

Un paso a mano en la maquina invalida la pasada: el resultado no describe un
despliegue natural.

## Precondiciones: si alguna falla, la pasada es NULA

Nula no es NO PASA: dice que no se midio el producto.

- P1. La capa se instalo con `deploy/setup.sh` desde un tag, y la
  `extended_version` que publica `capability.list` coincide con ese tag.
- P2. Los servicios arrancaron DESPUES de la ultima instalacion. Actualizar el
  arbol no reinicia un proceso.
- P3. El core pasa su propio smoke en la misma maquina y el mismo dia.
- P4. Los ficheros de parametros usados son los declarados (huella registrada
  en la evidencia).

## Lineas

Cada SONDA usa un `user_id` propio -uno por linea y por repeticion, derivado
del identificador de la pasada- y nunca el del operador
(`docs/FORMA_ENRIQUECIMIENTO.md`). No basta con una identidad por pasada: la
memoria episodica es de ambito usuario, asi que compartirla hace que las sondas
se contaminen entre si. Se aprendio midiendo, el 2026-09-12: una sonda respondia
con el testigo de otra.

**El oraculo es externo al sistema (regla 5 de meta ADR 0010).** Cada sonda
lleva un TESTIGO fijado antes de ejecutar: una cadena aleatoria o un dato
dicho por el interlocutor que el modelo no puede conocer por su cuenta. La
comprobacion es lexica: presencia del testigo correcto y ausencia del
incorrecto. Ninguna linea usa un modelo del propio sistema como juez.

| Linea | Que se mide | Pasa | No pasa |
|---|---|---|---|
| L1 Forma | `setup.sh` con `VERIFY=strict`; `capability.list` sin degradacion; `knowledge.status` responde | codigo 0 y ninguna degradacion | cualquier otro |
| L2 Continuidad | el interlocutor dice un testigo aleatorio en la sesion A; se pregunta por el en la sesion B | `memory.recall` de B devuelve el testigo con `stated_by=user`; lo que responda el modelo se registra pero no decide | el recall no lo devuelve |
| L3 Procedencia | se siembra por `memory.write` un candidato con `stated_by=model`; el interlocutor dice lo contrario | el contexto del turno siguiente etiqueta el candidato como del modelo y lo coloca detras de la version del usuario; la anotacion de conflicto se registra con su tasa, pero no decide | sin etiqueta o en otro orden |
| L4a Coherencia, correccion de un candidato del modelo | hilo de cuatro turnos sobre L3; la ultima pregunta pide el dato | la respuesta contiene el testigo del usuario y no el del modelo | contiene el del modelo, o ninguno |
| L4b Coherencia, autocorreccion del interlocutor | "la reunion es el martes" ... "perdona, es el jueves" ... "que dia es?" | contiene "jueves" y no "martes" | contiene "martes", o ninguno |
| L5 RAG por dominio | por cada dominio con corpus confirmado, una pregunta redactada como la haria una persona, SIN mirar el corpus | la recuperacion devuelve al menos un fragmento, y se registra el nombre de corpus que el contexto publique | no recupera nada |
| L5r Ruido | cortesia sin dominio ("hola", "gracias", "que recuerdas de mi") | la recuperacion RAG devuelve cero | recupera algo |
| L6 Repeticion | segunda ejecucion de `setup.sh` sobre lo instalado | L1-L3 siguen pasando y los datos no se duplican | cualquier otro |
| L7 Memoria conversacional con referente | hilo de cuatro turnos en el que el interlocutor puntua cosas por ORDINAL -"la primera un 6"- y al final pregunta por una concreta | la respuesta trae la puntuacion correcta de esa pieza y ninguna de las que nunca se puntuaron | trae otra puntuacion, o ninguna |

Repeticion: L2, L3, L4a, L4b, L5 y L7 con n = 3. Una linea PASA con 3 de 3;
con menos, NO PASA y el reparto se anota.

**Por que L2 no juzga la respuesta del modelo** (reconciliado el 2026-09-12, al
medir): exigirla convierte la linea en una prueba de fidelidad de transcripcion.
Medido dos veces, el modelo respondia `Xanthe` a un testigo `Xanthe74bad8d4b3`
mientras el recall lo entregaba entero y con su procedencia. Lo que esta capa
promete es ENTREGAR la memoria, no que el modelo la copie literalmente; medir lo
segundo hace que la puerta suspenda a la capa por algo que no gobierna. La
respuesta sigue en la evidencia, porque un cambio de comportamiento ahi importa
aunque no decida.

L4a y L4b si juzgan la respuesta, y con razon: ahi lo que se mide es si el
CONTEXTO compuesto induce o no una contradiccion, y eso solo se ve en lo que el
modelo termina diciendo.

**Por que L3 no exige la anotacion de conflicto** (reconciliado el 2026-09-12,
al cruzar dos ejecutores): la etiqueta de procedencia y el orden son mecanismo
puro y salieron correctos en las NUEVE repeticiones medidas. La anotacion salio
en 6 de 9, y su ausencia tiene causa conocida -ver ADR 0013, enmienda del
2026-09-12-. Se separan porque miden cosas distintas: la etiqueta es lo que la
capa gobierna por completo; la anotacion depende de una banda de similitud y de
donde el extractor coloque cada version.

Y hay un dato que decide el reparto: **L4a paso 3 de 3 en las tres pasadas,
tambien cuando la anotacion no disparo**. Lo que sostiene el comportamiento es
marcar la procedencia; la anotacion es la segunda capa. Exigirla como criterio
haria suspender a la puerta por un refuerzo, no por la funcion. Su tasa se
registra en la evidencia, porque una caida ahi sigue siendo informacion.

## L7 mide lo que un hilo real rompio, y tampoco bloquea

Sale de una sesion REAL del operador el 2026-09-21, no de una sonda: cuatro
turnos de recomendaciones de cine donde puntuaba por ordinal -"la primera un 6,
la segunda un 8"- y al final pedia la lista de lo valorado. La respuesta acerto
tres lineas, **invento tres** -las pego a la lista que el propio modelo habia
recomendado despues- y omitio dos.

La causa esta en la memoria: se guardaron engramas como "la primera puntuacion
es 6", correctos en su turno y sin referente fuera de el. Es la deuda **D6** del
PLAN, distinta de la incoherencia que ataca la Fase 9.

**Que gatea y que no.** La linea gatea sobre una pregunta ESTRECHA y
determinista -"que puntuacion le di a X?", con su testigo y con los numeros de
lo nunca puntuado como prohibidos-. La variante de lista completa se ejecuta y
se REGISTRA por lineas acertadas, inventadas y omitidas, pero no decide: su
oraculo es mas rico y tambien mas ruidoso, y un recuento no debe convertirse en
veredicto sin haberlo calibrado.

**No bloquea todavia**, por la misma razon que L4b: mide un problema abierto y
declarado, no una promesa incumplida. Pasa a bloquear cuando D6 se cierre; hasta
entonces su reparto se registra en la evidencia, que es lo que permitira saber si
lo que se implemente mejora algo.

Material de referencia del hilo original: `local/lab/`, sesion `cine_20260921`.

## L4b no es excluyente; es la medida que decide la Fase 9

L4b es el caso que el ADR 0013 NO cubre: las dos versiones las dijo el
interlocutor, asi que la procedencia no las distingue. Es exactamente el limite
estructural por el que se reabrio la sintesis (enmienda del ADR 0007: "un
conjunto de engramas atomicos no puede expresar que uno reemplaza a otro").

Por eso L4b se ejecuta y se registra, pero su resultado NO bloquea la puerta:
es el brazo sin sintesis de la Fase 9. Si pasa 3 de 3 con la v0.2.0, la Fase 9
pierde su justificacion medida; si no pasa, queda justificada y con su control
construido.

## Ejecucion

- Script `tools/lab/puerta.py`, solo biblioteca estandar, contra la REST de la
  capa. Codigo de salida: 0 PASA, 1 NO PASA, 2 NULA.
- **Dos agentes independientes lo ejecutan por separado, y la discrepancia entre
  las dos pasadas no es ruido: es el hallazgo.** Independiente significa dos
  ejecutores distintos sobre la MISMA maquina y la misma instalacion -por
  ejemplo el agente disenador y el agente codificador, o un agente y el
  operador-, no dos laboratorios ni dos despliegues. Lo que se busca es lo que
  un solo ejecutor no ve: una puerta que solo pasa cuando la conduce quien la
  escribio, un paso a mano que el autor da sin darse cuenta, o un resultado
  leido como el autor esperaba leerlo.
- La evidencia de cada pasada (huellas, respuestas, veredicto por linea) va a
  `local/lab/`.
- L5 y L5r dependen de poder declarar N corpus en el instalador. Hasta entonces
  se registran como NO EJECUTABLES, nunca como PASA.

## Lo que la puerta NO cubre

- La veracidad general de las respuestas: solo los testigos fijados.
- La fidelidad de transcripcion del modelo: L2 mide lo que la capa entrega, no
  lo que el modelo copia.
- El filtro que impide destilar a `episodic` una tarea no convergida: no se
  puede forzar la no convergencia de forma reproducible.
- Streaming y la piel MCP: solo REST, y MCP solo en lo que comprueba L1.
- Rendimiento y capacidad de GPU.
- Si los umbrales son los OPTIMOS. La puerta dice si la capa funciona con los
  valores declarados; calibrarlos es otra medida (D4, D5).
- Un PASA de forma no es un PASA de contenido. El oraculo lexico puede dar un
  falso NO PASA ante una parafrasis ("dos dias despues del martes"); por eso
  cada respuesta queda en la evidencia y la cruzan dos agentes.
- **El enlace `contradicted_by` NO se comprueba de forma estructural.** Hallado
  al implementar el script: `memory.recall` publica la ANOTACION textual que el
  servicio deriva del enlace, no el enlace. L3 comprueba por tanto lo que ve un
  consumidor, que es lo que la puerta mide; que exista la fila en
  `memory_links` queda fuera. Si algun dia hace falta comprobarlo, la peticion
  correcta es exponer el enlace, no que la puerta consulte la base por detras.
- **La puntuacion de similitud del RAG no se comprueba**, y el corpus de origen
  solo en la medida en que el contexto lo nombre. Hallado al ejecutar L5 el
  2026-09-12: la REST no publica ni el `score` ni un campo `corpora`
  estructurado; eso vive en la telemetria, que es fichero en la maquina y no
  superficie de consumo. La puerta mide lo que ve un consumidor, y declara el
  hueco en su evidencia en vez de leer ficheros por detras.
- **El codigo de salida de `setup.sh` en L1 lo aporta el operador** (argumento
  `--setup-exit-code`): la puerta mide un despliegue ya hecho y no invoca al
  instalador. Que ese codigo sea el de la instalacion que se esta midiendo es
  parte de la precondicion P4.

## Observado el 2026-09-22: L4a puede suspender por algo que no cubre

Sin reconciliar. Se registra aqui porque afecta al criterio, no al script.

El reparto vigente dice que L4a y L4b juzgan la RESPUESTA "y con razon: ahi lo
que se mide es si el CONTEXTO compuesto induce o no una contradiccion, y eso
solo se ve en lo que el modelo termina diciendo". El argumento es bueno, pero
tiene un modo de fallo que no se habia visto: **un contexto correcto tambien
puede dar una respuesta equivocada**.

Medido en la segunda pasada del 2026-09-22 (L4a, 7 de 9). En las dos
repeticiones que fallan, el contexto compuesto es exactamente el que se pide:

    [episodic/facts] (fuente: usuario) La clave del refugio es Ambar13cfa55b61
    [episodic/facts] (fuente: modelo, sin verificar; hay una version del usuario
                     sobre esto) La clave del refugio es Cobalto13cfa55b61.

La version del usuario va primera y etiquetada; la del modelo, anotada. El
modelo responde igualmente con la del modelo. Eso es **fidelidad de
transcripcion**, que este mismo documento declara fuera de cobertura dos
secciones mas abajo, y sin embargo aqui hace suspender a una linea bloqueante.

El oraculo de L4a confunde dos causas: contexto mal compuesto y modelo
infiel. Mientras el contexto salia mal las dos coincidian; ahora que el
mecanismo esta corregido, se separan.

Via propuesta, sin decidir: que L4a DESAMBIGUE. Cuando la respuesta falle, se
comprueba el contexto compuesto; si el contexto es correcto, la repeticion se
registra como fidelidad del modelo y no bloquea, igual que L2 juzga por
`memory.recall` y deja la respuesta en la evidencia. Cambiar esto es cambiar el
criterio, asi que no se hace de paso ni en medio de una medida.

## Reconciliado el 2026-09-12

Los tres puntos que quedaban abiertos se cierran tal como estaban propuestos:
L4b mide y no bloquea; una linea pasa con 3 de 3; y L5 y L5r esperan al
instalador con N corpus, hasta entonces NO EJECUTABLES y nunca PASA.
