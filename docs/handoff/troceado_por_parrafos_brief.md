# Handoff de implementacion: el troceado respeta los parrafos (cierre de D9)

Destinatario: agente codificador (Codex).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus sobre el banco y el laboratorio. NUNCA quien implementa.
Fecha: 2026-10-13. RECONCILIADO con el operador el 2026-10-13.
Base: `main`, con `v0.5.0` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PLAN.md`, deuda **D9**.
3. `docs/handoff/troceado_y_poda_brief.md`: lo que ya se entrego en `v0.5.0`.
4. En el codigo: `chunk_text` y sus auxiliares (`src/ianest_extended/ingest.py`)
   y `tests/test_ingest.py`.

## Por que existe este encargo, medido

`v0.5.0` desplegada en el laboratorio: la bateria de sondas del corpus da 73/74,
y el criterio del hito es sin fallos. El fragmento que responde a la sonda que
falla existe, pero empieza con la ultima frase del parrafo ANTERIOR, de otro
tema, y puntua 0.532; el parrafo solo puntua 0.622 y quedaria primero.

La causa es del diseno de D9, no de su entrega: la ventana de tamano fijo no
esta alineada a parrafos, asi que un fragmento es "cola de un tema mas cabeza de
otro" con cualquier regla de solape. Retocar el solape solo cambia que sonda
falla.

Simulado con el mismo embebedor sobre el corpus y las 74 sondas:

    troceado                 fragmentos  aciertos  top1 medio
    v0.5.0                       325      73/74      0.678
    parrafos enteros             312      74/74      0.706

## Lo que se pide, en una frase

Que un fragmento este hecho de parrafos ENTEROS, y que solo se parta un parrafo
cuando el solo no cabe en la ventana.

## Decisiones de diseno (reconciliadas; no las reabras)

1. **Parrafo**: bloque de texto separado de los demas por una o mas lineas en
   blanco (la frontera de parrafo que `ingest.py` ya reconoce). Se le quitan los
   blancos de los extremos; por dentro no se toca.
2. **Empaquetado voraz y en orden**: se van juntando parrafos consecutivos,
   unidos por una linea en blanco, mientras el fragmento no supere la ventana
   (`chunk_chars`). El parrafo que no cabe abre el fragmento siguiente.
3. **Sin solape entre fragmentos hechos de parrafos enteros.** Ningun fragmento
   repite texto de un parrafo vecino.
4. **Parrafo mayor que la ventana**: se trocea el solo con el algoritmo de
   `v0.5.0` (fronteras de linea, frase y palabra, y solape como maximo). Sus
   trozos NO se juntan con parrafos vecinos: el fragmento en curso se cierra
   antes, y el parrafo siguiente abre fragmento nuevo.
5. Un texto sin ninguna linea en blanco es un solo parrafo: si cabe, un
   fragmento; si no, se comporta exactamente como en `v0.5.0`.
6. `rag_chunk_tokens` y `rag_chunk_overlap` conservan nombre, significado y
   defecto. El solape solo actua dentro de un parrafo mayor que la ventana.
7. La firma de `chunk_text` no cambia.

## Lo que NO entra (y si lo haces, esta mal)

- La poda, `chunks_deleted`, el almacen o cualquier salida publica.
- Reconocer titulos, listas, markdown o cualquier estructura que no sea la
  linea en blanco.
- Juntar o descartar parrafos cortos por tamano minimo.
- Umbrales, `top_k`, reranking, el embebedor, la memoria, el instalador, el core.

## Criterios de aceptacion (falsables)

1. **Parrafos enteros.** Con parrafos menores que la ventana, todo fragmento es
   la union, en orden y con una linea en blanco entre ellos, de parrafos
   completos del texto. Ningun fragmento empieza ni termina dentro de un parrafo.
2. **Voraz.** Dos parrafos consecutivos que caben juntos van en el mismo
   fragmento; para todo fragmento salvo el ultimo, anadirle el parrafo siguiente
   superaria la ventana.
3. **Sin repeticion.** Ningun parrafo aparece en dos fragmentos.
4. **Parrafo gigante aislado.** Un parrafo mayor que la ventana, entre dos
   parrafos pequenos: sus trozos no contienen texto de los vecinos, y los
   vecinos no contienen texto suyo.
5. **Sin linea en blanco, como `v0.5.0`.** Para textos sin lineas en blanco, la
   salida es identica a la de `v0.5.0` (las pruebas de D9 que usan esos textos
   siguen pasando sin tocarlas).
6. **Limite, cobertura y determinismo.** Ningun fragmento supera la ventana;
   todo caracter no blanco aparece en algun fragmento; misma entrada, misma
   salida.
7. **Palabras enteras.** Sigue sin haber cortes a mitad de palabra, salvo la
   palabra mayor que la ventana.
8. **Sin regresion.** Suite completa en verde CON PostgreSQL y sin skips. Si una
   prueba de D9 con parrafos cambia de expectativa por este encargo, se adapta y
   se declara en el informe cual y por que.

## Lo que NO verifica este encargo

La bateria de 74 sondas sin fallos, las sondas de ruido y el regimen con
dominio se miden en el laboratorio tras reingerir. Lo hace Opus.

## Impacto de version

Correccion de comportamiento sin cambio de contrato: **PATCH** (`0.5.1`). El
CHANGELOG dice que tras actualizar hay que reingerir.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x, banco incluido).
