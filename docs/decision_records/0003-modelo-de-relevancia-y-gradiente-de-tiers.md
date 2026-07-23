# Decision 0003: modelo de relevancia y gradiente de tiers (Opcion C)

Fecha: 2026-07-18

## Decision

La recuperacion de memoria ordena los candidatos por un ranking ponderado de
senales, y un TIER se define por sus pesos, no por una ventana de fecha.

    ranking = wR*R + wS*S + wE*E + wC*C        (luego filtro de dominio)
    R(edad) = 0.5 ^ (edad / H)

- R: recencia; S: similitud semantica (coseno sobre embeddings); E: estabilidad
  (refuerzos acumulados); C: score/importancia. La coherencia de dominio actua
  como FILTRO (gate), no como sumando: acota, no ordena.
- Un tier es su vector de pesos `(wR, wS, wE, wC)` mas su vida media `H`. Dos
  tiers son distintos (Leccion 1, core ADR 0011) si y solo si su vector difiere.
  Esto convierte la Leccion 1 en una prueba: vectores iguales = tiers aliasados
  = uno sobra.

Gradiente experiencial de tres tiers (punto de partida configurable, no hardcode):

| Tier | Scope | (wR, wS, wE, wC) | H (vida media) | Escritura |
|---|---|---|---|---|
| conversacional | `session_id` | (1.0, 0, 0, 0) | ~4 horas | write-back directo |
| episodica | `user_id` | (0.5, 0.35, 0.05, 0.10) | ~30 dias | write-back (deduped) |
| semantica | `user_id` | (0.05, 0.50, 0.25, 0.20) | off (~anos) | solo consolidacion, comprimida |

El gradiente temporal de la ambicion de la cantera (corto/medio/largo) se
DISUELVE en dos sitios, ninguno un tier nuevo:

1. La edad es una senal continua (R) dentro de la curva episodica -> semantica,
   no un muro. Con H=30d en episodica: a 30d R=0.5, a 90d R=0.125, a 180d R~0.02;
   "corto" (recencia manda) se vuelve "medio" y "largo" (ya solo similitud y
   estabilidad la mantienen viva) sin frontera.
2. El "medio" de horizonte de tareas de la cantera ("compromisos y seguimiento")
   es el namespace `tasks` con recuperacion sensible a recencia, no una capa de
   durabilidad (namespace ortogonal a tier).

La consolidacion episodica -> semantica se dispara cuando R cae bajo un umbral
(~0.1) Y hay estabilidad/score suficiente; si no, la memoria sale de la ventana
caliente (archivada, no borrada). Mas las delegadas de conscience
(`historica`/`persona`/`principles`), que son la version identidad de la
semantica (ADR 0002).

La similitud exige embeddings, luego un motor con vectores: `postgres + pgvector`
como referencia y produccion. Un vector DB dedicado se descarta porque el
workload es relacional-primero (ACID, lineage con foreign keys, autoridad de
escritura del ADR 0002); partirlo en dos sistemas anade dolores de consistencia
sin ganancia a la escala de una entidad. Dependencia nueva: un modelo de
embeddings (servible por el Ollama del lab); modelo y dimensionalidad se deciden
en Fase 2/3.

## Motivo

Hace imposible el aliasing de tiers POR CONSTRUCCION (Leccion 1): tres vectores
demostrablemente distintos -recencia-pura / equilibrado / similitud-estabilidad
con recencia apagada- en vez de cinco tiers con ventanas duras que aliasarian.
Aplica la disciplina de no crear un tier sin comportamiento propio.

Y da a la memoria un comportamiento analogo al humano, que es el fin de la capa
(`docs/VISION_MEMORIA.md`): recencia para lo reciente, similitud+estabilidad para
lo que importa sin importar cuando, y consolidacion con compresion -el "modo
sueno" de la cantera (core ADR 0034)- para el largo plazo.

## Consecuencia

- El modelo de relevancia es el `retrieval-mode` de cada declaracion de tipo
  (ADR 0002): el vector de pesos y H son columnas de la declaracion; los valida
  `memory_type.validate` (vectores iguales entre dos tiers = rechazo).
- Los numeros (H = 4h / 30d / off; los vectores) son punto de partida
  configurable por registro (leccion de la cantera), no valores fijos en codigo.
- Pendiente del roster de Fase 2: los namespaces y la clase de cada tipo, incluido
  `entities`, que tiene su propia reconciliacion (un perfil no decae, se
  actualiza; no encaja en el gradiente).
- Impacto de version: ninguno (sin contrato publico cortado; se corta en Fase 7).
