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

## A que tipos se aplica, y a cuales NO

| Tipo | Suelo | Motivo |
|---|---|---|
| `semantic`, `episodic` | SI | memoria duradera y tematica: si no viene a cuento, estorba |
| `dialog` | NO | su cometido es la CONTINUIDAD de la conversacion, no la pertinencia tematica. Un suelo aqui romperia "y lo que te dije antes?" |
| `identity`, `principles`, `safety` | NO | delegados, se inyectan de forma incondicional por diseno (`ADR 0002`). Un suelo los alcanzaria y silenciaria la voz del ente |

Los delegados ademas se recuperan por otro camino (`ALWAYS_INJECT`), asi que no
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

## Criterios de aceptacion (falsables)

1. **Gatea por similitud, no por el compuesto.** Un engrama con similitud por
   debajo del umbral NO se recupera aunque su relevancia compuesta sea alta por
   recencia o estabilidad. Prueba automatizada con senales controladas.
2. **Ordena el compuesto.** Entre los que pasan el suelo, el orden sigue siendo el
   de la relevancia compuesta, sin cambios respecto a hoy.
3. **`dialog` intacto.** Un turno de dialogo poco similar se sigue recuperando: la
   continuidad no depende de la pertinencia tematica.
4. **Delegados intactos.** `identity`, `principles` y `safety` se siguen
   inyectando con similitud arbitrariamente baja.
5. **Configurable.** La clave aparece en el esquema con el resto, se fija por
   entorno, y su ausencia toma el defecto declarado.
6. **Cero resultados es valido.** Una recuperacion que no deja pasar nada completa
   y emite telemetria con sus contadores a cero; no es error.
7. **Sin regresion.** La suite en verde -incluidas las pruebas de PostgreSQL si
   hay DSN- mas las pruebas nuevas.

## Entrega

Deja el trabajo STAGED sobre `main`, con `git add` por ruta explicita. **No crees
rama, no commitees, no hagas push.**

Marca D4 como cerrada en `docs/PLAN.md` sin borrar su diagnostico, y actualiza
`CHANGELOG.md` bajo `[No publicado]` declarando que el umbral es provisional y
que su calibracion va con la de D5.

No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
