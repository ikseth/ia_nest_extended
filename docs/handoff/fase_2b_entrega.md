# Entrega de implementacion: fase 2b

Fecha: 2026-07-24
Rama indicada por el usuario: `fase-2-memoria-registro`
Impacto de version: ninguno; no cambia el contrato publico.

## Decisiones tomadas

- `install.sh` resuelve su raiz con `BASH_SOURCE` y opera desde ella, por lo que
  puede invocarse desde otro directorio.
- Docker solo se selecciona si responden tanto el daemon como `docker compose`.
  Si no, se prueba Podman funcional y se prefiere `podman compose`, con
  `podman-compose` como fallback.
- En openSUSE, la ausencia de runtime instala `podman` y `podman-compose` con
  `zypper`. La ausencia de Python 3.13 instala `python313` y `python313-pip`.
  Cada instalacion requiere confirmacion, salvo con `--assume-yes`, y usa
  `sudo` solo cuando el proceso no es root.
- Otras distribuciones se detectan mediante `/etc/os-release`, pero la
  instalacion automatica se rechaza con un error explicito.
- La disponibilidad de PostgreSQL se comprueba desde el contenedor con
  `pg_isready`, cada dos segundos y con timeout de 90 segundos.
- La ruta con DB exporta e imprime el DSN loopback del compose. Ademas exige
  que pytest termine en verde y sin skips. La ruta `--skip-db` elimina el DSN
  del entorno, acepta los skips y remite a las razones impresas por pytest.
- `.venv` se reutiliza solo si contiene un Python 3.13. Una version distinta se
  rechaza con instrucciones para reconstruirla, sin borrar datos por
  inferencia.
- El README documenta el arranque, los flags, la parada sin perdida de datos y
  la limpieza explicita del volumen para Docker y Podman.

## Dudas abiertas

- La disponibilidad exacta de `podman-compose`, `python313` y
  `python313-pip` debe confirmarse en la version de openSUSE del laboratorio.
- La seleccion de runtime, la instalacion con `zypper`, el arranque del compose
  y la espera de salud necesitan la prueba prevista en el laboratorio.

## Que quedo probado

- `bash -n install.sh`: limpio.
- `./install.sh --help`: limpio.
- `./install.sh --skip-tests --skip-db`: entorno preparado y pytest omitido
  con resumen explicito.
- Control de ASCII sobre `install.sh`, `README.md`, `CHANGELOG.md` y esta nota:
  limpio.
- `./install.sh --skip-db`: dos ejecuciones consecutivas terminaron en verde,
  reutilizaron `.venv` e instalaron de nuevo el paquete editable sin romper el
  entorno. Resultado de ambas:

      10 passed, 6 skipped

  Los seis skips pertenecen a `tests/test_postgres_store.py` y declaran:

      IANEST_EXTENDED_TEST_DSN no definido; tests postgres omitidos

- Para respetar la prohibicion de conexiones remotas, la prueba se ejecuto sin
  indice de paquetes. El `.venv` preexistente no contiene `setuptools`; se uso
  el `setuptools 80.9.0` local del sistema y se desactivo el aislamiento de
  build mediante el entorno de pip:

      PIP_NO_INDEX=1 PIP_NO_BUILD_ISOLATION=false \
      PYTHONPATH=/usr/lib/python3.13/site-packages \
      ./install.sh --skip-db

  Un primer intento offline con el aislamiento de build activo fallo antes de
  ejecutar tests porque pip no podia descargar `setuptools>=75`. No fue un
  fallo de la ruta normal, que puede resolver sus dependencias, ni se oculto.

## Que no quedo probado

- No se ejecuto la ruta con DB: en esta maquina no hay Docker ni Podman y no se
  instalaron.
- No se ejecutaron los seis tests PostgreSQL ni se valido el requisito de cero
  skips con DB.
- No se probo la instalacion de paquetes con `zypper`.
- `shellcheck` no esta instalado en esta maquina; por tanto, no se ejecuto.
- No se conecto a hosts remotos ni al laboratorio.

## Entrada anadida a CHANGELOG bajo No publicado

Se anadio bajo `### Anadido`:

    - Instalador de desarrollo `install.sh`, idempotente y orientado primero a
      openSUSE: seleccion Docker/Podman, PostgreSQL+pgvector con espera de salud,
      `.venv` Python 3.13, instalacion editable y pytest; incluye modos
      `--assume-yes`, `--skip-db` y `--skip-tests`, documentacion de uso y handoff
      de Fase 2b. Sin cambios en el contrato publico; impacto de version: ninguno.
