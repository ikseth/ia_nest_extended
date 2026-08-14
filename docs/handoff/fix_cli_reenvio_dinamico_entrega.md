# Entrega: reenvio dinamico en la piel CLI

Autor: agente codificador (modo ciego).
Base: `main`, su ultimo commit (`8354413`). Rama: `fix-cli-reenvio-dinamico`.
Fecha: 2026-08-14
Encargo: correccion acotada pedida por el agente verificador tras la Fase 7a.
Doctrina que lo gobierna: `docs/decision_records/0011-...md`, enmienda de
2026-08-14, punto 11 (ninguna piel puede exigir conocer una capacidad para poder
invocarla) y meta ADR 0007 (anadir capacidades abajo no obliga a editar arriba).

Verificacion: NO la hace quien implementa.

## 1. Que se implemento

Solo la piel (`src/ianest_extended/cli.py`) y el docstring de
`src/ianest_extended/capabilities.py`. El servicio, el sustrato, la memoria y el
RAG quedan intactos.

### Regla de resolucion

`main()` mira el primer token POSICIONAL de la linea de comandos, saltando las
opciones globales y sus valores (`--env-file RUTA` y `--env-file=RUTA`):

1. Si ese token es un grupo conocido -los que registra el parser: `prompt`,
   `memory`, `memory_type`, `knowledge`, `runtime`, `domain`, `model`, `config`,
   `eval`-, el flujo es EXACTAMENTE el de antes. No se toco ninguna de sus rutas
   de codigo.
2. Si no lo es, `GRUPO ACCION` se interpreta como la capacidad `grupo.accion` y
   se reenvia por `ExtendedService.forward()`, el mismo camino generico que ya
   usaban las declaradas.
3. Si falta la accion, error tipado (`ExtendedError`, campo `capability`,
   codigo de salida `1`). No se inventa ruta ni se adivina nombre. Si el core
   responde que no existe, su error llega tal cual por el camino de siempre.

La lista de grupos conocidos se DERIVA del parser (`_group_names`), no de una
segunda lista escrita a mano: no hay dos sitios que puedan desincronizarse.

### Superficie de la invocacion dinamica

Las mismas banderas que ya usan las reenviadas, sin sintaxis nueva:
`--prompt TEXTO`, `--param CLAVE=VALOR` (repetible), `--payload JSON`, las cinco
de identidad y `--json`, mas la global `--env-file`, que sigue valiendo antes o
despues de la capacidad. `GRUPO ACCION --help` describe la capacidad reenviada.

Verbo: la misma regla generica que el servicio ya documenta -sin cuerpo, `GET`;
con cuerpo, `POST`-. Como para una capacidad desconocida no hay dato del que
deducir el verbo, el cuerpo se envia SOLO si el operador declaro alguno con
`--prompt`, `--param` o `--payload`; en ese caso se anade tambien la identidad,
igual que en el reenvio declarado. Sin ninguna de esas banderas, la peticion va
sin cuerpo y el verbo es `GET`. Asi se alcanzan tanto las capacidades servidas
por `GET` como las servidas por `POST` sin que la piel las conozca.

Streaming, opacidad de la respuesta y codigos de salida son literalmente el
mismo codigo: se extrajo `_emit_forward()`, que ahora comparten el reenvio
declarado y el dinamico.

### Papel de `capabilities.py`

Su docstring afirmaba que la lista existia porque "el CLI debe construir su
ayuda" y era, de hecho, la condicion para invocar. Ahora dice lo que es: NO
habilita nada -el CLI resuelve cualquier `GRUPO ACCION` desconocido- y su unico
aporte es AYUDA ENRIQUECIDA (subcomando documentado, verbo declarado, resumen)
de las capacidades que hoy conocemos. Sigue declarado como interino: desaparece
cuando el core entregue `capability.list` (`extended CR-0002`), momento en que el
catalogo de abajo se obtiene en ejecucion y se fusiona (ADR 0011, puntos 9 y 10).

### Ayuda de primer nivel

