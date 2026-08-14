# Entrega de implementacion: fase 7a (servicio con contrato uniforme y CLI)

Autor: agente codificador (modo ciego, sin ver la conversacion de diseno).
Base: `main`, su ultimo commit (`2812ea9`). Rama: `fase-7a-contrato-uniforme`.
Fecha: 2026-08-14
Brief: `docs/handoff/fase_7a_brief.md`.

Verificacion: NO la hace quien implementa. Este documento declara lo hecho, lo
decidido, lo cubierto, lo que quedo fuera y las inconsistencias detectadas.

## 1. Que se implemento

### Composition-root (`src/ianest_extended/composition.py`)

`ExtendedComposition` construye cada dependencia (cliente del core, embedder,
store de memoria, store RAG, telemetria) SOLO cuando la operacion invocada la
necesita, y la cachea. Admite inyeccion por constructor como costura de prueba.
`memory.maintain` no construye el cliente del core ni contacta con Ollama.

La migracion es explicita: el root VERIFICA el esquema (`verify_schema()`, de
solo lectura, anadido a los dos adaptadores y a los puertos) y falla con
`SchemaMigrationRequiredError` indicando `ianest-extended runtime migrate`.
`ExtendedComposition.migrate()` es el unico camino que muta esquema.

### Fachada (`src/ianest_extended/service.py`)

`ExtendedService` es la superficie unica de todas las pieles:

- **Reenvio generico**: `forward(capability, payload, method)`. La ruta se
  deriva del nombre por convencion (`prompt.run` -> `/prompt/run`), asi que no
  hay codigo por capacidad ni `if` por nombre. Soporta respuesta JSON y
  `text/event-stream`, decidido por el `Content-Type` de la respuesta.
- **Sobreescritura de `prompt.run`**: usa el `MemoryEnricher` existente (recall,
  composicion dentro del presupuesto, llamada al core y write-back) y devuelve
  el payload del core INTACTO; el contexto y los identificadores viajan aparte,
  en `PromptRunResult`, para no ensuciar la forma de la respuesta.
- **Capacidades propias**: `memory_type.list`, `memory_type.validate`,
  `memory.recall`, `memory.write`, `memory.consolidate`, `memory.maintain`,
  `knowledge.ingest|status|suggest|confirm|reject`, envolviendo lo que ya
  existia.

`forward()` rechaza con error tipado las capacidades sobreescritas y las
propias, para que nadie degrade `prompt.run` reenviandolo por descuido.

### Tipado / opaco

Se conserva la validacion campo a campo SOLO en `prompt.run` (write-back),
`domain.route` y `domain.list` (gate de dominio). Todo lo demas se reenvia sin
parsear, sin validar y sin reescribir; `CoreResult` guarda ademas el payload
crudo del core para poder devolverlo tal cual.

### Modelo de timeout

`request_timeout_seconds` se retira y se parte en `connect_timeout_seconds` e
`inactivity_timeout_seconds`. El transporte pasa de `urllib` a `http.client`
para poder fijar el timeout de inactividad sobre el socket y leer el flujo
evento a evento.

### Superficie de parametros

`plan_enrichment()` resuelve las banderas: configuracion da DEFAULTS y la
peticion hace override; los tres estados importan (`None` = default). `enrich`
desactivado es un macro que implica `use_memory`, `use_rag` y `write_back`
desactivados, y sigue emitiendo telemetria propia. Combinacion contradictoria
(`enrich` desactivado con una fuente activada, o `domain` junto a
`auto_domain`) es `EnrichmentParameterError` con el campo culpable.

`rag_enabled` deja de decidir cableado: es solo el default de `use_rag`. El root
cablea el store RAG siempre que puede y, si se pide RAG sin sustrato, emite
`RagUnavailableError`. Los numeros (top-k, presupuestos, umbrales,
`dedup_threshold`) siguen sin bandera.

### Errores tipados y codigos de salida

`ExtendedError` es la base con `type` (la clase), `message`, `field`, `origin`
(`ia_nest_extended`), `request_id` y `to_dict()`. Reparenta `MemoryError`,
`RagError`, `ExtendedConfigError` y `ExternalServiceError`. `DownstreamError` es
el transporte en proceso del error ajeno: `to_dict()` devuelve el payload del
core TAL CUAL, sin re-envolver, re-tipar ni traducir. Codigos de salida iguales
a los del core: `0`, `1` con `Tipo (campo): mensaje` en stderr (o su JSON con
`--json`) y `2` con la ayuda del grupo.

