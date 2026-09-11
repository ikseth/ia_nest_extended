# Puerta de laboratorio de ia_nest_extended

Estado: reconciliado 2026-09-12. Declarado ANTES de medir.
Version: 1.0 - 2026-09-12

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

Cada pasada usa un `user_id` propio, nuevo en cada ejecucion, y nunca el del
operador (`docs/FORMA_ENRIQUECIMIENTO.md`).

**El oraculo es externo al sistema (regla 5 de meta ADR 0010).** Cada sonda
lleva un TESTIGO fijado antes de ejecutar: una cadena aleatoria o un dato
dicho por el interlocutor que el modelo no puede conocer por su cuenta. La
comprobacion es lexica: presencia del testigo correcto y ausencia del
incorrecto. Ninguna linea usa un modelo del propio sistema como juez.

| Linea | Que se mide | Pasa | No pasa |
|---|---|---|---|
| L1 Forma | `setup.sh` con `VERIFY=strict`; `capability.list` sin degradacion | codigo 0 y ninguna degradacion | cualquier otro |
| L2 Continuidad | el interlocutor dice un testigo aleatorio en la sesion A; se pregunta por el en la sesion B | la respuesta de B contiene el testigo, y `memory.recall` de B lo devuelve con `stated_by=user` | falta cualquiera de las dos |
| L3 Procedencia | se siembra por `memory.write` un candidato con `stated_by=model`; el interlocutor dice lo contrario | el contexto del turno siguiente etiqueta el candidato como del modelo y anotado, y lo coloca detras de la version del usuario | sin etiqueta, sin enlace `contradicted_by` o en otro orden |
| L4a Coherencia, correccion de un candidato del modelo | hilo de cuatro turnos sobre L3; la ultima pregunta pide el dato | la respuesta contiene el testigo del usuario y no el del modelo | contiene el del modelo, o ninguno |
| L4b Coherencia, autocorreccion del interlocutor | "la reunion es el martes" ... "perdona, es el jueves" ... "que dia es?" | contiene "jueves" y no "martes" | contiene "martes", o ninguno |
| L5 RAG por dominio | por cada dominio con corpus confirmado, una pregunta redactada como la haria una persona, SIN mirar el corpus | el corpus esperado aparece en los recuperados (`corpora` en telemetria) | no aparece |
| L5r Ruido | cortesia sin dominio ("hola", "gracias", "que recuerdas de mi") | `k_returned = 0` de RAG | recupera algo |
| L6 Repeticion | segunda ejecucion de `setup.sh` sobre lo instalado | L1-L3 siguen pasando y los datos no se duplican | cualquier otro |

Repeticion: L2, L3, L4a, L4b y L5 con n = 3. Una linea PASA con 3 de 3; con
menos, NO PASA y el reparto se anota.

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
- El filtro que impide destilar a `episodic` una tarea no convergida: no se
  puede forzar la no convergencia de forma reproducible.
- Streaming y la piel MCP: solo REST, y MCP solo en lo que comprueba L1.
- Rendimiento y capacidad de GPU.
- Si los umbrales son los OPTIMOS. La puerta dice si la capa funciona con los
  valores declarados; calibrarlos es otra medida (D4, D5).
- Un PASA de forma no es un PASA de contenido. El oraculo lexico puede dar un
  falso NO PASA ante una parafrasis ("dos dias despues del martes"); por eso
  cada respuesta queda en la evidencia y la cruzan dos agentes.

## Reconciliado el 2026-09-12

Los tres puntos que quedaban abiertos se cierran tal como estaban propuestos:
L4b mide y no bloquea; una linea pasa con 3 de 3; y L5 y L5r esperan al
instalador con N corpus, hasta entonces NO EJECUTABLES y nunca PASA.
