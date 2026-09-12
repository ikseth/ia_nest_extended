# Handoff: la contradiccion no se detecta entre namespaces

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-09-12.
Base: `main`, su ultimo commit, con `v0.2.2` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/decision_records/0013-...md`, ENTERO, y en especial su enmienda del
   2026-09-12.
3. `docs/PUERTA_LABORATORIO.md`, fila L3 y la nota que explica por que la
   anotacion deja de ser criterio.
4. `docs/POLITICA_WRITEBACK.md`.

## El problema, medido

Dos ejecutores independientes pasaron la puerta sobre el MISMO despliegue
natural y dieron veredictos distintos. La unica linea que difiere es L3, y
sumando las tres pasadas la anotacion de contradiccion salio en **6 de 9**
repeticiones sin que nada cambiara en el producto.

La causa esta identificada y no es la banda de similitud:
`record_contradiction` compara dentro del MISMO namespace
-`WHERE type_name = ? AND user_id = ? AND namespace = ?`- y el namespace lo
elige el modelo de extraccion. Medido en la pasada cruzada:

    [episodic/tasks]  (fuente: usuario) La clave del refugio es Ambar5f3929594d
    [episodic/facts]  (fuente: modelo, sin verificar) ... Cobalto5f3929594d

Misma frase, distinto cajon: el candidato del modelo ni siquiera entra en la
comparacion.

## Parte 1: la deteccion compara por tipo, no por cajon

**Que se pide.** Que `record_contradiction` busque candidatos dentro del mismo
`type_name` y `user_id`, SIN filtrar por `namespace`.

Motivo, y define el alcance: una contradiccion es sobre el CONTENIDO, no sobre
el cajon donde el extractor lo puso. El riesgo de comparar mas candidatos esta
acotado por dos cosas que el ADR 0013 ya decidio y que NO cambias: la banda de
similitud sigue gateando, y la accion no es destructiva -anota y despriorza, no
retira-.

Lo que NO cambia:

- El resto del filtro: mismo tipo y mismo usuario siguen siendo condicion.
- Los umbrales `conflict_threshold` y `dedup_threshold`, ni sus defectos.
- `EngramStatus.SUPERSEDED` sigue sin usarse.
- El enlace sigue siendo `contradicted_by` en `memory_links`, y la unica fuente
  de verdad.

## Parte 2: L3 de la puerta deja de exigir la anotacion

Ya reconciliado y escrito en `docs/PUERTA_LABORATORIO.md`. En
`tools/lab/puerta.py`:

- **L3 PASA con la etiqueta de procedencia y el orden**: el candidato del modelo
  aparece etiquetado como del modelo y DETRAS de la version del usuario.
- **La anotacion de conflicto se sigue comprobando y se registra con su tasa**
  (por ejemplo `anotacion 2/3`) en la salida humana y en el JSON, pero NO decide
  el veredicto.
- Motivo: en nueve repeticiones L4a paso 3/3 incluso cuando la anotacion no
  disparo. Lo que sostiene el comportamiento es la procedencia; la anotacion es
  refuerzo, y un refuerzo no debe suspender la puerta.

## Parte 3: el script no dice nada durante diez minutos

Una pasada tarda entre 8 y 12 minutos y no imprime NADA hasta el final. El
operador la dio por colgada, con razon.

**Que se pide.** Progreso por stdout a medida que avanza: una linea corta por
sonda terminada, con linea, repeticion y veredicto parcial, y el resumen final
igual que ahora. Sin dependencias nuevas y sin barras de progreso: texto plano,
que puede acabar en un fichero de registro.

## Fuera de este encargo (NO implementar)

- Tocar umbrales o defectos de configuracion.
- Cambiar el resto del criterio de la puerta.
- Tocar el core, el instalador ni el laboratorio.

## Criterios de aceptacion (falsables)

1. **Detecta entre namespaces.** Un candidato `stated_by=model` en
   `episodic/facts` y una afirmacion del usuario en `episodic/tasks`, con
   similitud dentro de la banda, produce el enlace `contradicted_by`. Prueba con
   PostgreSQL, con skip explicito si no hay DSN, como el resto del banco.
2. **Sigue acotado por tipo y usuario.** Un candidato de OTRO `user_id`, o de
   otro `type_name`, no se anota aunque el texto sea identico.
3. **La banda sigue gateando.** Por debajo de `conflict_threshold` no se anota;
   por encima de `dedup_threshold` se refuerza como hasta ahora.
4. **No destructivo.** El candidato anotado conserva `status=active`.
5. **L3 por etiqueta y orden.** Con un stub cuyo contexto etiqueta y ordena bien
   pero NO trae anotacion, L3 PASA y la salida declara la tasa de anotacion.
6. **L3 sigue fallando cuando toca.** Sin etiqueta, o con el candidato del
   modelo delante de la version del usuario, L3 NO PASA.
7. **Progreso.** Ejecutada contra el stub, la salida emite al menos una linea por
   sonda antes del resumen final, y el resumen no cambia de forma.
8. **Sin regresion.** Suite completa en verde.

## Impacto de version

Parte 1: correccion de comportamiento en el write-back; la forma de lo que
devuelven `memory.recall` y `memory.write` no cambia. PATCH en la serie pre-1.0.
Partes 2 y 3: instrumentales, sin impacto.

Documenta la parte 1 en `CHANGELOG.md` y, si `docs/POLITICA_WRITEBACK.md`
describe el alcance de la deteccion, alinealo ahi tambien.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x): la parte 1 se
prueba con el banco de PostgreSQL y las partes 2 y 3 con el stub.
