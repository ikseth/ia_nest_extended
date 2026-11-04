# Brief: paso cero, decidir si el turno pide conocimiento

Estado: decidido por el operador el 2026-11-04. Impacto: aditivo, PATCH.

Lee antes: `docs/PLAN.md` (Hito siguiente, punto 1) y
`docs/PUERTA_LABORATORIO.md` (seccion "L5r y el paso cero"). Es el criterio, y no
se cambia aqui.

## Que se construye

Antes de buscar en el conocimiento, se compara el turno con unas frases de
cortesia. Si la similitud con la mas parecida llega al umbral, no se busca. La
memoria no cambia nunca por esto.

Es la ruta de charla de un enrutador semantico. Es mecanismo, no personalidad: no
escribe nada, no toca `identity` ni `principles` y no cambia lo que se manda al
modelo salvo por la ausencia de fragmentos.

## Piezas

1. **Modulo nuevo `src/ianest_extended/knowledge_gate.py`.** Clase pequena con una
   decision: `decide(prompt) -> GateDecision`, con `decision`, `score`, `threshold`,
   `nearest` y el embedding del turno. Valores de `decision`: `skip`, `search`,
   `not_applied`, `error`. El decisor debe poder sustituirse en el futuro: quien
   lo usa solo conoce esa decision, no la lista ni el umbral.
2. **Frases.** Ya escritas en `src/ianest_extended/data/courtesy_es.txt`; no las
   cambies. Incluye el fichero como dato del paquete (`pyproject.toml`). Lineas
   vacias y las que empiezan por `#` se ignoran.
3. **Configuracion** (`ExtendedConfig`, con el patron de los demas parametros):
   - `IANEST_EXTENDED_KNOWLEDGE_GATE_ENABLED`, por defecto verdadero;
   - `IANEST_EXTENDED_KNOWLEDGE_GATE_THRESHOLD`, por defecto `0.70`;
   - `IANEST_EXTENDED_KNOWLEDGE_GATE_PHRASES_FILE`, opcional, sustituye al fichero
     del paquete.
   Sin ninguna variable, el despliegue natural ya lo lleva encendido: ningun paso
   a mano.
4. **Embeddings.**
   - Las frases se calculan la primera vez que hacen falta, una vez por proceso, en
     una sola peticion por lotes (`/api/embed` de Ollama acepta una lista) y con
     cerrojo. Un fallo no se guarda: se reintenta en el turno siguiente. Comprueba
     que la instancia vive en la composicion y no se recrea en cada peticion.
   - El embedding del turno se reutiliza en la busqueda:
     `RagStore.retrieve` acepta un `query_embedding` opcional. Una pregunta no debe
     pagar un embedding de mas. Un test lo comprueba contando llamadas.
5. **Un solo punto de decision para los dos caminos.** Hoy se recupera por
   `Enricher._retrieve_rag` (`enrichment.py`) y, por separado, por
   `service.memory_recall`, que llama al almacen directamente. `memory_recall` debe
   pasar por el mismo metodo del enriquecedor, conservando su respuesta y su
   telemetria actuales salvo lo que se anade aqui. Sin esto, la puerta podria pasar
   sin servir a quien conversa.
6. **Casos.**
   - `use_rag=false`, sin almacen o puerta apagada: `not_applied`, sin embedding de
     mas.
   - Un `use_rag=true` explicito NO se salta el paso cero: la sonda de L5r lo pide
     asi.
   - Las subtareas de `task.run` (`Enricher.retrieve_rag`) no pasan por el paso
     cero: `not_applied`. Las redacta el planificador, no el interlocutor.
   - Se aplica con dominio resuelto y sin el.
   - Cualquier excepcion del paso cero: se busca como hoy, `error`, y un aviso en
     el log una sola vez. Ante la duda, se busca.
7. **Telemetria.** En `rag.retrieve`, aditivo en `details`: `knowledge_gate` con
   `decision`, `score`, `threshold` y `nearest`. En un `skip` el evento se registra
   igual, con `k_returned` 0 y `status` `skipped`. Comprueba que nada que lea estos
   eventos se rompa con ese estado.
8. **Superficie, para poder medir.** `memory.recall` anade `knowledge_gate` a su
   respuesta. La linea L5r tiene que comprobar tambien un turno enriquecido por
   REST: mira que publica hoy `prompt.run`. Si ya informa de los fragmentos
   recuperados, usalo; si no, anade lo minimo y aditivo. Dime que has elegido.
   Documenta en `docs/EXTENDED_CONTRACT.md` y en `CHANGELOG.md` (`[No publicado]`).
9. **Puerta (`tools/lab/puerta.py`), linea L5r, con los cinco puntos del criterio.**
   - Frases de `tools/lab/paso_cero_bateria.json`, que ya esta escrito y NO se
     cambia. Ese fichero fija los puntos 2 y 4.
   - Punto 3: un argumento nuevo con la ruta de un JSONL con campo `pregunta`.
     Esas preguntas son privadas y no entran en el repo. Sin el argumento, el punto
     queda NO EJECUTABLE y L5r no puede dar PASA.
   - Los puntos 3 y 4 se juzgan por `knowledge_gate.decision == "search"`, no por
     el numero de fragmentos: una pregunta puede buscar y no encontrar.
   - La evidencia registra por frase la decision, la puntuacion y la mas parecida.
   - Actualiza `tests/test_lab_puerta.py`.

## Lo que NO entra

- Memoria y conocimiento en paralelo, indice vectorial, cache de embeddings en la
  memoria, reranker: piezas posteriores.
- `interlocutor_profile` (`edge CR-0002`): pieza siguiente.
- Cambiar el umbral, las frases o la bateria para que algo pase.
- Tocar `ia_nest_core`.

## Tests

- Con `FakeEmbedder` (determinista): una frase exacta de la lista da `skip`; otra
  da `search`. Decision comun a los dos caminos.
- Memoria intacta en un `skip`: el contexto la sigue trayendo.
- Telemetria en los cuatro valores de `decision`.
- Sin solape entre `courtesy_es.txt` y `cortesia_ciega` o `mixtos` de la bateria.
- Si un test existente cambia porque su texto es una frase de la lista (`hola`),
  cambia el texto del test, no el mecanismo, y dimelo.

## Reglas

Docs y comentarios en ASCII, sin acentos. Repo publico: sin IPs ni nombres de
maquina. Sin tags ni dependencias nuevas.
