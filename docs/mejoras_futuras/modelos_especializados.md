# Modelos especializados: mejoras futuras a valorar

Estado: propuesta para valorar; adopcion y diseno sin reconciliar
Version: 0.1 - 2026-09-21
Categoria: recuperacion, extraccion y capacidades especializadas

## Alcance y estado del arte

El usuario aprueba el 2026-09-21 conservar y publicar las oportunidades
presentadas en la conversacion. Se aprueba el registro para futuras
evaluaciones, no la seleccion de modelos ni su incorporacion al producto.
Fuentes consultadas el 2026-09-21; revalidar versiones y disponibilidad al
abrir cada experimento. Complementa [Jev](jev_y_decisiones_tipadas.md).

No todo modelo de IA es un LLM conversacional. Hay encoders que puntuan o
extraen, detectores, reconocedores, modelos numericos y arboles entrenados para
una tarea. Tampoco todos son no generativos: un transcriptor de voz puede
generar secuencias sin ser un asistente generalista.

El panorama combina familias consolidadas (reranking, NLI, OCR y voz) con
encoders multitarea y modelos fundacionales de series temporales. No existe
un ganador universal ni evidencia de superioridad en IA Nest sin evaluacion
propia. Los candidatos siguientes ilustran capacidades, no un ranking global
del estado del arte ni una lista de modelos homologados.

## Oportunidades mas cercanas a las necesidades actuales

### Recuperacion: reranker multilingue

Candidato: [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3),
encoder multilingue con licencia Apache-2.0, ejecutable mediante
Transformers/FlagEmbedding. Puntua conjuntamente una consulta y un pasaje.
No es un modelo de embeddings ni requiere por si mismo reindexar el corpus.

Hipotesis: en extended, reordenar candidatos ya recuperados podria aumentar
la relevancia del contexto inyectado con un presupuesto limitado. No sustituye
los filtros de dominio, permisos o identidad. Su puntuacion, incluso
normalizada, no es una probabilidad calibrada de verdad.

Comparar contra la recuperacion actual: nDCG/Recall@k, utilidad de la respuesta,
latencia p95 y memoria con distintos limites de candidatos. Mantener una via
sin reranker si su coste no compensa. La recomendacion de embeddings existente
en extended ADR 0006 no cambia por registrar esta propuesta.

### Extraccion: encoders de entidades y estructuras

