# Handoff de implementacion: fase 7a (servicio con contrato uniforme y CLI)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-14
Base: `main`, commit `0c2f6ff`.

Estado de contrato: reconciliado. Gobiernan `extended ADR 0011`, `meta ADR 0007`
(contrato uniforme) y `docs/VERSIONADO.md`. No hay diseno abierto en esta tarea.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `ia_nest_meta/docs/ARQUITECTURA_DE_CAPAS.md` (meta ADR 0007): el invariante y
   las cuatro reglas. Es lo que esta tarea implementa.
3. `ia_nest_meta/docs/FORMA_DE_ERRORES_Y_TRAZA.md` (meta ADR 0009): forma de los
   errores que cruzan capas y encadenado de la traza.
4. `docs/decision_records/0011-interfaz-de-consumo-contrato-uniforme.md`.
5. `docs/EXTENDED_CONTRACT.md` (que se expone) y `docs/VERSIONADO.md` (que cuenta
   como contrato).
6. `docs/PLAN.md`, seccion Fase 7a.
7. `core docs/CORE_CONTRACT.md` para la forma de las capacidades del core. NO se
   copia aqui: se referencia (convencion transversal 6).

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Objetivo

Que esta capa deje de exponer un catalogo propio y menor, y pase a exponer el
contrato uniforme: reenvia lo que no enriquece, sobreescribe `prompt.run`, y
anade lo suyo. Todo por UN servicio, con un composition-root compartido y el CLI
como piel fina instalable.

## Dentro de fase 7a

### 1. Composition-root (`composition.py`)

Una factoria que arma el servicio a partir de `ExtendedConfig`. Requisito duro:
**construccion perezosa**. Cada dependencia (store de memoria, store RAG,
embedder, cliente del core, telemetria) se construye solo cuando la operacion
invocada la necesita, y se cachea.

Motivo: hoy `maintain` funciona con Ollama caido porque instancia el store con
`embedder=None`. Si el root construye con avidez, el mantenimiento pasa a exigir
Ollama y el laboratorio se rompe.

### 2. Fachada `ExtendedService`

Superficie unica que usan todas las pieles. Contiene:

- **Reenvio generico.** Un unico camino que reenvia al core cualquier capacidad
  que esta capa no sobreescriba. Sin codigo por capacidad, sin `if` por nombre.
  Debe soportar respuestas JSON y respuestas `text/event-stream` (el core sirve
  cuatro rutas SSE, y `POST /task/run` es SSE SIEMPRE).
- **Sobreescritura de `prompt.run`**, que es el `MemoryEnricher` actual: recall,
  composicion dentro del presupuesto, llamada al core y write-back. Conserva la
  forma de peticion y respuesta del core; lo unico que cambia es que el prompt
  ejecutado lleva contexto.
- **Capacidades propias**, envolviendo lo que ya existe: `memory_type.list`,
  `memory_type.validate`, `memory.recall`, `memory.write`, `memory.consolidate`,
  `memory.maintain`, `knowledge.ingest`, `knowledge.status`, `knowledge.suggest`,
  `knowledge.confirm`, `knowledge.reject`.

### 3. Regla tipado / opaco

**Tipado solo donde se sobreescribe; opaco donde se reenvia.**

El cliente actual valida campo a campo la respuesta del core (`prompt_run`
comprueba `response`, `trace`, `request_id`, `finish_reason`, `params`;
`domain_route` valida cinco campos). Eso re-declara el contrato del core en
codigo. Se conserva SOLO para lo que esta capa necesita interpretar
(`prompt.run` para el write-back, `domain.route` y `domain.list` para el gate de
dominio). Todo lo demas se reenvia sin parsear, sin validar y sin reescribir.

### 4. Modelo de timeout

`request_timeout_seconds` unico deja de servir para respuestas en streaming. Se
parte en timeout de CONEXION y timeout de INACTIVIDAD entre eventos. Ambos
configurables, con los valores de hoy como defaults del primero.

### 5. Superficie de parametros

Regla: **la configuracion da DEFAULTS; las banderas son override POR PETICION; y
ninguna bandera de politica decide cableado.**

Parametros de `prompt.run` sobreescrito: `enrich`, `use_memory`, `use_rag`,
`write_back`, `domain`, `auto_domain`, `model`.

