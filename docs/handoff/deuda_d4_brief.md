# Handoff de implementacion: deuda D4, suelo de relevancia en la memoria

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-19
Base: `main`, su ultimo commit.

Estado de contrato: reconciliado. La deuda esta declarada en `docs/PLAN.md`, D4.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PLAN.md`, deudas D1, D4 y D5.
3. `docs/decision_records/0003-modelo-de-relevancia-y-gradiente-de-tiers.md`: la
   formula de relevancia y que significa cada senal.
4. `docs/ROSTER_MEMORIA.md`: los tipos declarados y sus modos de recuperacion.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## El problema

D1 puso un suelo de similitud al RAG y NO a la memoria. Observado en laboratorio:
a una pregunta sobre guardado de semillas se le inyecto un engrama con el color
favorito del interlocutor.

Hay top-k y presupuesto, pero ningun umbral que diga "esto no viene a cuento".

## La decision de diseno, y es la parte que importa

**El suelo se aplica a la SIMILITUD, no a la relevancia compuesta.**

La relevancia de un engrama es una formula de cuatro senales -recencia,
similitud, estabilidad y score, con pesos por tipo (`ADR 0003`)-. Un umbral sobre
esa suma seria un error: un engrama viejo pero exactamente pertinente puede caer
por debajo, y uno reciente y ajeno puede pasar. El compuesto ORDENA; no dice si
algo viene a cuento.

La separacion es la misma que D1 hizo para el RAG:

    similitud    gatea:  esto trata de lo que se pregunta?
    compuesto    ordena: de lo pertinente, que va primero?

## A que tipos se aplica, y a cuales NO (RECONCILIADO 2026-08-19)

| Tipo | Suelo | Motivo |
|---|---|---|
| `episodic` | SI | ruido reciente, alto volumen y vida corta: es donde vive lo que estorba |
| `semantic` | NO | lo consolidado ya paso un JUICIO para llegar ahi. Es lo que el ente sabe de su interlocutor, y su cometido es acompanar siempre, no solo cuando viene a cuento |
| `dialog` | NO | continuidad de la conversacion, no pertinencia tematica. Un suelo romperia "y lo que te dije antes?" |
| `identity`, `principles`, `safety` | NO | delegados, inyeccion incondicional por diseno (`ADR 0002`). Silenciarlos seria apagar la voz del ente |

El brief anterior aplicaba el suelo tambien a `semantic`. El usuario lo reconcilio
el 2026-08-19 y **queda solo en `episodic`**. El motivo, con la evidencia
delante: la promocion `episodic -> semantic` ya es un filtro, y es un filtro por
JUICIO en vez de por distancia coseno. Usar el gradiente que ya existe es mejor
que un umbral que no distingue "soy alergico a los frutos secos" de "mi color
favorito es el verde".

Consecuencia que hay que DECLARAR y no disimular: hoy la Fase 4 apenas consolida,
asi que a corto plazo esto se parecera a no tener suelo. No invalida la decision;
senala que el trabajo siguiente esta en la consolidacion.

Los delegados se recuperan ademas por otro camino (`ALWAYS_INJECT`), asi que no
basta con no pasarles el umbral: hay que asegurarse de que el mecanismo no los
toca, y probarlo.

## El valor por defecto: provisional y declarado

Se anade una clave de configuracion propia, con el prefijo y el estilo de las
existentes. **No se reutiliza la del RAG**: son sustratos distintos, con
embebedor comun pero contenido y longitudes muy diferentes, y compartir clave
ataria dos calibraciones que no tienen por que coincidir.

El valor por defecto se declara PROVISIONAL en el CHANGELOG y en el propio
codigo. No hay medida todavia: la memoria del laboratorio se purgo y no hay
volumen para calibrar. La calibracion va junto a la del RAG cuando entre corpus y
uso reales, y por `D5` puede que ni siquiera exista un valor unico que sirva.

Elige un valor conservador y di en el CHANGELOG por que ese: ante la duda es peor
silenciar una memoria pertinente que admitir una mediocre, porque lo primero hace
que el ente parezca que no te conoce.

## Fuera de esta tarea (NO implementar)

- Calibrar el umbral, ni el del RAG. Es otra pasada, con datos.
- Tocar la formula de relevancia, los pesos por tipo o el roster.
- Tocar el write-back, la consolidacion o el presupuesto de composicion.
- Aplicar suelo a `dialog` o a los delegados.
- Tocar el core o el laboratorio.

## Como se prueba un umbral: la similitud se CONTROLA, no se hereda de un hash

La primera implementacion fallo por aqui y conviene decirlo antes de los
criterios. Las pruebas usan `FakeEmbedder`, que deriva el vector de un hash del
texto: la similitud entre dos textos cualesquiera es practicamente aleatoria.
Sobre esa base, un umbral no se puede probar ni calibrar, y produce fallos que
parecen conflictos de diseno y no lo son -la prueba de continuidad de la fase 3
quedo en rojo por esto, no por el suelo-.

**Toda prueba del suelo debe construir embeddings con similitud CONOCIDA**, no
confiar en lo que salga del hash. Un par de vectores fijados a mano, o un
embebedor de prueba que devuelva lo que la prueba decida, valen; el hash no.

Y con la misma disciplina: si una prueba preexistente pasa a depender del suelo,
no se toca su asercion para que pase. Se entiende primero POR QUE cambia.

## Idempotencia del banco de pruebas de PostgreSQL

Defecto preexistente, hallado al verificar D4 y que hay que cerrar aqui porque
impide fiarse de cualquier verde: la base de pruebas **no se limpia**, ni entre
ejecuciones ni entre pruebas, de modo que acumula filas y los resultados dependen
de la historia. Llego a tener mas de cien engramas de pasadas anteriores.

Se pide que una ejecucion parta siempre de un estado conocido. La forma la elige
quien implementa -recrear el esquema, vaciar las tablas entre pruebas, o
transaccion por prueba con reversion-, con una condicion: **ejecutar la suite dos
veces seguidas debe dar el mismo resultado**, y ejecutar una prueba sola debe dar
el mismo resultado que dentro de la suite.

## Criterios de aceptacion (falsables)

1. **Gatea por similitud, no por el compuesto.** Un engrama `episodic` con
   similitud CONTROLADA por debajo del umbral no se recupera, aunque su relevancia
   compuesta sea alta por recencia o estabilidad.
2. **Ordena el compuesto.** Entre los que pasan, el orden sigue siendo el de la
   relevancia compuesta.
3. **`semantic` sin suelo.** Un engrama `semantic` con similitud CONTROLADA muy
   por debajo del umbral se sigue recuperando. Es la decision reconciliada y su
   prueba es la que la defiende.
4. **`dialog` sin suelo.** Igual que el anterior, con un turno de dialogo.
5. **Delegados intactos.** `identity`, `principles` y `safety` se recuperan con un
   umbral arbitrariamente alto.
6. **Configurable.** La clave aparece en el esquema, se fija por entorno y su
   ausencia toma el defecto declarado.
7. **Cero resultados es valido.** Una recuperacion que no deja pasar nada completa
   y emite telemetria con sus contadores a cero; no es error.
8. **La continuidad de la fase 3 sigue verde.** Y si hubo que tocar esa prueba, el
   informe explica que cambio y por que, sin ajustar la asercion para que pase.
9. **Suite idempotente.** Dos ejecuciones seguidas con PostgreSQL dan el mismo
   resultado, y una prueba aislada da lo mismo que dentro de la suite.
10. **Sin regresion.** La suite en verde, con PostgreSQL y sin el.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama que ya esta activa. **No
cambies de rama, no crees rama, no commitees, no hagas push.** La rama y el commit
los hace el revisor; tu sandbox tampoco puede escribir en `.git`.

Marca D4 como cerrada en `docs/PLAN.md` sin borrar su diagnostico, y actualiza
`CHANGELOG.md` bajo `[No publicado]` declarando que el umbral es provisional y
que su calibracion va con la de D5.

No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
