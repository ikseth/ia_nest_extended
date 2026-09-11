# Handoff de implementacion: el instalador ingiere N corpus

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-09-12.
Base: `main`, su ultimo commit, con `v0.2.0` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/DESPLIEGUE.md`, seccion "Corpus reproducible".
3. `docs/PUERTA_LABORATORIO.md`: esto es lo que hoy impide medir sus lineas
   L5 y L5r.
4. `docs/VERSIONADO.md`: el fichero de parametros del instalador es contrato
   publico y esta capa ya tiene version publicada. Importa como se introduce
   una clave.

## El problema, verificado sobre el codigo

`deploy/setup.sh` ingiere UN corpus: `CORPUS_PATH`, `CORPUS_NAME` y
`CORPUS_DOMAINS` son claves escalares, y `ingest_corpus()` hace una sola llamada
a `knowledge ingest` seguida de un `knowledge confirm` por dominio.

Un laboratorio real tiene N corpus con dominios DISTINTOS -hoy 19, cada uno con
el suyo-. Con una sola terna no se pueden declarar, asi que ese despliegue no se
puede reproducir con el instalador y el corpus acaba entrando a mano. Un paso a
mano invalida la puerta de laboratorio: deja de describir un despliegue natural.

No es un defecto de diseno del instalador, es una funcion que le falta.

## Lo que se pide

Una clave nueva, `CORPUS_MANIFEST`, con la ruta de un fichero declarativo que
lista N corpus. Las tres claves actuales NO se retiran ni se renombran.

**Las claves, literales, para que no las inventes:**

    CORPUS_PATH       (ya existe)
    CORPUS_NAME       (ya existe)
    CORPUS_DOMAINS    (ya existe)
    CORPUS_MANIFEST   (nueva)

**Precedencia, y esto es contrato:** `CORPUS_MANIFEST` es EXCLUYENTE con las
tres anteriores. Declarar ambas cosas es error tipado al validar, nunca
precedencia silenciosa; es la misma regla que ya aplica `validate_config` a
`SERVICE_ENABLE`/`SERVICE_INSTALL` y a `VERIFY`. Sin ninguna de las dos, el
instalador no ingiere nada, que es el comportamiento de hoy.

### Formato del manifiesto

Texto plano ASCII, una linea por corpus, tres campos separados por `|`:

    # nombre_corpus | dominios separados por coma | ruta al texto
    linux_docs       | linux                      | nuevo/linux/linux.txt
    scripting_docs   | codigo,linux               | recuperado/scripting.txt
    domotica_docs    | domotica                   | nuevo/domotica

Reglas:

1. Lineas vacias y las que empiezan por `#` se ignoran.
2. Los espacios alrededor de cada campo se recortan.
3. **Las rutas se resuelven RELATIVAS AL DIRECTORIO DEL MANIFIESTO**, para que
   el manifiesto y sus textos viajen juntos. Una ruta absoluta se acepta tal
   cual.
4. La ruta puede ser fichero o directorio: es lo que ya acepta
   `knowledge ingest`.
5. Un corpus puede declarar varios dominios; cada uno se confirma por separado,
   igual que hoy.
6. El mismo nombre de corpus dos veces en el manifiesto es error tipado.

### Comportamiento

Por cada linea, y en el orden del fichero: `knowledge ingest --corpus NOMBRE
--domain D1 [--domain D2] RUTA`, y despues un `knowledge confirm --corpus
NOMBRE --domain Dn` por dominio. Es exactamente lo que hace hoy
`ingest_corpus()`, repetido.

**Que pasa si una linea falla.** El instalador ABORTA con codigo distinto de
cero, nombrando el corpus que fallo y conservando la causa. Los corpus ya
ingeridos se quedan: la ingesta es idempotente por corpus, referencia de fuente
y ordinal de chunk, asi que repetir el comando completo despues de arreglar la
linea no duplica nada. Declara ese comportamiento en `docs/DESPLIEGUE.md`: no
es una transaccion y no vamos a fingir que lo sea.

**Validacion, antes de tocar la base.** Se valida el manifiesto ENTERO antes de
ingerir la primera linea: fichero legible, sintaxis de tres campos, nombres no
vacios, dominios no vacios y rutas legibles. Un error de sintaxis en la ultima
linea no debe descubrirse a mitad de la ingesta. Los DOMINIOS no se validan
aqui: eso lo hace `knowledge ingest` contra `domain.list` del core, y duplicar
esa validacion seria re-declarar contrato ajeno.

## Fuera de esta tarea (NO implementar)

- Cambiar el formato de `knowledge ingest` o `knowledge confirm`.
- Vincular por chunk, auto-etiquetar, o tocar el gate de recuperacion.
- Exportar o clonar vectores. La fuente es texto y los embeddings se derivan.
- Una capacidad nueva que liste corpus (es otra deuda, C2 del inventario).
- Tocar el core, la memoria, el RAG o el laboratorio.

## Criterios de aceptacion (falsables)

Al estilo de `tests/test_deploy_setup.py`, que ya prueba el instalador aislado.

1. **N corpus.** Un manifiesto con tres corpus y dominios distintos produce tres
   `knowledge ingest` con sus `--domain` correctos y un `knowledge confirm` por
   vinculo, en el orden del fichero.
2. **Excluyente.** Declarar `CORPUS_MANIFEST` junto a cualquiera de
   `CORPUS_PATH`/`CORPUS_NAME`/`CORPUS_DOMAINS` falla al validar, con mensaje
   propio y codigo distinto de cero, sin haber ingerido nada.
3. **Compatibilidad.** Un fichero de parametros que solo declara la terna
   antigua se comporta EXACTAMENTE como hoy. Y uno que no declara ninguna de
   las dos cosas no ingiere, tampoco como hoy.
4. **Rutas relativas.** Un manifiesto en `/X/manifiesto.txt` con ruta
   `nuevo/linux.txt` ingiere `/X/nuevo/linux.txt`.
5. **Validacion previa.** Un manifiesto cuya ULTIMA linea tiene dos campos en
   vez de tres falla antes de la primera ingesta.
6. **Nombre repetido.** Dos lineas con el mismo nombre de corpus fallan al
   validar.
7. **Aborto con nombre.** Si la segunda de tres lineas falla al ingerir, el
   codigo de salida es distinto de cero, el mensaje nombra ese corpus, y la
   tercera no se intenta.
8. **Repeticion.** Ejecutar dos veces el mismo manifiesto deja el mismo estado
   y no duplica chunks ni vinculos.
9. **Sin regresion.** La suite en verde, y dos ejecuciones seguidas con el
   mismo resultado.

## Documentacion

`docs/DESPLIEGUE.md`, seccion "Corpus reproducible": anade el manifiesto con un
ejemplo, la regla de exclusion, la resolucion relativa y el comportamiento ante
fallo. `CHANGELOG.md` en `[No publicado]`.

## Impacto de version

Adicion compatible: una clave nueva, ningun defecto cambiado y ningun
comportamiento distinto sin declararla. En la serie pre-1.0 sube PATCH.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x). Esta tarea se
prueba entera con el banco aislado del instalador.
