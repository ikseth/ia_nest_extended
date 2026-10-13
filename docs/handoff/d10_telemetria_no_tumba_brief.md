# Handoff de implementacion: D10, la telemetria no tumba la peticion

Destinatario: agente codificador (Codex).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus sobre el banco y el laboratorio. NUNCA quien implementa.
Fecha: 2026-10-13. RECONCILIADO con el operador el 2026-10-13.
Base: `main`, con D8 y D9 ya entregadas (tercera entrega del hito v0.5.0).

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PLAN.md`, seccion "Hito v0.5.0" y deuda **D10**.
3. En el codigo: `TelemetryWriter` (`src/ianest_extended/telemetry.py`);
   `write_catalog_cache` (`src/ianest_extended/catalog_cache.py`) como precedente
   de escritura de mejor esfuerzo; y el bloque final de `deploy/setup.sh`, desde
   `write_setup_snapshot` hasta `verify_runtime`.

## Por que existe este encargo, medido

La CLI no es cliente del servicio: construye la capa en su propio proceso, con
el usuario que la lanza. CLI y servicio escriben en el mismo fichero de
telemetria, uno por dia, que crea el primero que escribe.

En el laboratorio (2026-09-30 y 2026-10-11) el operador uso la CLI como root
antes de que el servicio escribiera ese dia. El fichero nacio de root, el
servicio (que corre como `OPERATOR_USER`) no pudo anadir,
`TelemetryWriter.record` propago el `PermissionError`, y REST y MCP devolvieron
error interno a TODA peticion hasta el dia siguiente.

El instalador puede provocar lo mismo: corre como root e invoca la CLI para
ingerir el corpus DESPUES de su `chown -R` del directorio de estado.

## Lo que se pide

1. **`TelemetryWriter.record` no lanza.** Si la linea no se puede serializar o
   escribir, se emite UNA linea por stderr (ruta del fichero, clase y mensaje
   del error; nunca el contenido del evento) y la llamada vuelve. El aviso sale
   una vez por proceso y por pareja (ruta, clase de error). La linea se pierde:
   sin reintento, sin cola, sin fichero alternativo. La contencion va en ese
   unico punto, no en cada llamada, y cubre `Exception`, no `BaseException`.
2. **El instalador devuelve el estado a `OPERATOR_USER` al terminar de usar la
   CLI.** Se repite el `chown -R` del directorio de estado despues de
   `ingest_corpus` y antes de `install_services`. El que ya existe se queda.
3. **Una frase en `docs/DESPLIEGUE.md`:** la CLI instalada se usa como
   `OPERATOR_USER`; usada como otro usuario puede dejar ficheros de estado que
   el servicio no pueda escribir, y ese dia el servicio no registra telemetria.

## Lo que NO entra (y si lo haces, esta mal)

- Que el wrapper o la CLI cambien de usuario, grupos, setgid, umask o ACL.
- Que la CLI pase a ser cliente del servicio. Esta decidido como direccion y es
  el hito siguiente; aqui no se toca.
- Rotacion, retencion, formato o campos de la telemetria.
- Declarar en `health` o en cualquier salida que la telemetria falla.
- `remember_session_id`, las units de systemd, el core, el laboratorio.

## Criterios de aceptacion (falsables)

Un directorio sin permiso de escritura NO sirve como doble: si la suite corre
como root, escribe igual. Usa un fallo que no dependa del usuario, por ejemplo
un `telemetry_dir` cuyo padre es un fichero regular.

1. **`record` no lanza** con un directorio de telemetria imposible de crear.
2. **Aviso unico y sin contenido.** stderr recibe una linea con la ruta y el
   error; cien llamadas seguidas dan UNA linea; la linea no contiene el
   `request_id`, la identidad ni los `details`.
3. **Serializacion contenida.** Un `details` no serializable tampoco lanza, y
   avisa.
4. **La operacion sobrevive.** Con la telemetria rota, `prompt.run` por el
   servicio (dobles del banco) devuelve la misma salida que con la telemetria
   sana, y la misma peticion por REST devuelve 200.
5. **Recuperacion sin reinicio.** Si el fallo desaparece, la siguiente llamada
   del mismo `TelemetryWriter` escribe su linea.
6. **Orden en el instalador.** En el banco de `tests/test_deploy_setup.py`, con
   sus dobles y su registro de llamadas: hay un `chown -R` del directorio de
   estado posterior a la ultima invocacion de la CLI y anterior al arranque de
   los servicios.
7. **Sin regresion.** Suite completa en verde CON PostgreSQL y sin skips.

## Lo que NO verifica este encargo

El criterio del hito se mide en el laboratorio: crear como root el fichero de
telemetria del dia y comprobar que REST y MCP siguen respondiendo. Lo hace Opus
y NO forma parte de esta entrega.

## Impacto de version

Correccion de un defecto, sin cambio de contrato: **PATCH**. Entrada en
`CHANGELOG.md`.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x, banco incluido).
