# Handoff de implementacion: el script de la puerta de laboratorio

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-09-12.
Base: `main`, su ultimo commit, con `v0.2.0` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. **`docs/PUERTA_LABORATORIO.md` entero.** Es el criterio, esta reconciliado y
   manda sobre este brief. Aqui solo esta como se implementa.
3. `docs/EXTENDED_CONTRACT.md`: las capacidades que el script ejerce.
4. `ia_nest_meta/docs/DOCTRINA_MULTI_IA.md`, regla de la puerta de laboratorio
   (meta ADR 0010).

## Que se pide

Un script `tools/lab/puerta.py` que ejecute la puerta y emita VEREDICTO.

- **Solo biblioteca estandar.** Nada de dependencias nuevas: tiene que correr
  en la maquina desplegada sin instalar nada. Es la misma regla que el smoke del
  core.
- **Habla REST**, que es la superficie que consumen las capas de encima. Las
  rutas se derivan del nombre de la capacidad: `prompt.run` -> `/prompt/run`,
  `memory.recall` -> `/memory/recall`, `memory.write` -> `/memory/write`,
  `knowledge.status` -> `/knowledge/status`, `capability.list` ->
  `/capability/list`.
- **Codigos de salida: 0 PASA, 1 NO PASA, 2 NULA.** Nula es "no se midio el
  producto" y no es un suspenso; la da cualquier precondicion incumplida.

### Superficie que vas a usar, verificada sobre el codigo

Cuerpo de una peticion enriquecida:

    {"prompt": "...", "domain": "linux", "identity": {"user_id": "...",
     "session_id": "..."}}

`identity` admite `user_id`, `session_id`, `service`, `namespace` y
`domain_tag`; lo que no se indica cae a defaults de configuracion.

Siembra de un candidato del modelo, para L3 y L4a:

    POST /memory/write
    {"principal": "extended",
     "request": {"type_name": "episodic", "namespace": "facts",
                 "content": "...", "stated_by": "model",
                 "identity": {"user_id": "...", "session_id": "..."}}}

`stated_by` admite `user`, `model` y `unknown`; omitirlo deja `unknown`.

### Identidad de cada pasada

`user_id` NUEVO en cada ejecucion, con prefijo reconocible (`puerta-<uuid4>`), y
`session_id` propio por hilo. **Nunca el `user_id` del operador**: mezclaria
trafico de prueba con su memoria real (`docs/FORMA_ENRIQUECIMIENTO.md`). El
script no borra nada: escribe bajo su propia identidad y ahi se queda.

### Testigos, que son el oraculo

Cada sonda lleva un TESTIGO fijado EN EL CODIGO, no generado a partir de la
respuesta. Dos clases:

1. **Aleatorio**: una cadena que el modelo no puede conocer (`perro llamado
   Xanthe-4f2a`). Se genera al arrancar la pasada y se usa en las dos puntas:
   lo que se afirma y lo que se comprueba.
2. **Par fijo**: dos valores incompatibles del mismo hueco (`martes`/`jueves`).
   Se comprueba presencia del correcto Y ausencia del incorrecto.

La comprobacion es lexica, insensible a mayusculas y acentos. **Ningun modelo
del sistema hace de juez.**

## Lineas a implementar

Cada una devuelve veredicto propio y su evidencia. `docs/PUERTA_LABORATORIO.md`
las define; esto es la traduccion a codigo.

**Precondiciones (si fallan: NULA, y no se ejecuta ninguna linea).**

- P1: `capability.list` responde y su `extended_version` coincide con el tag que
  se le pasa al script por argumento (`--tag`).
- P2: se le pasa por argumento la marca de tiempo de instalacion (`--instalado`)
  y el script comprueba contra ella el arranque del servicio, que obtiene de
  `systemctl show -p ExecMainStartTimestamp` SOLO si corre en la propia maquina;
  si no puede, lo declara NO COMPROBADO y la pasada es NULA.
- P3 y P4 son del operador y se registran como declaradas, no se comprueban.

**L1 Forma.** `capability.list` sin degradacion y con las capacidades propias
presentes. `knowledge.status` responde.

