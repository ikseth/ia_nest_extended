# Entrega de implementacion: fase 7b

Autor: agente codificador (modo ciego).
Base: `main`, commit `f91abcd`.
Fecha: 2026-08-18.
Brief: `docs/handoff/fase_7b_brief.md`.

Verificacion: NO la hace quien implementa. Este documento declara lo hecho, las
decisiones de implementacion, los criterios cubiertos, lo que queda fuera y las
inconsistencias observadas.

## 1. Que se implemento

### `reasoning.run`

`ExtendedService.reasoning_run` reutiliza `MemoryEnricher`: recall de memoria y
RAG, composicion dentro del presupuesto, llamada tipada al core y write-back. El
cliente interpreta solo `output` y `trace`; el payload completo del core se
devuelve intacto. Tiene passthrough, traza propia y piel CLI interina con las
banderas del camino upfront de `prompt run`.

### `task.run`

El camino enriquecido ejecuta:

1. `task.plan` con el prompt original, identidad y `effort` opcional.
2. Copia del objeto de respuesta, eliminando solo `params`.
3. RAG independiente para cada subtarea, gateado por su `domain` ya resuelto.
4. Edicion exclusiva de `plan[i].prompt`.
5. Recall de memoria una vez, sobre el prompt superior para COMBINE/EVALUATE.
6. `task.run` con el prompt superior enriquecido y el plan suministrado.
7. Write-back del prompt ORIGINAL y la respuesta COMBINADA final.

`requirements`, `effort`, campos hermanos desconocidos y campos estructurales
desconocidos de cada subtarea se preservan. No se llama a `domain.route`. El
dominio `general` de una subtarea usa recuperacion RAG global, igual que el
camino upfront. El limite `rag_max_tokens` se aplica por subtarea e incluye el
envoltorio que se inyecta, medido con `estimate_tokens`.

Con `enrich=False`, el servicio llama directamente a `task.run`: no pide plan,
no envia `plan` y no pierde la re-planificacion del core.

### CLI, telemetria y medida

La CLI gana `reasoning run` y `task run`, ambas superficies escritas a mano y
marcadas INTERINAS en sus descripciones. En `task run`, `--domain` se usa solo
como faceta de lectura de memoria y no entra en la identidad enviada al core.

Los eventos propios `reasoning.run` y `task.run` encadenan `request_id` y
`downstream_request_id`; `task.run` anade `subtasks_enriched`.

`local/lab/fase_7b_tres_brazos.py` ejecuta tres repeticiones de la misma tarea en
los brazos sin plan, plan en eco y plan enriquecido. Emite `stop_reason`,
`requirements_covered`, numero de degradaciones, gasto, longitud de respuesta y
tiempo. Usa un `user_id` de laboratorio propio y desactiva write-back.

## 2. Decisiones de implementacion

1. La copia hacia `task.run` elimina SOLO `params`. La traza y cualquier campo
   hermano nuevo se preservan, porque el brief exige copiar el objeto y prohibe
   una lista blanca.
2. El presupuesto RAG de tarea cuenta tambien el envoltorio
   `<enrichment_context>`. Es la lectura mas estricta del criterio 5 y usa la
   misma funcion `estimate_tokens` de la capa.
3. `task run` no ofrece `--auto-domain`: el dominio RAG ya viene resuelto por
   subtarea y el brief prohibe llamar a `domain.route`. Conserva las banderas de
   fuentes y write-back de `prompt run`; `--domain` tiene la semantica especifica
   que el brief fija para tareas.
4. La extraccion episodica de tarea reusa literalmente la politica y el modelo
   del write-back existente. No se crea una politica paralela.

## 3. Criterios de aceptacion

