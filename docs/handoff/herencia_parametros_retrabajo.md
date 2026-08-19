# Retrabajo: la herencia de parametros rompe el CLI cuando el core responde

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Fecha: 2026-08-19
Base: la rama de trabajo de `docs/handoff/herencia_parametros_brief.md`.

El brief original sigue vigente. Esto corrige dos defectos hallados al ejercer la
implementacion contra un core real, y anade la decision de diseno que faltaba.

## Defecto 1 (bloqueante): colision de banderas

Con el core ALCANZABLE, todos los comandos abortan, incluidos los propios:

    argparse.ArgumentError: argument --domain: conflicting option string: --domain

Causa: el catalogo del core declara un parametro `domain`, y esta capa ya tiene su
propio `--domain` unificado -gate de conocimiento, ruteo y faceta de memoria en un
solo valor, `ADR 0011` punto 8, divergencia deliberada-. Al derivar banderas del
catalogo se anade una segunda `--domain` y argparse aborta la construccion entera.

El modo de fallo es el peor posible: **el CLI solo se rompe cuando el despliegue
funciona.** Sin core alcanzable, no hay catalogo remoto y no hay colision.

**Regla, y es una sola, derivada del dato:** las banderas que esta capa YA POSEE
-identidad, enriquecimiento y salida- tienen precedencia. Un parametro del
catalogo cuyo nombre colisione con una de ellas NO se vuelve a declarar; lo
gobierna la bandera de la capa. No es una excepcion para `domain`: es la regla
para cualquier colision presente o futura, sin lista escrita a mano de casos.

La ayuda de esa capacidad debe decir que ese parametro lo gobierna la bandera de
la capa, para que el operador no crea que se ignora.

## Defecto 2: el parser consulta la red

La rebanada anterior fijo que construir el parser fuese puramente local, y su
prueba sigue en verde porque llama a `_build_parser()` sin argumentos, que es el
camino local. El fetch ocurre en `main()`, de modo que la prueba mide una funcion
y no el flujo real.

**La prueba debe ejercer el punto de entrada real** (`cli.main`) contra un stub
alcanzable, y fallar si durante el analisis de argumentos se pide el catalogo.

## Decision de diseno que faltaba: el catalogo remoto se CACHEA

Hay una tension real que el brief original no resolvio: para ofrecer
`task plan --effort` hay que conocer los parametros del core, y eso exige el
catalogo remoto; pero el parser no puede pedirlo por red.

Se resuelve con cache local, no relajando la regla:

1. El parser se construye SIEMPRE desde fuentes locales: el catalogo propio, mas
   el catalogo remoto CACHEADO si existe. Nunca hay red en ese camino.
2. `capability.list` sigue consultando el catalogo remoto en vivo -es su
   cometido- y **actualiza la cache** como efecto. Refrescar es, para el
   operador, ejecutar `capability list`.
3. Sin cache y sin core, las capacidades propias conservan sus banderas y lo
   ajeno se sigue invocando por `--param`. Degradado, nunca roto.
4. La cache es estado local, no configuracion: vive junto al estado que la capa
   ya persiste localmente y no se versiona.
5. Una cache de un core distinto del configurado no se usa: se declara de que
   origen es y, si no coincide, se ignora y se degrada como si no existiera.

Esto conserva el criterio que gobierna todo el diseno -el catalogo hace falta
para EXPLICAR, nunca para INVOCAR- y ademas lo mejora: ahora tambien se explica
sin core delante.

## Criterios de aceptacion (falsables)

1. **No hay colision.** Con un catalogo -propio o cacheado- que declare un
   parametro llamado como una bandera propia de la capa, el parser se construye y
   el CLI funciona. Prueba automatizada.
2. **Gana la bandera de la capa.** En ese caso el valor que llega al core es el de
   la bandera propia, y no se envia dos veces ni se pisa en silencio.
3. **Regla general, no excepcion.** La prueba usa un nombre de parametro
   cualquiera que colisione, no `domain`, para demostrar que no hay lista de
   casos escrita a mano.
4. **El parser no toca la red, de verdad.** Prueba sobre `cli.main` contra un stub
   ALCANZABLE: analizar argumentos no pide el catalogo. Debe fallar si se pide.
5. **La cache se escribe.** `capability list` deja la cache actualizada.
6. **La cache se usa.** Con el core inalcanzable pero cache presente, las
   capacidades ajenas conservan sus banderas derivadas.
7. **Cache de otro origen.** Una cache cuyo origen no coincida con el core
   configurado se ignora, y el CLI degrada a `--param` sin fallar.
8. **Sin cache y sin core.** Las propias conservan banderas; lo ajeno se invoca
   por `--param`; nada aborta.
9. **Los criterios 5, 6 y 7 del brief original, con prueba propia.** Entrada de
   fichero que rellena varios parametros; colision fichero/bandera como error
   tipado; `--param` como escape y su colision con una bandera declarada. Fueron
   implementados sin prueba aislada y hay que cubrirlos.
10. **Sin regresion.** La suite en verde, y el CLI verificable a mano contra un
    core alcanzable sin abortar.

## Entrega

Deja el trabajo en el arbol de trabajo, sobre la rama actual. No crees rama, no
commitees, no hagas push. No entres al laboratorio.