Candidatos: [GLiNER2.5 multilingue](https://huggingface.co/fastino/gliner2.5-multi-v1)
y [GLiNER multilingue](https://huggingface.co/urchade/gliner_multi-v2.1), con
licencia Apache-2.0 en las fichas consultadas. La familia permite extraer
fragmentos tipados; GLiNER2 amplia el repertorio a clasificacion y estructuras.
La [biblioteca GLiNER2](https://github.com/fastino-ai/GLiNER2) distingue la
ejecucion local del cliente de servicio: verificar el modo offline elegido.

Hipotesis: acelerar la deteccion de menciones y campos en extended, conservando
el texto y los offsets de origen. Ser multilingue no acredita calidad suficiente
en espanol. Una mencion extraida no resuelve identidad, correferencia ni hechos
implicitos; tampoco convierte lo dicho por alguien en verdad.

Evaluar precision/recall por tipo y exactitud de fragmentos sobre casos propios.
No reemplaza por defecto toda la extraccion generativa ni la sintesis del
writeback. Las referencias exactas y la procedencia siguen gobernadas por
extended ADR 0004 y extended ADR 0013.

### Relaciones entre afirmaciones: inferencia de lenguaje natural

Candidato: [mDeBERTa-v3-base-mnli-xnli](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli),
encoder multilingue con licencia MIT. Clasifica relaciones de implicacion,
neutralidad o contradiccion entre textos. Es una linea base establecida, no
una afirmacion de liderazgo en benchmarks de 2026.

Hipotesis: ayudar a conscience a seleccionar pares que merecen revision.
La similitud vectorial de extended no demuestra contradiccion semantica; NLI
tampoco demuestra verdad factual. Deben controlarse sujeto, fecha, contexto,
negaciones y direccion de la implicacion antes de interpretar una etiqueta.

Evaluar falsos positivos de contradiccion, abstencion y calibracion en espanol.
El juicio sigue perteneciendo a conscience: una etiqueta no autoriza borrar
memorias, modificar identidad o elevar confianza. La ubicacion del runtime
no queda decidida por esta ficha.

## Otras familias, condicionadas a un consumidor real

| Familia y candidato | Posible aportacion | Condicion o limite |
|---|---|---|
| OCR: [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), detectores y reconocedores PP-OCR | Preparar documentos escaneados para una futura ingesta. | Elegir pesos para espanol, conservar documento/pagina y medir errores de texto y estructura. El codigo Apache-2.0 no sustituye revisar cada artefacto. PaddleOCR-VL incluye un modelo de lenguaje: no confundirlo con la via OCR especializada. |
| Deteccion de voz: [Silero VAD](https://github.com/snakers4/silero-vad), MIT | Detectar intervalos de habla en una futura interfaz de audio. | No transcribe ni identifica hablantes. Medir falsos cortes y ruido, con ejecucion local CPU/ONNX o PyTorch. |
| Transcripcion: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) y [pesos large-v3 convertidos](https://huggingface.co/Systran/faster-whisper-large-v3), MIT | Convertir voz en texto para un consumidor futuro. | Especialista de voz con decodificacion generativa; medir error en espanol, ruido, tiempo y memoria. CPU/GPU e INT8 disponibles no garantizan un presupuesto concreto. |
| Vision: [SigLIP 2](https://huggingface.co/google/siglip2-base-patch16-224), Apache-2.0 | Recuperacion imagen-texto o clasificacion visual por etiquetas. | Encoder, no razonador visual ni generador de explicaciones. Necesita corpus o interfaz visual; evaluar espanol y mantener separados los espacios de embeddings. |
| Series temporales: [Chronos-2](https://huggingface.co/amazon/chronos-2), Apache-2.0 | Pronosticar demanda, consumo o magnitudes de un dominio. | Modelo numerico multivariante ejecutable localmente; comparar con predictores simples y particiones temporales. Una posible senal para pulse no sustituye su regulacion tecnica ni concede autoridad de actuacion. |
| Datos tabulares: [CatBoost](https://github.com/catboost/catboost), Apache-2.0 | Clasificar incidencias o estimar duraciones a partir de campos estructurados. | Arboles entrenados con datos propios, no un checkpoint universal. Exige etiquetas y un caso concreto; comparar con reglas o regresion sencilla. |

TabPFN ilustra la evolucion hacia modelos fundacionales tabulares, pero no se
propone como candidato aprobado: la [licencia de los pesos TabPFN 2.6](https://huggingface.co/Prior-Labs/tabpfn_2_6/blob/main/LICENSE)
consultada limita su uso a fines no comerciales y no productivos. No extrapolar
la licencia del codigo a los pesos ni esta restriccion a todas las versiones.

Estas oportunidades no amplian los formatos de ingesta actuales ni asignan
audio o vision al core. Primero debe existir una necesidad y decidirse la capa
propietaria conforme al alcance y a la gobernanza del ente.

## Premisas y puerta de entrada a una evaluacion

Aplican las premisas y fronteras referenciadas en la [ficha de Jev](jev_y_decisiones_tipadas.md#alternativas-y-premisas),
no una politica nueva de esta ficha. En particular:

1. Ejecucion local verificable tras descargar los artefactos, sin remision de
   datos a servicios externos. Ollama no es sinonimo de localidad: muchos de
   estos especialistas requieren otro runtime, cuyo coste debe justificarse.
2. Revisar por separado licencia de codigo y pesos, procedencia, revision
   fijable, idioma y restricciones de uso. Ser abierto no implica cumplir todas
   las premisas. En dominios sensibles, aplicar tambien el criterio de
   procedencia de la configuracion del core; no asumir que elimina sesgos.
3. Definir consumidor, propietario, error tolerable y presupuesto de recursos.
   No equiparar tamano de descarga con RAM/VRAM de ejecucion.
4. Comparar con el comportamiento vigente y una alternativa sencilla, con datos
   en espanol representativos y conjuntos separados de ajuste y prueba.
5. Medir calidad y coste de extremo a extremo: arranque, concurrencia, recargas,
   p50/p95, memoria y degradacion del resto del ente. Para pronosticos, evitar
   fuga temporal y comprobar cobertura de los intervalos.
6. Preservar procedencia, trazabilidad y posibilidad de desactivar o sustituir
   el especialista. Una puntuacion o clasificacion no cambia permisos.

## Priorizacion sugerida, no comprometida

Por proximidad al trabajo actual, valorar primero reranking y extraccion en
extended, solo si aparecen problemas medidos que los justifiquen. Considerar
NLI cuando conscience tenga un consumidor real. OCR, voz, vision, series
temporales y tabular quedan condicionados a sus respectivos dominios.

Hoy no hay pruebas comparativas del laboratorio ni ganador seleccionado.
La siguiente decision pendiente es escoger un unico experimento con umbrales
de aceptacion previos, no instalar una coleccion de modelos.

## Impacto

Solo documentacion de propuestas: sin cambios de contrato, codigo,
configuracion, SemVer o tag. No se modifica el plan vigente ni se abre un CR.
Si una evaluacion conduce a un cambio, su diseno y resultado se reconciliaran
en la capa propietaria; se declarara entonces el impacto contractual conforme
a `ia_nest_meta/docs/POLITICA_SEMVER.md` y se tramitara CR si corresponde.
