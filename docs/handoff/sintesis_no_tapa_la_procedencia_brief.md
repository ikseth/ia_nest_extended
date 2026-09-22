# Handoff: la sintesis no puede tapar la procedencia

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, banco y laboratorio. NUNCA quien implementa.
Fecha: 2026-09-22.
Base: `main`, su ultimo commit, con `v0.3.1` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `docs/PUERTA_LABORATORIO.md`, lineas L3, L4a y L4b.
2. `docs/decision_records/0013-...md`, decision 4 y su enmienda del 2026-09-12.
3. `docs/decision_records/0007-...md`, enmienda del 2026-09-12.
4. `docs/POLITICA_WRITEBACK.md`, seccion de sintesis de hilo.

## Lo medido, y es el motivo entero

Con la sintesis encendida y ventana 3, en el laboratorio:

    L4b  el usuario se corrige a si mismo   sin sintesis 2/15   con sintesis 9/9
    L4a  el usuario corrige al modelo       sin sintesis 9/9    con sintesis 6/9

La fase arregla el caso para el que se diseno **y estropea el que ya
funcionaba**. Causa observada en los resumenes reales:

    "La clave del refugio es Cobalto9de48fcf59."
    "La clave del refugio es Cobalto... La clave del refugio es Ambar... OK. LISTO."

El primero conserva SOLO la version del modelo. Y al sustituir, la sintesis
-que es `stated_by=unknown`- retira del contexto los engramas que llevaban
`(fuente: modelo, sin verificar; hay una version del usuario sobre esto)`.
Es decir, **destruye la senal que hacia funcionar el ADR 0013**.

## La regla que se pide

**Un engrama implicado en una contradiccion no lo sustituye la sintesis: se
compone junto a ella.**

Implicado significa cualquiera de los dos lados del enlace `contradicted_by`:
el candidato anotado y el item del usuario que lo anota.

Concretamente, en la composicion del recall (`enrichment.py`): al construir el
conjunto de ids sustituidos por una sintesis, **excluir los que participan en
una contradiccion**. El resto se sigue sustituyendo, porque ahi esta el ahorro
de presupuesto que la fase promete.

Lo que NO cambia:

- La sintesis se sigue generando igual, con su ventana y sus enlaces.
- Los engramas no implicados en contradicciones se siguen sustituyendo.
- El recorte por presupuesto sigue actuando: si no cabe todo, recorta como hoy.
- Con la fase apagada, nada cambia.

## Un cambio, una medida

**NO toques el prompt de sintesis en este encargo**, aunque veas que produce
ruido ("OK. LISTO.") y que a veces se queda con la version equivocada. Eso es
real y se arregla aparte: si cambiamos las dos cosas a la vez no sabremos a cual
atribuir la mejora, y esta fase ya nos ha ensenado lo caro que es medir mal.

## Criterios de aceptacion (falsables)

1. **Coexistencia.** Con sintesis y un candidato anotado por contradiccion, el
   contexto compuesto contiene la sintesis Y los engramas implicados, con sus
   etiquetas de procedencia intactas.
2. **La sustitucion sigue viva.** Los engramas de la ventana NO implicados en
   contradicciones no aparecen en el contexto cuando hay sintesis.
3. **Orden.** Los implicados conservan el orden que exige L3: la version del
   usuario delante de la del modelo.
4. **Presupuesto.** El contexto compuesto sigue respetando el limite; si no
   cabe, recorta por el criterio de siempre.
5. **Apagada, identica.** Con `thread_synthesis_enabled=false`, el contexto es
   el de hoy, bit a bit.
6. **PostgreSQL.** Prueba end to end del caso completo: sembrar candidato del
   modelo, contradecirlo, generar sintesis y comprobar 1, 2 y 3.
7. **Sin regresion.** Suite completa en verde, con PostgreSQL y sin skips.

## Impacto de version

Cambia el comportamiento de una funcion que esta APAGADA por defecto, y no toca
contrato: **PATCH** en la serie pre-1.0.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x, banco incluido).
