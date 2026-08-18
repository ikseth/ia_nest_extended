# Handoff de implementacion: catalogo propio y fusionado

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-18
Base: `main`, su ultimo commit.

Estado de contrato: reconciliado. Gobiernan `extended ADR 0012` (esta tarea lo
implementa), `extended ADR 0011` puntos 9 a 11, y `meta ADR 0007`.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/decision_records/0012-capacidades-reflexivas.md`. Es el encargo.
3. `docs/decision_records/0011-interfaz-de-consumo-contrato-uniforme.md`, puntos
   9, 10 y 11.
4. `ia_nest_meta/docs/ARQUITECTURA_DE_CAPAS.md`, reglas 1 a 3.
5. `core docs/CORE_CONTRACT.md`, seccion `capability.list`: la forma de lo que se
   va a fusionar. NO se copia aqui; se referencia.

No hace falta releer el resto del corpus doctrinal.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Objetivo

Que esta capa deje de reenviar `capability.list` -que hoy devuelve el catalogo
del core y ninguna capacidad propia- y pase a declarar el suyo, obtener el de
abajo en ejecucion y devolver la FUSION. De ese catalogo salen las pieles.

## Dentro de esta tarea

### 1. Catalogo propio, declarativo

Un modulo declarativo con las capacidades PROPIAS de esta capa, no una lista de
nombres. Por capacidad: nombre canonico, resumen corto, si transporta identidad,
si su respuesta es streaming, sus parametros (nombre, tipo, obligatoriedad,
valores admitidos, defecto) y su proyeccion por interfaz.

Las capacidades propias son las de `docs/EXTENDED_CONTRACT.md`: `memory_type.*`,
`memory.*` y `knowledge.*`. Declara TODAS, incluidas las que hoy no tienen
subcomando de CLI, con su hueco de interfaz explicito -igual que hace el core con
las suyas-. REST y MCP no existen todavia (fase 7c): su proyeccion es nula, y
declararla nula es distinto de no declararla.

Las dos capacidades `prevista` del contrato (`knowledge.retrieve`,
`knowledge.corpus.list`) NO se declaran: no tienen implementacion y anunciarlas en
un catalogo seria prometer lo que no existe.

### 2. Fusion

`capability.list` deja de reenviarse y pasa a capacidad SOBREESCRITA del
servicio. Devuelve la union de:

- las capacidades propias,
- las del core obtenidas EN EJECUCION, tal como las declare.

Reglas de la fusion, y son contrato:

- **Una capacidad sobreescrita aparece UNA sola vez**, con la declaracion de esta
  capa. Hoy son `prompt.run`, `reasoning.run` y `task.run`. No se devuelven dos
  entradas con el mismo nombre.
- **Una capacidad reenviada aparece TAL CUAL la declaro el core**, sin
  reescribir, sin filtrar y sin completar campos.
- **Una capacidad del core que esta capa no conozca aparece igualmente.** Es el
  invariante: el catalogo se obtiene, no se copia.
- Cada entrada declara su **procedencia** -propia, sobreescrita o reenviada-, que
  es informacion que un consumidor necesita para saber si lo que invoca lleva
  enriquecimiento. Es un campo aditivo y no altera la forma de lo que el core
  declaro.
- La respuesta declara la version de esta capa ademas de la del core. Ambas se
  publican; no se sustituye una por otra.

### 3. Las pieles salen del catalogo

El CLI construye su ayuda del catalogo fusionado y **se retira la lista estatica**
de `capabilities.py`, que `ADR 0011` ya declaraba interina.

Se conserva intacta la resolucion generica del punto 11: un `GRUPO ACCION` que no
aparezca en el catalogo se sigue resolviendo como capacidad reenviada. Conocerla
solo mejora la ayuda; nunca la habilita.

### 4. El core apagado no puede romper nada

**El catalogo hace falta para EXPLICAR, nunca para INVOCAR.** De ahi:

- Las capacidades que hoy funcionan sin core -`memory.maintain`,
  `runtime migrate`, y en general las propias que no lo necesitan- siguen
  funcionando con el core inalcanzable.
- Construir el parser NO puede exigir una llamada de red. El CLI se arma con el
  catalogo PROPIO, que es local; lo ajeno se pide solo cuando hace falta
  explicarlo: al pedir `capability list` o la ayuda general.
- Con el core inalcanzable, `capability.list` devuelve lo propio y declara que no
  pudo obtener lo de abajo, con la forma de error tipado del ente
  (`meta ADR 0009`). No inventa un catalogo vacio ni finge exito.

## Fuera de esta tarea (NO implementar)

- Componer `runtime.health` y `config.validate` (`ADR 0012`, punto 3: esperan
  consumidor).
- REST y MCP (fase 7c). El catalogo debe quedar LISTO para ellas, sin escribirlas.
- Cortar tag, mover `docs/DEPENDENCIAS.md`, tocar el core o el laboratorio.
- Suelo de relevancia en la memoria, y las deudas D3 y fase 6.
- Cambiar el comportamiento de ninguna capacidad ya existente. Esta tarea mueve
  el CATALOGO, no la ejecucion.

## Criterios de aceptacion (falsables)

1. **Lo propio es visible.** `capability.list` a traves de esta capa incluye
   `memory.recall` y `knowledge.ingest`. Hoy no las incluye: es el defecto que se
   corrige.
2. **Lo ajeno desconocido atraviesa.** Contra un stub que declare una capacidad
   que esta capa no conoce, esa capacidad aparece en el catalogo fusionado SIN
   tocar codigo de la capa.
3. **Sin duplicados.** Una capacidad sobreescrita aparece exactamente una vez, con
   la declaracion de esta capa.
4. **Reenviado intacto.** Una capacidad reenviada aparece con los campos que
   declaro el stub, incluidos los que esta capa no modela.
5. **Procedencia.** Cada entrada declara si es propia, sobreescrita o reenviada.
6. **Sin lista estatica.** `FORWARDED_CAPABILITIES` desaparece; ninguna prueba ni
   piel depende de ella.
7. **Ayuda derivada.** La ayuda del CLI para una capacidad propia sale del
   catalogo declarativo, no de texto escrito en la piel.
8. **Invocable sin catalogo.** Con el core inalcanzable: `memory maintain` se
   ejecuta, y un `GRUPO ACCION` desconocido sigue resolviendose por el camino
   generico.
9. **Fallo honesto.** Con el core inalcanzable, `capability.list` devuelve lo
   propio y declara el fallo de lo ajeno con error tipado; no devuelve una lista
   parcial fingiendo exito.
10. **Arranque sin red.** Construir el parser del CLI no realiza ninguna llamada
    de red. Prueba automatizada.
11. **Sin regresion.** La suite sigue en verde mas las pruebas nuevas.

## Entrega

Deja el trabajo STAGED sobre `main`, con `git add` por ruta explicita. **No crees
rama, no commitees, no hagas push.**

Actualiza `docs/EXTENDED_CONTRACT.md` (mover `capability.list` a sobreescrita y
declarar que `runtime.health` y `config.validate` responden por el core) y
`CHANGELOG.md` bajo `[No publicado]` con el impacto de version.

No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