**L2 Continuidad.** Sesion A: el interlocutor afirma el testigo aleatorio.
Sesion B (mismo `user_id`, otro `session_id`): se pregunta por el. PASA si la
respuesta contiene el testigo Y `memory.recall` de B devuelve un engrama con ese
testigo y `stated_by=user`.

**L3 Procedencia.** Se siembra por `memory.write` un candidato
`stated_by=model` con el testigo incorrecto. El interlocutor afirma el correcto.
PASA si el contexto de `memory.recall` del turno siguiente trae el item del
modelo etiquetado (`fuente: modelo, sin verificar`), con la anotacion de que hay
una version del usuario, y colocado DETRAS de la version del usuario.

**L4a Coherencia, correccion de un candidato del modelo.** Hilo de cuatro
turnos sobre L3; el ultimo pregunta por el dato. PASA si la respuesta contiene
el testigo del usuario y no el del modelo.

**L4b Coherencia, autocorreccion del interlocutor.** Turno 1 afirma `martes`;
turno 3 corrige a `jueves`; turno 4 pregunta. PASA si contiene `jueves` y no
`martes`. **L4b se ejecuta y se registra, pero NO cambia el codigo de salida**:
es el brazo sin sintesis de la Fase 9. Su resultado sale en el informe con esa
etiqueta.

**L5 y L5r RAG.** NO EJECUTABLES hasta que el instalador acepte N corpus
(`docs/handoff/instalador_n_corpus_brief.md`). Deja el codigo escrito y que
declare `NO EJECUTABLE`, nunca `PASA`. No inventes un corpus para poder
ejecutarlas.

**L6 Repeticion.** Fuera del script: la ejecuta el operador repitiendo el
instalador y volviendo a lanzar la puerta. El script no invoca al instalador.

**Repeticion de las lineas:** `--n` con defecto 3. Una linea PASA con n de n.
Con menos, NO PASA, y el informe dice el reparto (por ejemplo `2/3`).

## Salida

- Humano por stdout: una linea por linea de la puerta con su veredicto y, en el
  fallo, el testigo esperado y el fragmento de respuesta que lo contradice.
- `--json RUTA` escribe la evidencia completa: peticiones, respuestas, testigos,
  veredictos y tiempos. Es lo que se guarda en `local/lab/` y lo que cruzan los
  dos agentes.
- Cabecera con lo que la puerta NO cubre, copiada de
  `docs/PUERTA_LABORATORIO.md`. Un PASA de forma no es un PASA de contenido, y
  el informe tiene que decirlo el mismo.

## Fuera de esta tarea (NO implementar)

- Tocar el servicio, la memoria, el RAG, el instalador o el core.
- Borrar datos, migrar esquema o reiniciar servicios.
- Juzgar la calidad de una respuesta mas alla de los testigos.
- Streaming y MCP.

## Criterios de aceptacion (falsables)

Se prueban contra un stub HTTP local, como ya hace `tests/test_rest.py`. **No
hace falta laboratorio y no debes entrar en el.**

1. **Veredicto verde.** Con un stub que responde lo esperado, salida 0 y todas
   las lineas ejecutables en PASA.
2. **Veredicto rojo.** Con un stub que devuelve el testigo incorrecto en L4a,
   salida 1 y esa linea en NO PASA con su evidencia.
3. **Nula por version.** Con un stub cuya `extended_version` no coincide con
   `--tag`, salida 2 y ninguna linea ejecutada.
4. **L4b no decide.** Con un stub que falla SOLO L4b, la salida es 0 y el
   informe la marca como brazo de la Fase 9.
5. **Reparto.** Con `--n 3` y un stub que falla una de las tres, la linea sale
   `2/3` y NO PASA.
6. **Identidad propia.** Toda peticion lleva un `user_id` con el prefijo de la
   pasada, y dos ejecuciones seguidas usan `user_id` distintos.
7. **L5 declarada.** Sin corpus, L5 y L5r salen NO EJECUTABLE y no afectan al
   codigo de salida.
8. **Solo estandar.** El script no importa nada fuera de la biblioteca estandar.

## Impacto de version

Ninguno: es instrumental, no toca contrato publico ni comportamiento de la capa.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x).