La telemetria pasa de `core_request_id` a `downstream_request_id` y se anade el
evento `prompt.run`, que se emite tambien en passthrough.

### Piel CLI (`src/ianest_extended/cli.py`)

Entry-point instalable `ianest-extended`, gramatica GRUPO ACCION, `--json` en
todas las acciones, `--env-file RUTA` global. Identidad no obligatoria con
defaults de configuracion (`service` = `local_cli`) y `session_id` generado UNA
VEZ y recordado en fichero local (`src/ianest_extended/identity.py`). `--domain`
unificado, sin `--domain-tag`. Las acciones reenviadas se construyen a partir de
un unico dato (`src/ianest_extended/capabilities.py`), interino hasta
`capability.list` (`extended CR-0002`). `prompt run` acepta ademas
`--show-context` y `--dry-run`. `cli.py` no importa `adapters` ni `clients`.

### Migracion y retirada de harnesses

Se anade `runtime migrate` y `install.sh` lo invoca. Se elimina `chat.py` y se
retiran los `main()` de `ingest.py`, `knowledge.py` y `maintain.py`: sus modulos
siguen existiendo como logica de dominio envuelta por el servicio, pero
`python -m ianest_extended.chat|ingest|knowledge|maintain` deja de ser un
comando. `README.md` documenta la superficie nueva.

## 2. Decisiones que hubo que tomar, y por que

Cada una rellena un hueco del brief que impedia escribir codigo. Se declaran
para que se reconcilien o se corrijan; ninguna se da por doctrina.

1. **Default del timeout de inactividad.** El brief fija "los valores de hoy
   como defaults del primero" (conexion) y no dice nada del segundo. Se toma
   tambien `30.0`, el valor de hoy, porque es el unico que no cambia el
   comportamiento observable. PENDIENTE DE DECISION del disenador.
2. **Ruta por defecto del fichero de sesion.** El brief dice que es
   configurable, no cual es su default. Se usa
   `$XDG_STATE_HOME/ianest_extended/session_id` (con `~/.local/state` como
   fallback). Motivo: un default relativo daria una sesion distinta por
   directorio de trabajo, y el CLI debe servir fuera de la raiz del repo -que es
   justo lo que `--env-file` persigue-. No queda dentro del repo, asi que no hay
   nada que anadir a `.gitignore`.
3. **Valor por defecto de `user_id`.** El brief fija `service` = `local_cli` y
   no fija el resto. Se usa `local_operator`, configurable con
   `IANEST_EXTENDED_DEFAULT_USER_ID`. Riesgo declarado: cambiar ese valor
   fragmenta la clave de memoria de la instalacion.
4. **Verbo HTTP del reenvio generico.** Para una capacidad que esta capa no
   conoce no hay dato del que deducir el metodo. Regla generica adoptada: sin
   cuerpo, `GET`; con cuerpo, `POST`. La lista interina declara el verbo de las
   siete capacidades conocidas, que es lo que el CLI necesita para su ayuda.
5. **Defaults de configuracion que no existian.** `enrich`, `use_memory` y
   `write_back` no tenian clave. Se anaden `ENRICH_ENABLED`, `MEMORY_ENABLED` y
   `WRITE_BACK_ENABLED` (todas `true`), porque la regla "la configuracion da
   DEFAULTS" exige una para cada bandera.
6. **Alcance de `--dry-run`.** Se interpreta como "no llama a `prompt.run` y no
   persiste". Si el enriquecimiento necesita resolver dominio, sigue
   consultando `domain.list` (dominio explicito) o `domain.route`
   (`--auto-domain`), porque sin eso no se puede componer el prompt que el
   comando debe imprimir. PENDIENTE DE CONFIRMACION.
7. **Nombre del evento de telemetria del passthrough.** El brief exige
   telemetria propia sin nombrar el evento. Se anade `prompt.run`, emitido
   siempre (enriquecido y passthrough), y se conservan `enrich.recall` y
   `enrich.write_back` del camino enriquecido. El esquema de telemetria es
   contrato (`docs/VERSIONADO.md`, punto 5), asi que este nombre necesita
   reconciliacion.
8. **`auto_domain` deja de exigir store RAG.** Antes la resolucion automatica
   solo ocurria con RAG cableado. Como el brief la declara parametro de
   `prompt.run` (no de RAG), ahora depende solo de la bandera. Cambio de
   comportamiento observable.
