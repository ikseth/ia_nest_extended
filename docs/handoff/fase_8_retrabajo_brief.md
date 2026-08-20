# Retrabajo fase 8: el paquete no lleva sus migraciones

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Fecha: 2026-08-20
Base: la rama de trabajo de `docs/handoff/fase_8_instalador_brief.md`.

El instalador se probo en una maquina limpia -el criterio de salida de la fase- y
FALLO. El brief original sigue vigente; esto corrige lo que la prueba destapo.

## Defecto 1 (bloqueante): los SQL de migracion no viajan con el paquete

    FileNotFoundError: .../venv/lib/python3.13/db/migrations/0001_memory_registry.sql

Causa: `db/migrations/*.sql` vive FUERA de `src/` y el paquete no los declara como
datos. En una instalacion EDITABLE el repositorio esta en disco y la ruta relativa
funciona; en una instalacion REAL el wheel no los incluye y `runtime migrate`
revienta.

**Por que no se habia visto nunca**: la suite, el laboratorio y todo el desarrollo
corrian sobre `pip install -e`, que es el unico modo que oculta este error. Es la
version de empaquetado del mismo patron que ya nos costo tiempo tres veces: un
verde que no significaba lo que parecia.

**Que se pide.** Que las migraciones formen parte del paquete instalado y se
localicen por el mecanismo de recursos del propio paquete, no por una ruta
relativa al arbol de trabajo. La forma la elige quien implementa -moverlas dentro
de `src/ianest_extended/` y leerlas como recurso es lo directo-, con dos
condiciones:

1. Funciona igual en instalacion editable y en instalacion real.
2. No se duplica el contenido de los SQL: hay una sola copia, no una en `db/` y
   otra dentro del paquete.

## Defecto 2: el almacen provisionado no sobrevive a un reinicio

Verificado el 2026-08-20: al reiniciar el anfitrion, el contenedor del almacen no
volvio -su compose no declara politica de reinicio- mientras el del backend de
modelos si volvio, porque el suyo declara `unless-stopped`. La capa se queda sin
almacen y nadie avisa.

Se pide que `deploy/postgres.compose.yaml` declare politica de reinicio, como ya
hace el compose del backend en el core.

## Defecto 3 (menor): el fallo de red no se distingue del fallo de paquete

Cuando la maquina aun no tiene salida a internet, el instalador muere con cinco
reintentos de `pip` y un `Network is unreachable` enterrado. El operador no puede
distinguir "no hay red" de "el paquete no existe".

Se pide una comprobacion previa de alcance del indice de paquetes, con mensaje
propio. Es la misma familia que el hallazgo que esta capa reporto al core sobre su
endpoint sin resolver.

## Criterios de aceptacion (falsables)

1. **Instalacion real.** Instalado el paquete SIN modo editable en un entorno
   limpio, `runtime migrate` encuentra sus migraciones y termina bien.
2. **Instalacion editable.** Lo mismo sigue funcionando en editable.
3. **Una sola copia.** Los SQL no estan duplicados en dos sitios del repositorio.
4. **Prueba que lo habria cazado.** Una prueba automatizada que falle si las
   migraciones dejan de ser alcanzables desde el paquete instalado. Sin ella, esto
   vuelve.
5. **Reinicio del almacen.** El compose declara politica de reinicio.
6. **Red ausente.** Sin salida a internet, el instalador falla con un mensaje
   propio que nombra la red, no con un volcado de reintentos de pip.
7. **Sin regresion.** La suite en verde.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. No cambies de rama,
no crees rama, no commitees, no hagas push. No entres al laboratorio.

NO marques la fase 8 como cerrada: se cierra cuando la instalacion en maquina
limpia termine bien, y eso lo comprueba el revisor.
