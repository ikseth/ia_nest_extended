# Handoff de retrabajo: la puerta se contamina a si misma

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-09-12.
Base: `main`, su ultimo commit, con `v0.2.1` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `docs/PUERTA_LABORATORIO.md`: el criterio, que NO cambia con este retrabajo.
2. `docs/handoff/puerta_script_brief.md`: el encargo original, que sigue
   vigente en todo lo que este no toca.

## Que paso

La puerta se ejecuto por primera vez contra un despliegue natural el
2026-09-12 y dio NO PASA con este reparto: L1 PASA, L2 0/3, L3 1/3, L4a 2/3,
L4b 1/3, L5 y L5r NO EJECUTABLE.

**Ninguno de esos fallos es de la capa.** La evidencia demuestra lo contrario:
en L2, `recall_contains_witness_stated_by_user` es `true` y el contexto
inyectado trae el testigo entero; en L3, el contexto muestra la anotacion de
contradiccion correcta y en el orden previsto. Lo que fallo es el instrumento,
de tres maneras.

## 1. Una sola identidad para toda la pasada (lo que mas importa)

Todas las lineas y todas las repeticiones usan el MISMO `user_id`. La memoria
episodica es de ambito USUARIO, asi que las sondas se contaminan entre si.

- L3, repeticiones 2 y 3: las tres comprobaciones en falso, pero el contexto
  contiene la anotacion correcta referida al testigo de la repeticion 1. Los
  engramas viejos desplazan al nuevo y la comprobacion busca el nuevo.
- L4b: su primer turno responde "La clave del refugio es Ambar", que es materia
  de L3. El hilo llega contaminado antes de empezar.

**Que se pide.** Un `user_id` propio por LINEA y por REPETICION, derivado del
identificador de la pasada para que siga siendo rastreable:
`puerta-<run_id>-<linea>-<repeticion>`. El `run_id` sigue siendo uno por
ejecucion y aparece en la evidencia.

No lo resuelvas con `namespace` ni borrando memoria entre sondas: la capa no
debe recibir borrados de una prueba, y el aislamiento por identidad es el que
la propia capa promete.

## 2. Testigos con punto de corte

El testigo es `Xanthe-0240ded11d` y el modelo responde `Xanthe`. El guion
invita a truncar y el oraculo exige literalidad, de modo que la sonda acaba
midiendo la fidelidad de transcripcion del modelo y no la memoria de la capa.

**Que se pide.** Testigos SIN punto de corte natural: una sola palabra
inventada, sin guiones, espacios ni puntuacion, y que siga siendo imposible de
adivinar (por ejemplo `Xanthezul9k2`). La comprobacion sigue siendo literal: no
la relajes, no aceptes prefijos y no normalices el testigo mas alla de
mayusculas y acentos, que ya estaba.

El par fijo de L4b (`martes`/`jueves`) se queda como esta: ahi no hay
truncamiento posible y el par es el punto del experimento.

## 3. L5 y L5r ya son ejecutables

El brief original mandaba declararlas NO EJECUTABLE mientras el instalador no
supiera declarar N corpus. Ya sabe (`CORPUS_MANIFEST`, v0.2.1) y el laboratorio
tiene 19 corpus confirmados, asi que la condicion caduco. No fue un error tuyo.

**Que se pide.** Que se ejecuten de verdad:

- **L5**: por cada sonda, una pregunta con `--domain` de un dominio con corpus
  confirmado. PASA si la recuperacion RAG devuelve al menos un fragmento.
- **L5r**: cortesia sin dominio. PASA si la recuperacion RAG devuelve CERO.

Sondas de L5, redactadas sin mirar el corpus, que es la regla de calibracion de
esta capa (una sonda que reformula el texto mide parecido literal, no
relevancia). Usa estas cinco literalmente:

    linux         como abro un puerto en el cortafuegos de mi servidor
    finanzas      cuanto tarda en duplicarse mi dinero al 6 por ciento anual
    agricultura   cuando conviene sembrar tomates
    medicina      que hago ante una quemadura leve
    cocina        como se hace un sofrito

Sondas de L5r: "hola, buenos dias", "gracias por tu ayuda", "que recuerdas de
mi".

**Limite declarado, y no lo escondas.** El criterio pide comprobar que aparece
el corpus ESPERADO, y eso exige el nombre del corpus. Si la superficie REST no
lo publica -compruebalo, no lo supongas-, implementa lo que si es verificable
(que recupera y que el ruido no) y DECLARA en la salida y en la evidencia que
la identidad del corpus no se comprueba por REST. Es el mismo trato que ya se
le dio al enlace `contradicted_by`.

Si un dominio con corpus flaco no recupera, eso es deuda de CORPUS y no un
fallo de la puerta: registra la sonda como fallida con su puntuacion y no
cambies umbrales para forzar el verde.

## Fuera de este retrabajo (NO implementar)

- Cambiar el criterio de `docs/PUERTA_LABORATORIO.md`.
- Relajar el oraculo, aceptar prefijos o juzgar con un modelo.
- Que L4b bloquee el codigo de salida. Sigue sin bloquear.
- Tocar la capa, el instalador, el core o el laboratorio.

## Criterios de aceptacion (falsables)

Contra el stub HTTP, como el resto de las pruebas del script.

1. **Identidad por sonda.** Dos lineas de la misma pasada, y dos repeticiones
   de la misma linea, usan `user_id` distintos, y todos comparten el prefijo
   del `run_id`.
2. **Sin contaminacion.** Con un stub que registre las peticiones, ninguna
   sonda recibe en su contexto contenido sembrado por otra.
3. **Testigos sin corte.** El testigo generado no contiene guion, espacio ni
   puntuacion, y la comprobacion sigue exigiendo el testigo completo.
4. **L5 ejecutable.** Con un stub que devuelve fragmentos, L5 PASA; con uno que
   devuelve cero para una sonda con dominio, NO PASA con su reparto.
5. **L5r ejecutable.** Con un stub que devuelve cero para cortesia, PASA; si
   devuelve algo, NO PASA.
6. **Limite declarado.** Si la identidad del corpus no es verificable por REST,
   la salida y el JSON lo dicen en claro.
7. **Sin regresion.** Las ocho pruebas anteriores del script siguen verdes, y
   la suite completa tambien.

## Impacto de version

Ninguno: el script es instrumental y no toca contrato publico ni comportamiento
de la capa.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x). Este retrabajo se
prueba entero contra el stub.