- `enrich=False` es un MACRO: implica `use_memory=False`, `use_rag=False`,
  `write_back=False`. Passthrough real, que sigue emitiendo telemetria propia.
- Combinacion contradictoria (`enrich=False` con `use_rag=True`, o `domain` junto
  a `auto_domain`) es **error tipado**, no precedencia silenciosa.
- Los tres estados importan: sin especificar = default de config. En el CLI, eso
  es `BooleanOptionalAction` con `default=None`, no `store_true`.
- Numeros (top-k, presupuestos, umbrales, `dedup_threshold`) NO llevan bandera:
  se quedan en configuracion.

**Correccion obligatoria del cableado**: hoy `rag_enabled` decide a la vez la
politica y el cableado (`rag_store = None`), y produce un no-op silencioso.
Pasa a ser solo el default de `use_rag`. El root cablea el store RAG siempre que
sea posible; si se pide `use_rag` y el sustrato no esta disponible, error tipado,
nunca silencio.

### 6. Errores tipados y codigos de salida

La FORMA la fija el ente en `ia_nest_meta/docs/FORMA_DE_ERRORES_Y_TRAZA.md`
(meta ADR 0009), que es lectura obligatoria para este punto. El catalogo de tipos
es de esta capa; la forma no se inventa aqui.

Base `ExtendedError` con `type`, `message`, `field`, `origin` y `request_id`, mas
`to_dict()`, reparentando las familias actuales (`MemoryError`, `RagError`,
`ExtendedConfigError`, `ExternalServiceError`). Es libre: no hay contrato cortado.

**Un error del core NO se re-envuelve**: se propaga tal cual, con su `origin`
intacto. Esta capa solo emite error propio cuando el fallo es suyo. Nada de
tablas de traduccion de errores ajenos.

**Encadenado de traza**: la telemetria pasa a usar `downstream_request_id` donde
hoy usa un nombre especifico del vecino (`core_request_id`). Es el nombre
generico del ente, para que la cadena se lea igual en toda la pila; el cambio es
gratis porque no hay tag cortado.

Codigos de salida IGUALES a los del core: `0` ok, `1` error tipado en stderr con
formato `Tipo (campo): mensaje`, `2` uso incorrecto (imprime la ayuda del grupo).
No inventes un tercer codigo: la clase va en `type` y en `--json`.

### 7. Piel CLI

Entry-point instalable en `pyproject.toml`:

    [project.scripts]
    ianest-extended = "ianest_extended.cli:main"

Gramatica GRUPO ACCION, calcada del CLI del core. Todas las acciones aceptan
`--json`. Bandera global `--env-file RUTA`, espejo del `--config` del core, para
que el comando sirva fuera de la raiz del repo.

Identidad: `--user-id`, `--session-id`, `--service`, `--namespace`, con los
nombres del core. **Dejan de ser obligatorios** (ADR 0011, punto 7): defaults de
configuracion, con `service` por defecto `local_cli`.

`session_id` sin indicar se GENERA UNA VEZ Y SE RECUERDA: se persiste localmente
y las invocaciones siguientes lo reutilizan. NO se genera uno nuevo por
invocacion; con eso, `dialog` no encadenaria dos comandos seguidos y la memoria
conversacional del CLI no funcionaria. El fichero de estado es contexto local: no
se versiona (convencion transversal 5) y su ruta es configurable.

`--domain` unifica deliberadamente el gate de conocimiento, el dominio de ruteo
que viaja al core y el `domain_tag` de identidad, como ya hace el codigo. No se
anade `--domain-tag`: la separacion del core no aplica aqui (ADR 0011, punto 8).

Comandos:

- `prompt run` (sobreescrito) y `prompt stream` (reenviado).
- Reenviados: `domain list`, `domain route`, `model list`, `runtime health`,
  `config validate`, `eval run`.
- Propios: `memory recall|write|consolidate|maintain`, `memory_type list|validate`,
  `knowledge ingest|status|suggest|confirm|reject`.

**Interino declarado**: el CLI no puede enumerar lo que no puede consultar, y el
core aun no ofrece catalogo (`extended CR-0002`, propuesto). Por tanto la lista
de capacidades reenviadas se declara **en un unico sitio del codigo**, como dato,
no repartida por el parser: cuando llegue `capability.list`, sustituir ese dato
por la consulta debe ser un cambio local.

