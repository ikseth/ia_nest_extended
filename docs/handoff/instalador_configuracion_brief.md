# Handoff: el instalador no sabe declarar la configuracion de la capa

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-09-12.
Base: `main`, su ultimo commit, con `v0.2.1` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PUERTA_LABORATORIO.md`, sobre todo su REGLA DE CLASIFICACION.
3. `docs/VERSIONADO.md`: el esquema `IANEST_EXTENDED_*` es contrato publico.
4. `deploy/setup.sh`, funciones `load_config_file`, `validate_config` y
   `write_environment`.

## El problema, medido el 2026-09-12

La puerta de laboratorio corrio contra el primer despliegue natural y su linea
L5 fallo. Medidas las sondas contra el almacen, las dos que fallan puntuan
`0.470` (linux) y `0.478` (finanzas): por debajo del suelo base `0.50` y por
encima del `0.41` con dominio que D5 midio. Es decir, un AJUSTE DE
CONFIGURACION lo arregla.

Y ahi aparece el defecto: **ese ajuste no se puede declarar**. `ExtendedConfig`
tiene 44 campos; `setup.sh` conoce 21 claves propias y escribe 11 variables en
`extended.env` (cifras corregidas el 2026-09-12: el brief decia 45 y 20, y las
conto mal quien lo escribio). Los umbrales -`RAG_MIN_SCORE`, `RAG_MIN_SCORE_DOMAIN`,
`RAG_MIN_SCORE_NO_DOMAIN`, `CONFLICT_THRESHOLD`, `MEMORY_MIN_SIMILARITY`,
`TASK_TIMEOUT_SECONDS`...- no estan entre ellas, y una clave desconocida en el
fichero de parametros ES un error, con razon.

Consecuencia: hoy afinar la capa obliga a editar `extended.env` a mano. Un paso
a mano invalida la pasada de la puerta, asi que **el lado de "configuracion" de
la regla de clasificacion no tiene canal legitimo**. Eso convierte un ajuste en
un fallo de codigo, que es justo lo que la regla existe para separar.

## Parte 1: paso a traves de la configuracion de la capa

**Que se pide.** Que el fichero de parametros admita cualquier clave que
empiece por `IANEST_EXTENDED_` y la escriba TAL CUAL en `extended.env`.

Reglas, y son contrato:

1. **Solo pasan las que llevan el prefijo.** Una clave sin prefijo que el
   instalador no conozca sigue siendo error: eso es lo que caza las erratas.
2. **El instalador NO valida su valor.** El esquema vive en `config.py` y ahi se
   valida al arrancar; duplicar la validacion seria re-declarar contrato ajeno,
   que es la deriva que ya corregimos dos veces. Dilo en la documentacion.
3. **Colision = error tipado.** Declarar una que el instalador ya genera
   (`IANEST_EXTENDED_CORE_URL`, `..._REST_PORT`, `..._DATABASE_DSN` y las demas
   de `write_environment`) falla al validar, nombrando la clave y la opcion
   equivalente. No se acepta "gana la ultima".
4. **Orden y visibilidad.** Las heredadas se escriben DESPUES del bloque
   generado, en el orden en que aparecen en el fichero, para que un operador vea
   de un vistazo que se anadio a mano-declarado.
5. **Viajan al snapshot** de configuracion efectiva, porque forman parte de lo
   que describe ese despliegue.
6. **Idempotencia intacta.** Repetir el instalador con el mismo fichero deja el
   mismo `extended.env`.

No inventes un fichero aparte ni una seccion nueva: el fichero de parametros ya
es el hogar de la configuracion de esa instalacion.

## Parte 2: L2 deja de juzgar la respuesta del modelo

Reconciliado con el usuario el 2026-09-12, ya escrito en
`docs/PUERTA_LABORATORIO.md`. En `tools/lab/puerta.py`:

- **L2 PASA si `memory.recall` devuelve el testigo con `stated_by=user`.** La
  respuesta del modelo se sigue registrando en la evidencia, pero NO decide.
- Motivo, medido dos veces: el modelo responde `Xanthe` a un testigo
  `Xanthe74bad8d4b3` mientras el recall lo entrega entero. Esta capa promete
  entregar la memoria, no que el modelo la copie literalmente.
- **L4a y L4b NO cambian**: ahi lo que se mide es si el contexto compuesto
  induce una contradiccion, y eso solo se ve en la respuesta.

## Fuera de este encargo (NO implementar)

- Cambiar defectos de la capa ni tocar `config.py`.
- Validar valores en el instalador.
- Tocar el core, el laboratorio o el resto del criterio de la puerta.

## Criterios de aceptacion (falsables)

En `tests/test_deploy_setup.py` y `tests/test_lab_puerta.py`.

1. **Pasa a traves.** Un fichero con `IANEST_EXTENDED_RAG_MIN_SCORE_DOMAIN=0.41`
   produce esa linea en `extended.env`, con ese valor exacto.
2. **Sin prefijo sigue fallando.** Una clave desconocida sin prefijo aborta con
   error y sin escribir nada.
3. **Colision.** Declarar `IANEST_EXTENDED_REST_PORT` aborta con error tipado
   que nombra la clave y la opcion equivalente del instalador.
4. **Orden.** Las heredadas aparecen despues del bloque generado y en el orden
   declarado.
5. **Snapshot.** El `setup.conf` efectivo las conserva y una segunda ejecucion
   reproduce el mismo `extended.env`.
6. **L2 por el recall.** Con un stub cuyo recall devuelve el testigo con
   `stated_by=user` y cuya respuesta NO lo contiene, L2 PASA y la evidencia
   guarda ambas cosas.
7. **L2 sigue fallando cuando toca.** Si el recall no devuelve el testigo, L2 NO
   PASA aunque la respuesta lo contenga.
8. **Sin regresion.** Suite completa en verde.

## Impacto de version

La parte 1 amplia lo que el fichero de parametros admite, sin cambiar ninguna
clave existente ni ningun defecto: adicion compatible, PATCH en la serie
pre-1.0. La parte 2 es instrumental y no mueve version.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x).
