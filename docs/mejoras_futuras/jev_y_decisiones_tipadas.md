# Jev y modelos de decisiones tipadas: mejora futura a valorar

Estado: propuesta para valorar; adopcion y diseno sin reconciliar
Version: 0.2 - 2026-09-21
Categoria: exploracion de modelos / decisiones acotadas del ente

## Motivo y alcance del registro

El usuario aprueba el 2026-09-21 conservar y publicar esta propuesta de mejora
futura. Se registra la posibilidad de evaluarla, no una decision de
incorporacion. Las otras familias se recogen en la ficha complementaria de
[modelos especializados](modelos_especializados.md).

Hogar: `docs/mejoras_futuras/`, propuestas pendientes de evaluacion dentro de
la documentacion del producto. Esta ficha sustituye al borrador local; no es
un ADR, un CR ni una fase comprometida del plan. Su presencia en este repo no
asigna la capacidad a extended. Si se adopta, el resultado reconciliado se
documentara en su capa propietaria, referenciando esta exploracion sin duplicar
doctrina. La informacion externa fue consultada el 2026-09-21.

## Que ofrece Jev

TypeSafe AI presento Jev el 2026-09-15 como modelo System One. Recibe un estado
y preguntas acotadas; devuelve elecciones, puntuaciones y probabilidades.
Su API ofrece `Choice`, `Score` y `Noul`. Evalua preguntas independientes en
paralelo y no redacta texto libre.

Fuentes primarias:

- [Introduccion oficial](https://docs.typesafe.ai/introduction).
- [Anuncio y limites de sus evaluaciones](https://typesafe.ai/blog/introducing-system-one-models-and-jev).

La oferta publica consultada es una API remota. No se han encontrado pesos
oficiales descargables ni una via oficial local en Ollama. Revalidar esta
disponibilidad antes de tomar una decision.

El proveedor declara baja latencia y entrenamiento para decisiones calibradas.
Son afirmaciones a verificar con el trabajo real del ente. Sus comparativas
de lanzamiento no prueban superioridad en espanol, ni sobre nuestro hardware,
ni frente a nuestras lineas base. Una salida dentro del esquema puede estar
equivocada. Una probabilidad nativa tampoco garantiza calibracion en otro
dominio. No confundir concentracion de la distribucion con acierto observado.

## Aportacion que se quiere medir

Reducir tiempo y coste en decisiones semanticas repetitivas que tienen un
conjunto pequeno de resultados posibles. Conservar el estado de entrada,
criterios, revision del modelo y resultado para poder auditar la decision.
Permitir abstencion y escalado cuando la evidencia sea insuficiente.

No sirve para redactar planes, combinar respuestas, resumir hilos o formular
principios nuevos. Un modelo generativo sigue siendo necesario en esos pasos.
La validez de esquema no sustituye permisos, limites ni supervision.

## Encaje por funcion, pendiente de diseno

| Caso | Propietario de la funcion | Valor potencial y limite |
|---|---|---|
| Clasificar el dominio | core | Candidato para la clasificacion de `domain.route`; el contrato tambien exige motivo breve, que Jev no redacta. |
| Evaluar cobertura o suficiencia | core | Apoyo a validadores y EVALUATE; comprobar si puede cubrir todos los campos actuales, no solo el veredicto. |
| Cribar riesgos o conflictos con principios | conscience | Senal auxiliar para decidir que requiere deliberacion; no sustituye el juicio etico ni la personalidad. |
| Priorizar experiencias para reflexion | conscience | Puede proponer candidatos; no concede autoridad para escribir identidad o memoria confiable. |
| Elegir capacidad o iniciar investigacion | Sin hogar decidido | Concern ya registrado en meta; este modelo no resuelve su propiedad ni su orquestacion. |

Referencias que gobiernan esta valoracion:

- `ia_nest_core/docs/CORE_CONTRACT.md` y `docs/FRONTERAS.md`.
- core ADR 0034 y core ADR 0036: orquestacion y supervision. Los eventos
  observables no equivalen a un veto remoto ya implementado; su semantica
  interventora necesita su propia costura y consumidor.
- `ia_nest_meta/docs/CAPAS_FUTURAS.md`, "Quien decide y quien orquesta lo que
  el ente hace": seleccionar capacidad sigue sin hogar asignado.
- `docs/VISION_MEMORIA.md`, extended ADR 0002 y extended ADR 0007:
  sustrato/mecanismo en extended; juicio de significado y merito en conscience.
- extended ADR 0013: procedencia verificable y anotacion mecanica no equivalen
  a dictaminar verdad o contradiccion semantica.
- core ADR 0037: pulse es regulacion tecnica CPU/RAM, fuera de banda.

Precision respecto a la conversacion inicial: no queda decidido que toda
inferencia especializada deba alojarse en el core. El propietario de una
funcion y el servidor que ejecuta un modelo son decisiones distintas. El core
puede evaluar una mejora de su router; conscience puede necesitar un apoyo
propio. La ubicacion tecnica exige un caso consumidor y contrato concreto.

## Alternativas y premisas

Premisas documentadas: calidad, rendimiento, control local, sustituibilidad y
trazabilidad (`ia_nest_core/docs/VISION_FUNCIONAL.md`); espanol y coste moderado
(extended ADR 0006). La plantilla `ia_nest_core/config/core.lab.example.yaml`
expresa ademas la preferencia por modelos occidentales para dominios sensibles
a sesgo, incluido el fallback. La procedencia no demuestra ausencia de sesgos.

| Alternativa | Situacion para esta exploracion |
|---|---|
| Jev oficial | Referencia tecnica; la via remota consultada no satisface el objetivo de inferencia local. |
| LLM local con JSON Schema en Ollama | Linea base funcional disponible. Sigue generando texto; pedirle una cifra de confianza no reproduce la calibracion de Jev. |
| OpenJev, `razorback16/openjev` | Implementacion comunitaria independiente con API semejante, servida por vLLM o MLX. No es Jev oficial ni un modelo Ollama intercambiable. Evaluar recursos y madurez. |
| Laya Typed-Decisions | Checkpoint abierto especializado, ingles y limitado a cuatro familias de tareas; su propia ficha advierte sobre sobreconfianza y comparaciones no equivalentes con Jev. No se da por apto para el ente en espanol. |
| Granite Guardian / Llama Guard | Comparadores para juicios de seguridad concretos. Son modelos basados en LLM y no equivalentes generales a Jev. Revisar idioma, taxonomia y licencia del checkpoint. |

`qwen2.5:7b` figura como recomendacion de extraccion en extended ADR 0006,
no como modelo acreditado de conscience. Su posible uso como control de tareas
tecnicas no extiende esa recomendacion a etica o personalidad. La configuracion
efectiva y los modelos disponibles deben comprobarse al abrir el experimento.

Fuentes para revisar las alternativas:

- [JSON Schema en Ollama](https://docs.ollama.com/capabilities/structured-outputs).
- [OpenJev independiente](https://github.com/razorback16/openjev).
- [Laya: alcance, licencia y limitaciones](https://huggingface.co/convaiinnovations/laya-typed-decisions).
- [Granite Guardian en Ollama](https://ollama.com/library/granite4.1-guardian).
- [Llama Guard en Ollama](https://ollama.com/library/llama-guard3).

## Disparador y evaluacion pendiente

Abrir la valoracion cuando una decision concreta presente coste o errores
medidos, o cuando conscience tenga un consumidor real que necesite esa criba.
La novedad del modelo por si sola no justifica anadir infraestructura.

Antes de elegir candidato:

1. Definir una sola tarea inicial, su propietario y el coste de equivocarse.
2. Fijar un conjunto de casos en espanol con etiquetas externas al modelo;
   incluir ambiguedad, negaciones, falta de informacion y casos fuera de dominio.
3. Comparar contra el comportamiento actual y contra una solucion sencilla.
4. Separar calibracion y prueba: ajustar umbrales en un conjunto y evaluar en
   otro; medir acierto, falsos positivos/negativos, abstenciones, estabilidad
   ante parafrasis y calibracion (Brier/ECE cuando corresponda).
5. Medir latencia p50/p95, arranque en frio, RAM/VRAM y convivencia con los
   modelos ya residentes. Un modelo pequeno puede empeorar el conjunto si
   provoca recargas continuas.
6. Comprobar ejecucion sin red tras provisionar, licencia de codigo Y pesos,
   idioma, procedencia, version fijable y trazabilidad de las decisiones.
7. Declarar umbrales de aceptacion antes de medir. Adoptar solo si mejora el
   caso acordado sin deteriorar sus restricciones. Hoy no hay mediciones del
   laboratorio ni ganador declarado.

Ollama y ejecucion local no son sinonimos. Una alternativa con otro runtime
puede preservar localidad, pero tiene coste de instalacion y mantenimiento;
no se da por aceptado ese coste desde esta ficha.

## Impacto y siguiente decision

Esta nota no modifica contrato, codigo ni configuracion: sin impacto SemVer,
sin entrada de CHANGELOG y sin tag. No reserva una capacidad `decision.*`.
Un futuro cambio se valorara en la capa duena conforme a
`ia_nest_meta/docs/POLITICA_SEMVER.md`; si necesita contrato ajeno, usara CR.

Pendiente del usuario: elegir si merece abrirse un experimento y sobre que
decision real. El registro de las propuestas esta aprobado; su priorizacion,
el diseno y cualquier implementacion siguen pendientes.