El epilogo declara ahora que CUALQUIER capacidad del core es invocable como
`GRUPO ACCION` aunque no aparezca en la lista, y que los grupos listados solo son
los que esta capa conoce lo bastante para documentarlos.

## 2. Decision que hubo que tomar

Una sola, y se declara por si merece reconciliacion:

- **`-h`/`--help` antes de cualquier posicional sigue siendo la ayuda GENERAL.**
  Sin esta salvaguarda, `ianest-extended --help capability` habria entrado por el
  camino dinamico y habria fallado por accion ausente, cambiando un
  comportamiento que hoy funciona. Es la unica excepcion a "el primer posicional
  manda", y existe para no romper el criterio 4.

El resto sale de la instruccion recibida: el verbo por presencia de cuerpo, el
error tipado (codigo `1`) cuando falta la accion, y la reutilizacion de las
banderas existentes.

## 3. Criterios de aceptacion, uno a uno

Resultado real de `python -m pytest` en este entorno (sin PostgreSQL local):
**73 pasan, 26 se omiten**. Los 26 skips son los de PostgreSQL, con su razon
explicita. Antes de este cambio la suite eran 91 pruebas (65 + 26); ahora son 99
(73 + 26): las 8 nuevas estan en `tests/test_cli_unknown_capability.py`.

| # | criterio | prueba | estado |
|---|---|---|---|
| 1 | `capability nueva --param x=1` llega a `/capability/nueva` y devuelve 0, sin estar en `capabilities.py` | `tests/test_cli_unknown_capability.py::test_unknown_capability_is_invocable_without_editing_the_layer` (comprueba primero que el nombre NO esta declarado) | pasa |
| 2 | Capacidad desconocida con SSE retransmitida evento a evento por el CLI | `::test_unknown_capability_streams_event_by_event` | pasa |
| 3 | Error del core en capacidad desconocida con formato y codigo de siempre, conservando `type` y `origin` | `::test_unknown_capability_error_keeps_format_type_and_origin` (texto `AdapterError (modelo): ...` con codigo 1, y su JSON con `type` y `origin`) | pasa |
| 4 | Todo lo que ya funcionaba sigue igual; las 91 pruebas en verde | suite completa (91 previas en verde) y `::test_known_group_is_never_resolved_dynamically` (un grupo conocido con accion invalida sigue dando el error de argparse con codigo 2, sin tocar el core) | pasa |

Pruebas adicionales, no exigidas, que fijan lo que decidi:

- `::test_unknown_capability_without_body_is_a_get`: sin banderas de cuerpo, la
  peticion es `GET` y sin cuerpo (regla de verbo).
- `::test_unknown_group_without_action_is_a_typed_error`: falta la accion ->
  `ExtendedError (capability)` con codigo 1, y no se contacta con el core.
- `::test_top_level_help_declares_the_dynamic_invocation`: la ayuda general
  declara la invocacion dinamica.
- `::test_global_env_file_works_before_and_after_the_capability`: `--env-file`
  funciona tambien despues de la capacidad.

El stub del core gana tres rutas para poder falsar lo anterior: `GET
/estado/nuevo`, `POST /flujo/nuevo` (SSE) y `POST /capability/rota` (error con
`type` y `origin`). `POST /capability/nueva` ya existia.

Lo que NO se verifico: nada contra un core real; todo va contra el stub HTTP
local. Los dos casos de `tests/test_phase7a_postgres.py` siguen omitidos por
falta de PostgreSQL local en esta maquina.

## 4. Que quedo fuera

- Descubrimiento por `capability.list` (`extended CR-0002`): la ayuda sigue
  saliendo de la lista local, que ya no habilita nada.
- El servicio, el sustrato, la memoria y el RAG: sin tocar.
- Fusion del catalogo ajeno con el propio (ADR 0011, puntos 9 y 10): depende del
  core.

## 5. Impacto de version

Ninguno. No hay tag cortado ni contrato publicado. El cambio es aditivo sobre la
superficie CLI: no retira ni renombra ningun subcomando, ninguna bandera ni
ningun codigo de salida. Declarado en `CHANGELOG.md` bajo `[No publicado]`.
Sin merge, sin push y sin tags.