9. **Store de memoria ausente cuando la peticion no toca memoria.** Si
   `use_memory` y `write_back` estan desactivados pero el enriquecimiento sigue
   activo (solo RAG), no se construye el store: se inyecta un sustituto que
   falla con error tipado si alguien lo toca. Evita exigir la DB de memoria a
   una peticion que no la usa.
10. **Transporte HTTP propio.** Se cambia `urllib` por `http.client` porque no
    hay forma limpia de fijar el timeout de inactividad del socket ni de leer un
    `text/event-stream` incremental con `urlopen`. Sigue siendo stdlib.

## 3. Criterios de aceptacion, uno a uno

Resultado real de `python -m pytest` en este entorno (sin PostgreSQL local):
**63 pasan, 26 se omiten**. Los 26 skips son los de PostgreSQL, con su razon
explicita (`IANEST_EXTENDED_TEST_DSN no definido`).

| # | criterio | prueba | estado |
|---|---|---|---|
| 1 | Conformidad (ruta desconocida alcanzable sin tocar codigo) | `tests/test_uniform_contract.py::test_unknown_capability_is_reachable_without_touching_layer_code` | pasa |
| 2 | Reenvio opaco (campos desconocidos intactos) | `tests/test_uniform_contract.py::test_forwarded_response_reaches_caller_intact` y `::test_forwarded_get_capability_is_opaque` | pasa |
| 3 | Streaming retransmitido evento a evento | `tests/test_uniform_contract.py::test_stream_is_retransmitted_event_by_event` | pasa |
| 4 | Sobreescritura transparente (misma forma, `response` y `trace` intactos) | `tests/test_prompt_run_service.py::test_overridden_prompt_run_keeps_core_shape` | pasa |
| 5 | Passthrough (sin recall, sin inyeccion, sin escritura, con telemetria) | `tests/test_prompt_run_service.py::test_passthrough_does_not_recall_inject_or_write` | pasa |
| 6 | Contradiccion como error tipado | `tests/test_prompt_run_service.py::test_contradictory_combination_is_a_typed_error` (4 casos) | pasa |
| 7 | RAG sin silencio | `tests/test_prompt_run_service.py::test_requested_rag_without_substrate_fails_typed` y `::test_rag_policy_flag_does_not_decide_wiring` | pasa |
| 8 | Perezoso (`memory maintain` con core y Ollama caidos) | `tests/test_composition_and_cli.py::test_maintain_runs_with_core_and_ollama_unreachable` (pasa) y `tests/test_phase7a_postgres.py::test_maintain_runs_against_postgres_with_core_and_ollama_down` | pasa con fake; **la version contra PostgreSQL se OMITE aqui** |
| 9 | Aislamiento de la piel (`cli.py` sin `adapters` ni `clients`) | `tests/test_composition_and_cli.py::test_cli_does_not_import_adapters_or_clients` | pasa |
| 10 | Migracion (solo lectura con esquema sin migrar falla y no muta) | `tests/test_composition_and_cli.py::test_read_only_capability_fails_on_unmigrated_schema` (pasa) y `tests/test_phase7a_postgres.py::test_read_only_capability_fails_on_unmigrated_schema` | pasa con fake; **la version contra PostgreSQL se OMITE aqui** |
| 11 | Codigos de salida `0`, `1` y `2` | `tests/test_composition_and_cli.py::test_exit_code_zero_on_forwarded_capability`, `::test_exit_code_one_on_typed_error`, `::test_exit_code_one_with_json_error_payload`, `::test_exit_code_two_prints_group_help` | pasa |
| 12 | Error ajeno intacto / fallo propio con `origin` de la capa | `tests/test_uniform_contract.py::test_core_error_is_propagated_without_rewrapping` y `::test_own_failure_carries_this_layer_origin` | pasa, con la salvedad del punto 4.1 |
| 13 | Traza encadenada (`request_id` + `downstream_request_id`) | `tests/test_prompt_run_service.py::test_telemetry_chains_the_downstream_request_id` | pasa |
| 14 | Pruebas existentes en verde con los skips esperados | suite completa | pasa: 63 pasan, 26 skips de PostgreSQL |

Lo que NO se pudo verificar en este entorno:

- Los dos casos de `tests/test_phase7a_postgres.py` (criterios 8 y 10 contra el
  sustrato real) quedan OMITIDOS porque no hay PostgreSQL local ni runtime de
  contenedores disponible en la maquina donde se implemento. Estan escritos y se
  ejecutan con `IANEST_EXTENDED_TEST_DSN` definido.
