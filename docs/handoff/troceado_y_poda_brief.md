# Handoff de implementacion: D9, troceado en frontera y reingesta que poda

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus sobre el banco y el laboratorio. NUNCA quien implementa.
Fecha: 2026-09-29.
Base: `main`, su ultimo commit, con `v0.4.0` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PLAN.md`, deuda **D9** entera.
3. `docs/decision_records/0008-forma-del-rag-operativo.md` y
   `docs/decision_records/0009-modelo-de-datos-conocimiento-por-dominio.md`.
4. `docs/DESPLIEGUE.md`, lo que dice de la idempotencia de la ingesta y de una
   segunda ejecucion del instalador.
5. En el codigo: `chunk_text` e `ingest_path` (`src/ianest_extended/ingest.py`),
   `PostgresRagStore.ingest` (`src/ianest_extended/adapters/rag_postgres.py`) y
   `ExtendedService.knowledge_ingest`.

## Por que existe este encargo, medido

Con el corpus del laboratorio crecido a 288 fragmentos (2026-09-28):

- Cada fragmento empieza con unos 157 caracteres del tema anterior, cortados a
  mitad de palabra ("uete contiene un fichero..."). Parrafo solo frente a
  fragmento, con el mismo embebedor, diez casos:
  `+0.127 +0.055 +0.034 +0.032 +0.022 +0.016 +0.016 +0.000 +0.000 -0.014`.
  Los dos `0.000` son primeros parrafos de fichero, que no llevan cola. El
  `+0.127` hace que una pregunta casi literal ("vuelvo atras una actualizacion
  que rompio el sistema en tumbleweed") no recupere su propio parrafo.
- Al corregir un texto del laboratorio hubo que mantener a mano el numero de
  fragmentos, porque `ingest` hace upsert por `(corpus_id, source_ref, ordinal)`
  y nunca borra los que sobran.

## Lo que se pide, en una frase

Que ningun fragmento empiece ni termine a mitad de palabra, que el solape arranque
en una frontera natural del texto, y que ingerir un corpus deje en el almacen
exactamente los fragmentos del texto ingerido, ni uno mas.

## Decisiones de diseno (reconciliadas el 2026-09-29; no las reabras)

### 1. Fronteras del troceado

- El FINAL de un fragmento se decide como hoy: el ultimo salto de linea en la
  segunda mitad de la ventana; si no hay, el ultimo espacio; si tampoco, el
  corte duro.
- El INICIO del siguiente fragmento sale, como hoy, de retroceder
  `overlap_chars` desde ese final, y a partir de ahi **avanza hasta la primera
  frontera**, en este orden de preferencia, dentro del tramo de solape: inicio de
  parrafo (tras una linea en blanco), inicio de linea, inicio de frase (tras
  `. `, `? ` o `! `), inicio de palabra (tras un espacio).
- Si no hay ninguna frontera en el tramo de solape, el siguiente fragmento
  empieza en el final del anterior: sin solape antes que con solape roto.
- El unico corte a mitad de palabra permitido es el de una palabra mas larga que
  la ventana entera.
- `rag_chunk_tokens` y `rag_chunk_overlap` conservan significado y defectos: el
  solape configurado pasa a ser un maximo.

### 2. La ingesta de un corpus declara su contenido completo

Ingerir un corpus sustituye su contenido: en la MISMA transaccion del upsert se
borran los fragmentos del corpus cuyo `(source_ref, ordinal)` no esta en el lote
ingerido. Un fichero retirado del directorio, renombrado o acortado deja de
tener fragmentos. Es lo que el instalador ya supone cuando reingiere el
manifiesto en cada pasada.

Consecuencia que se acepta a sabiendas: ya no se puede ampliar un corpus
ingiriendo solo el fichero nuevo; se reingiere su ruta completa. Hoy nadie lo
hace (el manifiesto declara una ruta por corpus).

### 3. Lo que se publica

`knowledge.ingest` anade `chunks_deleted` a su salida, junto a `chunks_new` y
`chunks_updated`, en REST, MCP y CLI (`chunks_deleted=N` en la linea de texto).
`RagIngestResult` gana el campo correspondiente.

## Lo que NO entra (y si lo haces, esta mal)

- Retirar un corpus entero. `knowledge reject` quita vinculos pero el corpus
  sigue en la busqueda sin dominio; eso es otro encargo.
- Evitar re-embeber fragmentos cuyo texto no ha cambiado.
- Umbrales, `top_k`, reranking, el embebedor o la dimension.
- La memoria (engramas): este troceado es solo del RAG.
- El instalador, el laboratorio o el core.

## Criterios de aceptacion (falsables)

Los de PostgreSQL se ejecutan; hay banco. No los declares "no ejecutados" sin
intentarlo.

1. **Sin palabras partidas.** Sobre un texto de varios parrafos y sobre otro sin
   saltos de linea, ningun fragmento empieza ni termina a mitad de palabra.
2. **Solape en frontera.** Con parrafos de tamano menor que la ventana, cada
   fragmento a partir del segundo empieza en un inicio de parrafo, linea o frase,
   y nunca en el tramo cortado de una frase anterior.
3. **Cobertura.** Todo caracter no blanco del texto aparece en al menos un
   fragmento, y ningun fragmento supera la ventana.
4. **Palabra gigante.** Una palabra mas larga que la ventana se parte y el
   troceado termina (no hay bucle).
5. **Determinismo.** El mismo texto con los mismos parametros da los mismos
   fragmentos.
6. **Poda al encoger.** Ingerir un corpus con N fragmentos y reingerirlo con un
   texto que da M < N: quedan M en el almacen, comprobado por CONSULTA, y la
   salida declara `chunks_deleted = N - M`.
7. **Poda al retirar un fichero.** Corpus de directorio con dos ficheros;
   reingerido sin uno: los fragmentos de ese fichero desaparecen.
8. **Aislamiento.** La poda de un corpus no toca los fragmentos de ningun otro.
9. **Atomicidad.** Si el upsert falla a mitad, no se ha borrado nada.
10. **Idempotencia.** Reingerir el mismo texto dos veces: la segunda da
    `chunks_new=0` y `chunks_deleted=0`.
11. **Salida publicada** con `chunks_deleted` en las tres pieles.
12. **Sin regresion.** Suite completa en verde CON PostgreSQL y sin skips.

## Lo que NO verifica este encargo

La ganancia de recuperacion se mide en el laboratorio, reingiriendo el corpus y
repitiendo la bateria de 74 sondas del 2026-09-28 y la de preguntas del operador
del 2026-09-29. La hace Opus y NO forma parte de esta entrega.

## Impacto de version

Un campo nuevo en la salida de `knowledge.ingest`: adicion compatible, **MINOR**
en la serie pre-1.0. El troceado y la poda cambian comportamiento sin cambiar
contrato; se anotan en el CHANGELOG, porque tras actualizar hay que reingerir
para que surtan efecto.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x, banco incluido).