| # | criterio | cobertura | estado |
|---|---|---|---|
| 1 | Copia fiel | `test_task_plan_is_copied_faithfully_except_params` conserva `future_sibling` | pasa |
| 2 | `params` no vuelve | la misma prueba aserta ausencia en `task.run` | pasa |
| 3 | Solo se edita `prompt` | compara todos los campos restantes de cada subtarea | pasa |
| 4 | RAG por dominio | `test_task_rag_is_gated_and_bounded_per_subtask` usa `linux` y `codigo` sin cruce | pasa |
| 5 | Tope por subtarea | la misma prueba mide cada bloque con `estimate_tokens` | pasa |
| 6 | Tres brazos | `local/lab/fase_7b_tres_brazos.py`, tres repeticiones y tabla completa | escrito; no ejecutado contra lab por prohibicion del brief |
| 7 | Passthrough | `test_task_passthrough_does_not_plan_or_supply_a_plan` | pasa |
| 8 | Write-back | `test_task_write_back_uses_only_original_and_combined_turns` | pasa |
| 9 | `reasoning.run` transparente | `test_reasoning_run_keeps_the_core_payload_intact` | pasa |
| 10 | Telemetria | `test_task_telemetry_chains_ids_and_counts_subtasks` | pasa |
| 11 | Perezoso | la prueba existente `test_maintain_runs_with_core_and_ollama_unreachable` no cambia | pasa en la seleccion sin red |
| 12 | Regresion | pruebas nuevas y seleccion sin red en verde; suite completa bloqueada por el sandbox, detalle abajo | parcial por entorno |

Resultados locales:

- `python -m pytest tests/test_phase7b.py -q`: 8 pasan.
- seleccion nueva y existente sin sockets: 35 pasan.
- `python -m compileall -q src tests`: pasa.
- La suite completa recolecta 107 pruebas: 37 pasan, 26 se omiten y 44 no pueden
  arrancar porque este sandbox prohibe crear incluso sockets loopback. Esas 44
  pruebas usan el stub HTTP local y fallan en fixture con `PermissionError:
  [Errno 1] Operation not permitted`. Las 26 pruebas PostgreSQL se omiten por
  `IANEST_EXTENDED_TEST_DSN` ausente. El fallo de sockets ya ocurre sobre el
  `main` base antes de estos cambios.

## 4. Fuera de fase

- `capability.list` sobreescrita, catalogo fusionado y retirada de la CLI
  interina.
- `task.stream` y `prompt.stream` enriquecidos; ambos siguen reenviados crudos.
- Rango `docs/DEPENDENCIAS.md >=0.4`; espera al tag del core.
- REST, MCP, primer tag y cualquier cambio en el core.
- Esquema de memoria, politica de write-back, ranking, consolidacion y deudas
  D1-D3.
- Ejecucion contra el laboratorio o cualquier direccion `192.168.x.x`.

## 5. Inconsistencias detectadas, sin corregir por inferencia

1. `docs/DEPENDENCIAS.md` todavia describe `task.plan` como futuro y dice que el
   techo se reevalua al entregarse. El brief ordena expresamente NO tocarlo hasta
   que exista el tag v0.4.0; se deja intacto.
2. `ia_nest_core/docs/CORE_CONTRACT.md` rotula `task.plan` y la entrada de plan
   de `task.run` como "implementacion pendiente", mientras el brief declara la
   linea completa en `main` (`705941e`) y el codigo consultado la contiene. Es
   una inconsistencia del repo del core; no se modifica desde esta capa.
3. `docs/PLAN.md` conserva en la seccion 7a texto historico que presenta
   `capability.list` como aun no entregado. Corregir el descubrimiento y fusionar
   el catalogo pertenece a la siguiente rebanada, que el brief deja fuera; no se
   adelanta aqui.

## 6. Impacto de version

Ninguno: no existe aun contrato publicado ni primer tag. Se actualiza
`CHANGELOG.md` bajo `[No publicado]`; no se corta tag.

## 7. Estado de staging en este entorno

El trabajo queda completo en el working tree sobre `main`, sin rama, commit ni
push. No pudo dejarse staged porque el sandbox monta `.git` como solo lectura:
`git add` falla al crear `.git/index.lock` con `Read-only file system`. No se
intento ningun rodeo sobre el indice. Las rutas exactas que debe anadir el
revisor fuera de este sandbox son las enumeradas en el estado final; el script
de `local/lab/` requiere `git add -f` porque `local/` esta ignorado.