- No hay verificacion en laboratorio contra un core real (v0.3): todo lo
  anterior se prueba contra el stub HTTP local.

## 4. Inconsistencias detectadas (SIN corregir por inferencia)

1. **El core no emite `origin` ni `request_id` en sus errores.** El criterio 12
   pide que el error ajeno llegue "con su `type` y su `origin` originales", y
   `ia_nest_meta/docs/FORMA_DE_ERRORES_Y_TRAZA.md` incluye `origin` en el minimo
   comun. Pero `ia_nest_core/src/ianest_core/errors.py` (`CoreError.to_dict`)
   devuelve solo `type`, `message` y `field`. Consecuencia: contra el core real,
   `DownstreamError.origin` sera `None`. NO se rellena por inferencia (poner
   `ia_nest_core` seria inventar un dato del vecino). El criterio se prueba con
   un stub que si declara `origin`. Parece material para un CR al core.
2. **`docs/EXTENDED_CONTRACT.md` habla de fuentes descubribles.** Dice
   "desactivar una fuente concreta por nombre" y "Un consumidor descubre las
   disponibles, no las presupone", mientras que la fase 7a entrega banderas
   fijas (`use_memory`, `use_rag`) y ningun mecanismo de descubrimiento, que el
   brief difiere a `extended CR-0002`. No se implementa catalogo de fuentes ni
   se toca el contrato: se senala la divergencia.
3. **El `CHANGELOG` dice "Doce criterios de aceptacion falsables"** al describir
   el brief de la fase 7a, y el brief entregado enumera catorce. No se corrige.
4. **`rag_auto_domain` conserva su prefijo `rag_`** aunque `auto_domain` ha
   pasado a ser un parametro de `prompt.run` y no de RAG. Renombrar la clave
   tocaria el esquema de configuracion, que es contrato, sin que el brief lo
   pida. Se senala.
5. **`errors.MemoryError` sigue tapando el `MemoryError` incorporado de
   Python.** Es previo a esta fase y el brief solo pide reparentar las familias;
   no se renombra.
6. **La retirada de los harnesses es parcial en sentido literal.** Los modulos
   `ingest.py`, `knowledge.py` y `maintain.py` siguen existiendo (contienen la
   logica que el servicio envuelve) y solo pierden su `main()`, de modo que
   `python -m ianest_extended.ingest` no ejecuta nada en lugar de fallar con un
   mensaje. `chat.py` si desaparece por completo. Si se quiere un aviso de
   retirada explicito, es decision de diseno, no de implementacion.

## 5. Que quedo fuera (conforme al brief)

- `reasoning.run`, `task.run` y `prompt.stream` SOBREESCRITOS (fase 7b). Se
  reenvian; la ayuda del CLI declara que `prompt stream` no lleva memoria.
- Piel de CLI para `memory.write`, `memory.consolidate` y
  `memory_type.validate`: existen como capacidades del servicio, sin comando.
  `memory_type.validate` recibe un `MemoryType` ya construido: el formato de
  entrada por linea de comandos sigue sin reconciliar y no se inventa aqui.
- REST y MCP (fase 7c). El servicio queda listo para ellas: devuelve
  diccionarios serializables y no tiene logica en la piel.
- Descubrimiento de capacidades (`extended CR-0002`): la lista de reenviadas es
  un dato en `capabilities.py`, sustituible por una consulta en un cambio local.
- Cortar tag o pasar `docs/EXTENDED_CONTRACT.md` a `activo` (fase 7d).
- `knowledge.retrieve` y `knowledge.corpus.list`.
- No se toca el core, ni el esquema de memoria, ni la politica de write-back, ni
  el ranking, ni la consolidacion, ni el corpus del laboratorio, ni el
  despliegue.

## 6. Impacto de version

Declarado en `CHANGELOG.md` bajo `[No publicado]`: **MINOR cuando se corte tag**
(serie pre-1.0). Rompen contrato el esquema de configuracion -se retira
`REQUEST_TIMEOUT_SECONDS`- y la superficie CLI -se retiran los cuatro
harnesses-, ambos declarados como contrato en `docs/VERSIONADO.md`. Tambien
cambia el esquema de telemetria (`core_request_id` -> `downstream_request_id`).
No se corta tag ni se hace merge a `main`.
