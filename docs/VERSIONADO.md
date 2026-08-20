# Versionado de ia_nest_extended

Estado: activo
Version: 1.0 - 2026-08-14

La POLITICA de versionado es comun al ente y vive en
`ia_nest_meta/docs/POLITICA_SEMVER.md`: esquema `MAJOR.MINOR.PATCH`, el tag como
fuente de verdad, que numero subir y el proceso de publicacion.

Este documento fija lo que solo esta capa puede fijar: QUE cuenta como su
contrato publico. Cierra el PENDIENTE que `docs/DEPENDENCIAS.md` arrastraba y sin
el cual no se puede cortar el primer tag.

## Que es "contrato publico" (lo que gobierna la version)

Cuenta como contrato:

1. **Las capacidades propias** de `docs/EXTENDED_CONTRACT.md` (`memory_type.*`,
   `memory.*`, `knowledge.*`): nombres, parametros y forma de respuesta.
2. **La garantia de transparencia**: que esta capa reexpone el contrato del core
   del rango declarado en `docs/DEPENDENCIAS.md` sin alterar su semantica. Lo que
   se versiona aqui es LA GARANTIA, no el catalogo ajeno.
3. **Los parametros de extension del enriquecimiento**: activar o desactivar el
   enriquecimiento, desactivar una fuente, dominio explicito o automatico; y los
   nombres de las fuentes declaradas.
4. **El registro de tipos de memoria**: nombres de tipo, namespaces, tier,
   scopes y `writer_principal`. Es la superficie contra la que escriben
   `conscience` y lee `ia_nest_web`.
5. **El esquema de telemetria propio**: nombres de evento, contadores y campos.
6. **La taxonomia de errores** de la capa. Su FORMA (campos y propagacion entre
   saltos) sigue la del ente cuando exista en el taller; el catalogo es de aqui.
7. **El esquema de configuracion** `IANEST_EXTENDED_*` y la superficie
   CLI/REST/MCP.

## Que NO cuenta como contrato

- El esquema de la base de datos y sus migraciones. Son internos: la base se toca
  por capacidades, nunca directamente. Un cambio de esquema que no altere ninguna
  capacidad no sube version.
- Los adaptadores, los puertos internos y la estructura de modulos.
- Los harnesses de desarrollo (`python -m ianest_extended.*`), provisionales por
  definicion y retirados en la Fase 7a.

## Por que el catalogo del core no se re-declara aqui

Copiarlo crearia un segundo hogar del mismo documento, contra la convencion
transversal 6 (meta ADR 0008), y ataria la version de esta capa a cada cambio del
core aunque esta capa no prometa nada nuevo.

Consecuencia practica: una rotura del contrato del core NO es por si misma una
rotura del contrato de esta capa. Mueve el rango de `docs/DEPENDENCIAS.md`, y
esta capa sube version solo si cambia lo que ELLA promete, incluida su garantia
de transparencia (por ejemplo, si dejara de poder reexponer una capacidad).

## Que numero subir

Regla comun del ente. Esta capa esta en la serie pre-1.0 (`0.y.z`): un cambio que
rompe contrato sube MINOR y una adicion compatible o correccion sube PATCH.

Concreciones de este repo:

- Manifiesto de version: `pyproject.toml` (`version`).
- Los tags se cortan sobre `main`, y no los corta un agente por su cuenta.
- **Rompen contrato**: quitar o renombrar una capacidad propia; cambiar de forma
  incompatible el registro de tipos de memoria; renombrar eventos o columnas de
  telemetria; cambiar la taxonomia de errores de forma incompatible; dejar de
  reexponer una capacidad del core; degradar o filtrar lo reenviado.
- **Adicion compatible**: capacidad propia nueva; fuente de enriquecimiento
  nueva; campo aditivo; bandera nueva de CLI.

## Primer tag

Cortado en la Fase 7d como `0.1.0` (2026-08-20). Requisitos, y como se
cumplieron:

1. Este documento. Hecho desde el 2026-08-14.
2. `docs/EXTENDED_CONTRACT.md` en estado `activo`. Hecho al cortar.
3. **El contrato ejercido por al menos un consumidor real.** Lectura explicita,
   reconciliada con el usuario el 2026-08-20: la intencion del requisito es no
   congelar un contrato que nadie ha usado -leccion de `core ADR 0035`-, y se
   cumple porque el contrato se ejercio ENTERO por las tres pieles, contra
   modelos, corpus y almacen reales. Ejercerlo destapo defectos que ninguna
   prueba con stub veia: un `task.run` que expiraba con la configuracion de
   fabrica, una colision de banderas que solo aparecia con el core vivo, y un
   catalogo que devolvia dieciseis capacidades y ninguna propia.

   **Riesgo residual, declarado y no disimulado:** el ejercicio lo hizo el
   operador, no otra capa. Cuando `conscience` o `ia_nest_web` lo consuman
   encontraran cosas que aqui no se vieron. La serie `0.y.z` existe para eso: no
   promete estabilidad, promete que los cambios se declaran.

Al cortarlo se actualiza la fila de esta capa en
`ia_nest_meta/docs/REGISTRO_CAPAS.md`.
