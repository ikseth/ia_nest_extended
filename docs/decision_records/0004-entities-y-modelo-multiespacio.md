# Decision 0004: entities y modelo multi-espacio de recuperacion

Fecha: 2026-07-18

## Decision

**Modelo multi-espacio.** La recuperacion de memoria combina varios espacios de
cercania, cada uno con su REPRESENTACION NATURAL; la formula de ranking del
ADR 0003 es la funcion de combinacion:

| Espacio | Representacion | Cercania |
|---|---|---|
| semantico | vector denso aprendido (embedding) | coseno |
| temporal | escalar exacto (timestamp) | decaimiento `0.5^(edad/H)` |
| entidades | conjunto discreto exacto (`entity_refs`) | comparticion de etiquetas |
| dominio | categorico exacto (`domain_tag`) | filtro (gate) |

Regla: NUNCA aproximar lo que se conoce exactamente. Solo el espacio semantico
es denso y aprendido, porque es el unico sin verdad exacta disponible. Tiempo y
pertenencia a entidad son hechos exactos; embeberlos en vectores aprendidos los
degradaria a aproximaciones.

**Entities.** Tercer patron de almacenamiento, junto a la memoria que decae
(ADR 0003) y el conocimiento RAG:

1. Registro de entidades: cada entidad (persona, proyecto, objeto) tiene
   `entity_id` propio y un PERFIL mutable y versionado que no decae: se
   actualiza (como los principios de la cantera: refuerzo, estados, historial).
   Es la segunda dimension de identidad: la entidad perfilada no es la identidad
   del request.
2. Etiquetado: cada engrama experiencial lleva `entity_refs` (los `entity_id`
   que menciona). El etiquetado de menciones INEQUIVOCAS es mecanico y lo hace
   extended en el write-back (lado estricto). Lo ambiguo queda como
   mencion-sin-resolver: crear entidades nuevas y resolver ambiguedades es
   juicio, luego de conscience (delegada; fallback manual del operador mientras
   conscience no exista).
3. Recuperacion: "contexto de una entidad" = filtro duro por `entity_ref` (gate,
   como el dominio) + ranking ADR 0003 sobre ese subconjunto. La cercania
   vectorial densa NO define pertenencia (mide tema, no referente); queda como
   ayuda de DESCUBRIMIENTO de menciones sin etiquetar.

**Capacidades registradas y diferidas** (costura con nombre, sin construir):

- Asociacion graduada: grafo de co-menciones entre entidades (estilo
  `memory_links` de la cantera) con recuperacion de un salto a peso reducido
  (activacion propagada).
- Asociacion temporal: recuperar por ventana alrededor de un engrama ("que mas
  paso por aquella epoca").

Se implementan cuando la recuperacion plana se quede corta, no antes.

**Vocabulario.** Se adopta ENGRAMA como nombre del registro individual de
memoria (la traza de un recuerdo), distinto del TIPO (la declaracion, ADR 0002).

## Motivo

La similitud de embeddings mide tema, no referente: dos engramas de la misma
entidad pueden estar lejos en el espacio semantico ("arreglo el servidor" /
"le gusta el jazz") y dos de entidades distintas, pegados ("Fulano arreglo el
servidor" / "Mengano arreglo el router"). Definir la pertenencia por cercania
recuperaria mal en ambas direcciones. El vinculo real es un hecho exacto: la
referencia compartida. El etiquetado explicito lo captura sin aproximacion, y
en un motor unico (postgres + pgvector, ADR 0003) filtro exacto mas orden
vectorial es una sola query.

La linea etiquetar-es-mecanico / perfilar-es-juicio preserva la frontera del
ADR 0002: extended hace lo mecanico en el lado estricto; el perfil destilado es
sedimento de conscience. Y las asociaciones diferidas siguen la leccion del core
ADR 0035: una capacidad sin consumidor real se pudre; se le pone nombre, no
codigo.

## Consecuencia

- El esquema de la Fase 2 gana el registro de entidades (`entity_id`, perfil
  versionado) y la columna `entity_refs` en los engramas; el grafo de asociacion
  queda nombrado como evolucion del esquema, no construido.
- El roster de tipos de la Fase 2 queda completable: tiers (ADR 0003) +
  clases (ADR 0002) + entities (esta ADR). Propuesta en
  `docs/ROSTER_MEMORIA.md`.
- `docs/VISION_MEMORIA.md` se alinea (entities deja de estar "por decidir").
- Impacto de version: ninguno (sin contrato publico cortado; Fase 7).
