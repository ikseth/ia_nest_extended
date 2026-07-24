# Handoff de implementacion: fase 2b (instalador de recursos, openSUSE primero)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus/Fable), rol disenador.
Verificacion: Opus (la ruta completa con DB se probara en el laboratorio).
Base: rama `fase-2-memoria-registro` (sustrato de fase 2 ya implementado).

Espejo del patron del core (fase 9, core ADR 0024): instalacion reproducible,
bash idempotente, cabecera humana/IA (proposito, entradas, salidas, efectos,
requisitos, seguridad) segun `CONVENCIONES.md` del core.

## Objetivo

`install.sh` que deje el sustrato de la fase 2 ejecutable y verificado en una
maquina openSUSE limpia: runtime de contenedores, postgres+pgvector levantado,
venv con el paquete instalado y `pytest` completo en verde (sin skips de DB).

## Dentro de fase 2b

1. `install.sh` en la raiz (bash, idempotente, con cabecera):
   - Detecta runtime de contenedores: usa `docker` si esta disponible y
     funcional; si no, `podman` (con `podman compose` o `podman-compose`). Si no
     hay ninguno, lo instala con `zypper` (podman; requiere root/sudo: avisa
     claramente y pide confirmacion salvo `--assume-yes`).
   - Levanta la DB de `docker-compose.dev.yml` y espera el healthcheck con
     timeout y mensaje util.
   - Crea `.venv` con Python 3.13 e instala `pip install -e .[test]`.
   - Exporta/imprime `IANEST_EXTENDED_TEST_DSN` (el DSN local del compose) y
     ejecuta `pytest`; resumen final claro (verde/rojo, skips y por que).
   - Flags: `--help`, `--assume-yes`, `--skip-db` (solo venv+paquete+tests con
     skips), `--skip-tests`. Idempotente: segunda ejecucion no rompe nada.
   - openSUSE primero (`zypper`); estructura del script preparada para anadir
     otras distros despues (deteccion por `/etc/os-release`), sin implementarlas.
2. Seccion "Instalacion de desarrollo" en `README.md`: pasos desde cero,
   flags, y como parar/limpiar la DB (`docker compose down`).

## Fuera de fase 2b (NO implementar)

- Despliegue de produccion, systemd, otras distros, publicacion.
- Conexion a hosts remotos o al laboratorio (la prueba de lab la hace el
  disenador).
- Cambios en el sustrato de fase 2: si un test contra DB real fallara, NO
  refactorices el sustrato; documenta el fallo en la nota de entrega. Solo
  corrige bugs evidentes y minimos, documentando cada uno.

## Blanco de aceptacion

- En openSUSE limpio con docker o podman funcional: `./install.sh` termina con
  `pytest` sin skips de DB y todo en verde; ejecutado dos veces seguidas,
  mismo resultado (idempotencia).
- `./install.sh --skip-db` deja venv+paquete y pytest en verde-con-skips.
- `bash -n install.sh` limpio; shellcheck limpio si esta disponible.
- Cabecera presente; mensajes de error utiles; ASCII puro.

## Restricciones y limitaciones de tu entorno

- En esta maquina NO hay docker ni podman accesibles y tu sandbox no puede
  instalarlos: prueba lo que puedas (`bash -n`, shellcheck si existe,
  `--skip-db` end-to-end) y declara honestamente en la nota que la ruta con DB
  queda sin ejecutar aqui; se probara en el laboratorio.
- No ejecutes comandos git (sandbox con .git en solo lectura); los commits los
  hace el disenador.
- Prosa/comentarios en espanol ASCII; identificadores y flags en ingles;
  repo publico: sin datos internos.

## Entrega y handoff de vuelta

Ficheros en la rama activa (`fase-2-memoria-registro`) y nota en
`docs/handoff/fase_2b_entrega.md`: decisiones, dudas, que quedo probado y que
no, y la entrada anadida a `CHANGELOG.md` bajo "No publicado".
