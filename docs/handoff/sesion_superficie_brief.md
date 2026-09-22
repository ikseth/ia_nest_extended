# Handoff B: la superficie de sesiones

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, banco y laboratorio. NUNCA quien implementa.
Fecha: 2026-09-22.
Base: `main`, con la entrega A del ADR 0015 ya dentro (tabla `sessions`,
archivado por inactividad, `session_inactivity_seconds`).

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `docs/decision_records/0015-la-sesion-es-una-entidad.md`, puntos 5, 7 y 8.
2. `docs/decision_records/0014-la-capa-no-inventa-interlocutores.md`, para saber
   que NO se implementa aqui.
3. `docs/EXTENDED_CONTRACT.md`: como se declara una capacidad propia.
4. La entrega A en `src/ianest_extended/` (tabla `sessions`, `maintain`,
   `identity.py`): esto se monta encima.

## Que se pide

La entrega A hizo que el hilo exista. Esta lo hace **visible y manejable**.

### 1. Tres capacidades propias

`session.list`, `session.show`, `session.new`. Se declaran como capacidades de
la capa, con el patron que ya usan `memory.*` y `knowledge.*`, y por tanto
alcanzables por **REST, MCP y CLI**, no solo por la CLI.

- **`session.list`**: las sesiones **del `user_id` que pregunta**. No hay vista
  global (ADR 0015, punto 7). Por defecto solo las activas; con filtro se ven
  las archivadas. Cada fila: identificador, creacion, ultima actividad, estado y
  titulo.
- **`session.show`**: una sesion, con sus tiempos, su estado y sus marcas de
  ciclo de vida. Debe funcionar tambien con una sesion archivada.
- **`session.new`**: crea una sesion y devuelve su identificador.

### 2. El titulo sale del resumen, y no se inventa

El titulo es el `thread_summary` mas reciente de esa sesion, recortado.
**Derivado en la lectura, no almacenado**: una copia en la tabla se queda vieja
y hay que sincronizarla, y no vale la pena.

Si la sesion no tiene resumen -la sintesis esta apagada por defecto-, **no hay
titulo**. No lo fabriques del primer turno ni de ninguna otra cosa: una sesion
sin nombre se identifica por su id, que es lo que hace el operador cuando la
nombra el (`cine_20260926`).

### 3. La CLI dice en que hilo estas

Al invocar un comando que use memoria, una linea indicando la sesion en curso.

**Va por stderr, no por stdout.** La respuesta del modelo se canaliza y se pega
en otros sitios; un aviso mezclado ahi la ensucia.

### 4. Hilos paralelos por variable de entorno

`IANEST_EXTENDED_SESSION_ID`, para poder llevar hilos distintos en terminales
distintos, que con un fichero unico no se puede.

Precedencia, y documentala: `--session-id` gana a la variable, y la variable
gana al fichero recordado.

### 5. Subcomandos de la CLI

`session list`, `session show`, `session new`, con el patron de los grupos que
ya existen. `session new` ademas **pasa a ser la sesion recordada**, que es el
sentido de crearla desde la CLI.

## Lo que NO entra

- **Exigir `user_id` y `session_id` en REST/MCP**: es el ADR 0014, entrega C, y
  va despues a proposito, para que los clientes tengan antes con que cumplir.
- Tocar el reloj, el archivado o la migracion de la entrega A.
- Nada de `episodic` ni de la enmienda del ADR 0002: se decidio, no se
  implementa aqui.
- Cerrar sesiones a mano: `cerrada` es de conscience.

## Criterios de aceptacion, falsables

1. `session.list` de un usuario NO muestra las sesiones de otro, ni siquiera si
   comparten el texto del identificador.
2. Por defecto lista activas; con el filtro aparecen las archivadas.
3. `session.show` de una archivada responde, con su estado y su `archived_at`.
4. `session.new` crea la sesion y, desde la CLI, pasa a ser la recordada.
5. Con resumen, el titulo es ese resumen recortado. **Sin resumen, no hay
   titulo**, y no se inventa ninguno.
6. `--session-id` gana a `IANEST_EXTENDED_SESSION_ID`, y esta al fichero.
7. El aviso del hilo sale por **stderr**: redirigir stdout deja la respuesta
   limpia.
8. Las tres capacidades aparecen en el catalogo y responden por REST y por MCP,
   no solo por CLI.
9. Sin regresion: `python -m pytest -q` con `IANEST_EXTENDED_TEST_DSN` definido,
   **verde y sin skips**.

## Que entregar

Trabajo en el ARBOL sobre la rama activa: sin commit, sin push, sin cambiar de
rama. `CHANGELOG.md` bajo `[No publicado]` -adicion de capacidades: MINOR en
serie pre-1.0-. Documentos sin acentos ni tildes. Ejecuta `python -m pytest -q`
al terminar y reporta el resultado EXACTO.

En el informe final: que cambiaste fichero a fichero, los nueve criterios uno a
uno con su prueba y si la ejecutaste, el resultado de pytest, y cualquier
inconsistencia detectada sin corregirla.