`prompt run` acepta ademas `--show-context` y `--dry-run` (compone e imprime el
prompt enriquecido, no llama al core y no persiste).

### 8. Migracion explicita

El composition-root VERIFICA el esquema y falla con error tipado que indique el
comando a ejecutar. Deja de migrarse en cada arranque de cada comando: hoy un
`knowledge status` de solo lectura muta esquema. Se anade `runtime migrate` y se
actualiza `install.sh` para invocarlo.

### 9. Retirada de los harnesses

Se eliminan `python -m ianest_extended.chat|ingest|knowledge|maintain` y se
actualiza `README.md`. Una sola superficie; no se mantienen alias.

## Fuera de fase 7a (NO implementar)

- `reasoning.run` y `task.run` SOBREESCRITOS (fase 7b; `task.run` necesita
  `task.plan`, core v0.4). Reenviados si, sobreescritos no.
- REST y MCP (fase 7c). El servicio debe quedar listo para ellas, sin escribirlas.
- Descubrimiento de capacidades (espera a `extended CR-0002`).
- Cortar tag o pasar `docs/EXTENDED_CONTRACT.md` a `activo` (fase 7d).
- `knowledge.retrieve` y `knowledge.corpus.list`: nombres reservados en el
  contrato, sin implementacion hasta que `ia_nest_web` los ejerza.
- Tocar el core, el esquema de memoria, la politica de write-back, el ranking o
  la consolidacion. Esta fase mueve la superficie, no el sustrato.
- Ampliar el corpus del laboratorio o tocar despliegue.

## Criterios de aceptacion (falsables)

1. **Conformidad (meta ADR 0007).** Contra un core stub que declare una ruta que
   esta capa no conoce, esa ruta es alcanzable a traves del servicio SIN tocar
   codigo de la capa. Prueba automatizada.
2. **Reenvio opaco.** Una respuesta del stub con campos desconocidos llega al
   llamante intacta, sin validar ni reescribir.
3. **Streaming reenviado.** Una ruta SSE del stub se retransmite evento a evento;
   no se acumula ni se convierte a JSON.
4. **Sobreescritura transparente.** `prompt.run` enriquecido devuelve la misma
   FORMA que el del core, con `response` y `trace` intactos.
5. **Passthrough.** Con `enrich` desactivado no hay recall, ni inyeccion, ni
   escritura en memoria, y SI hay telemetria propia.
6. **Contradiccion.** `enrich` desactivado junto a una fuente activada produce
   error tipado, no precedencia silenciosa.
7. **RAG sin silencio.** Pedir RAG con el sustrato ausente produce error tipado,
   no un enriquecimiento vacio.
8. **Perezoso.** `memory maintain` se ejecuta con el core y Ollama inalcanzables.
9. **Aislamiento de la piel.** `cli.py` no importa `adapters` ni `clients`.
   Prueba automatizada.
10. **Migracion.** Un comando de solo lectura contra un esquema sin migrar falla
    con error tipado y no muta esquema.
11. **Codigos de salida.** `0`, `1` con `Tipo (campo): mensaje` en stderr, y `2`
    con ayuda del grupo.
12. **Error ajeno intacto.** Un error devuelto por el stub del core llega al
    llamante con su `type` y su `origin` originales, sin re-envolver ni traducir;
    un fallo propio de la capa lleva `origin` de esta capa.
13. **Traza encadenada.** Un evento de telemetria de una operacion que llamo al
    core lleva su `request_id` propio y el `downstream_request_id` del core.
14. Las pruebas existentes siguen en verde, con los skips esperados de PostgreSQL
    cuando no hay DB local.

## Entrega

Rama propia desde `main`. Al terminar, un documento
`docs/handoff/fase_7a_entrega.md` con: que se implemento, decisiones que hubo que
tomar y por que, criterios cubiertos uno a uno, lo que quedo fuera, e
inconsistencias detectadas SIN corregirlas por inferencia (se senalan).

Actualiza `CHANGELOG.md` bajo `[No publicado]` declarando el impacto de version.
No cortes tags. No hagas merge a `main`.

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia: eso
introduce diseno no reconciliado, y esta capa se construye en modo ciego.
