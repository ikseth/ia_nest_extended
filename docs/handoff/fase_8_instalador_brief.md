# Handoff de implementacion: fase 8, despliegue reproducible

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-20
Base: `main`, su ultimo commit, con `v0.1.0` publicada y la fase 7 cerrada.

Estado de contrato: reconciliado. La fase esta declarada en `docs/PLAN.md`.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PLAN.md`, fase 8: alcance y criterio de salida.
3. `install.sh` de este repo: es un preparador de entorno de DESARROLLO -venv,
   PostgreSQL en docker, pytest-. **No es lo que se pide y no se sustituye**; se
   deja como esta.
4. `core deploy/setup.sh` y `core deploy/ejemplo.setup.conf` como REFERENCIA de
   forma: layout declarativo, fichero de parametros, verificacion al terminar. No
   se copia; se espeja.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## El problema

Esta capa **no se sabe instalar**. Todo lo que hace falta para que funcione se
monto a mano, comando a comando: el venv, la configuracion, el almacen en otro
anfitrion, el modelo de embeddings, el esquema, el corpus y sus vinculos, los
comandos en el PATH, y ahora dos servicios -REST y MCP- que solo estan vivos
porque alguien los lanzo.

Si manana se levanta otra maquina, no hay con que reconstruirlo. Es la diferencia
entre "funciona donde se monto" y "se despliega", y ahora que la capa tiene
version publicada pesa mas.

## Dentro de esta tarea

### 1. `deploy/setup.sh` con fichero de parametros

Mismo layout que el core: `/opt/ia_nest/{repositories,config,state}`, con la
configuracion de esta capa en `config/extended/` y FUERA del repositorio. Hoy su
`.env` vivia dentro del arbol de trabajo, y eso ya se corrigio a mano; el
instalador debe hacerlo bien de origen.

Un `deploy/ejemplo.setup.conf` documentado con los parametros. Como minimo:
nombre de instancia, DSN del almacen, endpoint de embeddings, host y puerto de
REST, host y puerto de MCP, si se instalan y habilitan servicios, ruta del corpus
a ingerir, y nivel de verificacion.

### 2. El almacen: parametro, con las dos vias

Espeja la decision del core con su backend (`PROVISION_BACKEND`): el instalador
acepta un DSN de un almacen YA EXISTENTE, o lo provisiona si se le pide y hay
runtime de contenedores. La maquina objetivo puede no tener docker -es el caso
hoy-, asi que **apuntar a un almacen remoto debe ser un camino de primera clase,
no un apano**.

En los dos casos: verificar conectividad y ejecutar la migracion del esquema.

### 3. Conocimiento reproducible

Si el fichero de parametros declara una ruta de corpus, el instalador **ingiere y
confirma los vinculos** dominio-corpus.

Decision de diseno, y va escrita porque no es inferible: **se ingiere TEXTO, no se
clonan vectores.** Los embeddings son derivados del modelo de embeddings; copiar
vectores ata la instalacion a ese modelo y el dia que cambie quedan datos que
parecen validos y no lo son. Re-ingerir es reproducible por construccion.

### 4. Los comandos existen para el OPERADOR

Hoy `ianest-extended` vive dentro de un venv y no esta en el PATH: hubo que poner
envoltorios a mano. El instalador deja los comandos invocables desde cualquier
directorio, con su configuracion ya resuelta, sin activar venv ni recordar rutas.

### 5. Servicios

Unidades de sistema para la REST y para MCP, con su fichero de entorno, que
arranquen tras la red y se reinicien si fallan. Instalarlas y habilitarlas son
parametros distintos: instalar no es habilitar.

**Esperar al PUERTO, no a systemd.** Un `Type=simple` se da por arrancado al hacer
fork, no al escuchar; el core ya se comio esa carrera y su instalador la resuelve.

### 6. Verificacion al terminar

Con `VERIFY` estricto, el instalador comprueba y FALLA si algo no esta: esquema
migrado, servicios escuchando, `capability.list` respondiendo por la REST, y las
capacidades propias vivas. Devuelve codigo de salida distinto de cero si falla.

**Que se ejecute, no que se narre.** Es la leccion que esta capa le mando al core
en su hallazgo 3 y que aqui aplica igual.

### 7. Idempotente

Ejecutarlo dos veces seguidas no rompe lo instalado ni duplica nada. La segunda
pasada debe poder usarse para actualizar.

## Fuera de esta tarea (NO implementar)

- Provisionar el backend de modelos. Es del core y ademas hay un aviso duradero
  abierto en gobernanza sobre quien provisiona que.
- Autenticacion. Sigue sin haberla y se escucha en loopback por defecto.
- Tocar `install.sh`, que es otra cosa y sigue siendo util.
- Sustituir la configuracion existente de una instalacion previa sin decirlo: si
  encuentra una, lo declara y respeta lo que ya hay salvo que se le pida
  reemplazar.
- Tocar el core o el laboratorio.

## Criterios de aceptacion (falsables)

1. **Desde cero.** En una maquina con el sistema operativo limpio y sin nada de
   esta capa, un solo comando con su fichero de parametros la deja utilizable.
2. **Sin manos.** Terminado el instalador, un operador que no haya visto el
   repositorio puede ejecutar `ianest-extended prompt run` desde su directorio
   personal y obtener respuesta.
3. **Idempotencia.** Ejecutarlo dos veces seguidas termina en el mismo estado y
   con exito las dos.
4. **Almacen remoto de primera clase.** Con un DSN de un almacen que ya existe en
   otra maquina, el instalador migra el esquema y verifica, sin exigir runtime de
   contenedores en la maquina objetivo.
5. **Corpus.** Con una ruta de corpus declarada, al terminar `knowledge status`
   muestra los dominios con vinculo confirmado.
6. **Servicios.** REST y MCP quedan escuchando y sobreviven a un reinicio de la
   maquina si se habilitaron.
7. **Espera al puerto.** La verificacion no da por arrancado un servicio que aun
   no escucha.
8. **Verificacion que falla.** Con un DSN invalido a proposito, el instalador
   termina con codigo distinto de cero y un mensaje que nombra la causa.
9. **Config fuera del repo.** La configuracion queda en `config/extended/`, legible
   por el usuario que ejecuta los comandos, y no dentro del arbol de trabajo.
10. **Sin regresion.** La suite sigue en verde.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama que ya esta activa. **No
cambies de rama, no crees rama, no commitees, no hagas push.**

Documenta el procedimiento en `docs/DESPLIEGUE.md` -que hoy no existe- y actualiza
`CHANGELOG.md`. El `docs/PLAN.md` marca la fase 8 cuando se verifique en maquina
real, no antes: quien implementa no puede declararla cerrada.

No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
