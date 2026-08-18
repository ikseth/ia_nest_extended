# Decision 0012: las capacidades reflexivas se componen, no se reenvian

Fecha: 2026-08-18

## Decision

Una capacidad es **reflexiva** cuando su respuesta describe LA PILA y no el
mundo: dice que capacidades hay, si el sistema esta sano, si su configuracion es
valida. Una capacidad reflexiva NO se puede reenviar sin mentir, porque la
respuesta de la capa de abajo es una respuesta sobre la capa de abajo, y quien
pregunta cree estar preguntando por el conjunto.

1. **`capability.list` pasa a SOBREESCRITA.** Esta capa declara su propio
   catalogo, obtiene el de abajo en ejecucion y devuelve la FUSION. Es la
   aplicacion directa de `ADR 0011`, puntos 9 a 11.
2. **De ese catalogo fusionado salen todas las pieles** -CLI hoy; REST y MCP en
   la fase 7c-. Una sola fuente, varios consumidores. Ninguna piel vuelve a
   llevar una lista escrita a mano.
3. **`runtime.health` y `config.validate` siguen REENVIADAS por ahora**, y el
   contrato lo dice explicitamente: responden por el core, no por la pila. Su
   composicion se abre cuando exista un consumidor que necesite el estado del
   conjunto -`pulse` observando, o la presentacion mostrando salud-, no antes
   (`core ADR 0035`).
4. **El resto del catalogo del core se sigue reenviando tal cual.**
   `model.list`, `domain.*`, `prompt.*`, `task.*` y `eval.run` hablan del mundo,
   no de la pila: reenviarlas es correcto y no hay nada que componer.

### Que cuenta como reflexiva, para no tener que decidirlo caso a caso

La pregunta falsable es: **si esta capacidad se reenvia sin tocar, la respuesta
sigue siendo cierta para quien pregunto a la capa mas externa?**

Si la respuesta es "no, porque omite lo que esta capa anade o sabe", es
reflexiva y hay que componerla. Si es "si, porque la respuesta no depende de
cuantas capas haya", se reenvia.

## Motivo

Verificado el 2026-08-18: pedir el catalogo a traves de esta capa devuelve
dieciseis capacidades, **ninguna de ellas propia**. Un cliente que descubra por
catalogo concluye que `memory.recall` y `knowledge.ingest` no existen.

Eso incumple la regla 3 de `meta ADR 0007` -extension aditiva: una capa nunca
degrada lo de abajo, y subir de capa siempre suma- por la via mas tonta posible,
que es reenviar correctamente. El mecanismo de reenvio funciona; lo que falla es
aplicarlo a una capacidad que habla de si misma.

El invariante del ente lo exige por partida doble: sin catalogo fusionado, cada
piel necesita una lista escrita a mano, y entonces cada capacidad nueva del core
obliga a editar esta capa. `ADR 0011` ya declaro esa lista estatica como
INTERINA; esta decision la retira.

## Consecuencia

- `docs/EXTENDED_CONTRACT.md` mueve `capability.list` de reenviada a
  sobreescrita, y declara que `runtime.health` y `config.validate` responden por
  el core.
- Esta capa gana un catalogo propio DECLARATIVO -sus capacidades, sus parametros
  y su proyeccion por interfaz-, que hasta ahora solo existia como lista de
  nombres y como codigo de la piel CLI.
- La lista estatica de `capabilities.py` se retira; el CLI construye su ayuda del
  catalogo fusionado y conserva la resolucion generica de `ADR 0011` punto 11
  para lo que no conozca.
- Es prerequisito de la fase 7c: REST y MCP se derivan del mismo catalogo, y
  escribirlas antes obligaria a rehacerlas.
- La fusion necesita al core en ejecucion. Eso **no** puede volver obligatoria su
  presencia: las capacidades que hoy funcionan sin core -`memory.maintain`,
  `runtime migrate`- deben seguir funcionando con el core apagado, y la ayuda
  degrada sin que ninguna capacidad deje de ser invocable.

## Alcance de la regla

Esta decision la toma esta capa para si misma. La regla, sin embargo, no tiene
nada de particular de la memoria ni del conocimiento: cualquier capa que envuelva
a otra tiene el mismo problema con las mismas tres capacidades.

Si una segunda capa del ente se topa con ello -`conscience` sobre esta, o la
presentacion sobre ambas-, la regla deja de ser de aqui y su hogar pasa a ser
`ia_nest_meta/docs/ARQUITECTURA_DE_CAPAS.md`, junto al contrato uniforme del que
se deriva (meta ADR 0007, convencion transversal 6). No se promueve todavia,
porque hoy hay un solo caso y promover doctrina desde un caso unico es como
congelar una costura sin consumidor.

## Impacto de version

Ninguno todavia: no hay contrato cortado. Cuando lo haya, componer una capacidad
que antes se reenviaba es adicion compatible -devuelve mas, no menos-, salvo que
cambiara la forma de la respuesta del core, que no es el caso.
