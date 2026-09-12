# Decision 0013: procedencia de engramas y anotacion de contradiccion

Fecha: 2026-08-22

## Contexto: una brecha entre la doctrina y el codigo

El ADR 0007, en su enmienda del 2026-08-13, ya fijo la frontera de confianza:
el write-back mecanico produce CANDIDATOS (operativa, no confiable), y la
promocion a memoria durable-CONFIABLE es escritura supervisada del guardian.

Esa frontera NO estaba materializada. Medido en laboratorio el 2026-08-21 sobre
una sesion real de cuatro turnos:

- La extraccion de fase 3 recibe el turno del usuario y el del asistente en un
  mismo bloque (`USER:` / `ASSISTANT:`) y pide "informacion dicha en la
  conversacion". No distingue quien lo dijo: una alucinacion del modelo se
  persiste como `episodic/facts` con `confidence: 1`.
- El recall inyecta esos items como `[episodic/facts] ...`, indistinguibles de
  cualquier otro y con el mismo peso.
- El dedup detecta REDUNDANCIA (similitud >= 0.92 refuerza) pero no
  CONTRADICCION: dos items opuestos no alcanzan ese umbral, asi que COEXISTEN.
- `EngramStatus.SUPERSEDED` estaba declarado en el modelo y sin usar en ninguna
  linea del codigo.

Efecto observado: en el cuarto turno el contexto inyectado contenia a la vez
`[episodic/facts] La pelicula de 2011 es una precuela` y `[episodic/facts] No
tiene precuelas ni secuelas directas`. El modelo no podia sino contradecirse.
Cada alucinacion se convertia en premisa del turno siguiente.

## Decision

### 1. Procedencia como dato objetivo del engrama

Campo `stated_by` en `engrams`, con tres valores. El campo NO se llama
`provenance`: ese identificador ya designa el origen de una entrada del catalogo
(`own`, `overridden`, `forwarded`) en `capability.list`, y dos significados para
un mismo nombre en el mismo contrato publico es aliasing de vocabulario
(Leccion 1 del roster). `stated_by` dice ademas lo que el campo es: quien lo
dijo.

- `user`: lo dijo el interlocutor.
- `model`: lo genero el modelo.
- `unknown`: no consta.

`unknown` es el valor de los engramas anteriores a esta decision y de los items
cuya atribucion no se puede verificar. NO se les inventa procedencia: se aplica
el mismo criterio que `extended CR-0005` fijo para `source_trace_id`, un hueco
visible es mejor que un valor plausible y falso.

### 2. La procedencia la pone el codigo, no el modelo

La extraccion pide dos listas separadas (`from_user`, `from_assistant`) en el
mismo JSON, y es el CODIGO quien marca cada item segun la lista en que vino. Una
sola llamada, como hasta ahora: el coste no se duplica.

Salvaguarda mecanica: un item atribuido a un bloque debe tener anclaje lexico en
el texto de ese bloque. Sin anclaje suficiente, el item se degrada a `unknown`.
La garantia que se esta construyendo no puede depender de que acierte el mismo
modelo cuya falibilidad la motiva.

El anclaje obliga a una condicion sobre la extraccion que se descubrio
ejerciendola (e2e en laboratorio, 2026-08-22): el prompt tiene que PROHIBIR
traducir. Estando el prompt en ingles, `mistral_nemo` devolvia en ingles items
de una conversacion en espanol -o con `content` nulo-, el anclaje no reconocia su
propio bloque y TODA la atribucion caia a `unknown`; con la prohibicion
explicita, el item sale en su idioma y ancla. Sin esa linea el mecanismo es
inocuo: nada se atribuye, luego nada se anota.

### 3. La procedencia viaja al contexto

El recall marca la fuente en la linea inyectada: `(fuente: usuario)`,
`(fuente: modelo, sin verificar)`, `(fuente: no registrada)`. Un candidato deja
de ser indistinguible de un hecho.

### 4. La version del usuario ANOTA la del modelo; no la retira

Al escribir un item con `stated_by = user`, los engramas del mismo
`user_id`+`namespace` con `stated_by = model` que caigan en la BANDA DE
CONFLICTO -similitud entre `conflict_threshold` y `dedup_threshold`- reciben un
enlace `contradicted_by` en `memory_links`. **Su estado no cambia.** El recall
lee ese enlace y hace dos cosas: etiqueta la linea y la despriorza al recortar
por presupuesto.

Banda de conflicto: por encima de `dedup_threshold` el item es el MISMO (se
refuerza, como hasta ahora); por debajo de `conflict_threshold` no habla del
mismo asunto.

**Por que anotar y no retirar, que era la intencion inicial.** Medido en el lab
el 2026-08-22 con `bge-m3` (`local/lab/2026-08-22_banda_de_conflicto.md`): con
frases paralelas la similitud SI separa contradecir (0.7747-0.8303) de compartir
tema (0.6861-0.7285), pero el hueco es de ~0.046 y la redaccion real lo cruza
-una correccion autentica midio 0.7242, por debajo del umbral, mientras un par
pregunta/respuesta del mismo usuario midio 0.8140-. Un margen de centesimas no
sostiene una accion destructiva sobre la memoria. Anotar y despriorar tiene el
coste de error correcto: un falso positivo cambia un orden, no retira un
candidato legitimo.

Por lo mismo, la etiqueta dice solo lo que el mecanismo sabe -"hay una version
del usuario sobre esto"- y nunca "esto es falso" ni "corregido": con umbral
permisivo habria casos en que eso seria mentira, y una marca que miente al
modelo es peor que no marcar.

Esto es MECANISMO y no juicio, por el test de frontera del propio ADR 0007: no
evalua merito, significado ni etica; senala coincidencia sobre una banda de
similitud y deja el veredicto al lector del contexto.

Consecuencia honesta: `EngramStatus.SUPERSEDED` SIGUE sin usarse. Es un estado
que el modelo declara y que ningun flujo de esta capa necesita todavia; su sitio
natural es la escritura supervisada del guardian, no un barrido mecanico.

## Alternativas consideradas

- **Que el modelo etiquete la procedencia item a item.** Descartada: la
  procedencia es la garantia, y hacerla depender del modelo que alucina la
  vacia de contenido.
- **Dos llamadas de extraccion, una por emisor.** Es la version rigurosa y fue
  la primera opcion. Descartada por coste: la extraccion tardo entre 6 y 20 s
  por turno en el lab, y duplicarla contradice la tesis de frugalidad del ente.
  Las dos listas mas el anclaje lexico dan la misma garantia por el mismo precio.
- **No extraer episodicos del turno del asistente.** Tentadora -su respuesta ya
  vive cruda en `dialog` por diseno- pero tira contenido legitimo: una
  conclusion trabajada por el modelo es un candidato valido. La enmienda del ADR
  0007 permite llenar el pozo de candidatos; lo que prohibe es que alcancen lo
  confiable sin guardian. Marcarlos cumple; tirarlos sobra.
- **Detectar contradiccion con un modelo.** Seria juicio, y cruzaria la frontera
  del ADR 0002 hacia conscience. Ademas pondria a arbitrar sobre la veracidad al
  mismo componente que la falla.
- **Un campo `trust` (candidato/confiable).** Descartada HOY: seria constante
  -todo lo que escribe el write-back es candidato por la enmienda del ADR 0007-
  y su unico escritor posible, el guardian, no existe. Costura muerta (core ADR
  0035). `stated_by` es lo que hoy tiene consumidor real; `trust` se anadira
  cuando conscience lo escriba.

## Consecuencia

- Migracion `0004_stated_by.sql`: campo `stated_by`, sus indices, y
  `contradicted_by` en el CHECK de `memory_links.link_kind`.
- `EngramStatus.SUPERSEDED` SIGUE sin usarse, y es coherente con la decision 4:
  la version del usuario ANOTA la del modelo, no la retira. (Correccion del
  2026-09-12: esta linea decia que dejaba de ser un estado muerto, y se
  contradecia con el cuerpo del propio ADR. Venia de un borrador anterior en el
  que la version del usuario si retiraba la del modelo; esa forma se descarto
  por el margen medido. Verificado en el codigo: el valor solo aparece
  declarado en el modelo.)
- Config nueva: `conflict_threshold`, calibrado en 0.70 contra `bge-m3` en el
  banco del lab, no elegido a ojo.
- `Engram.contradicted`, derivado del enlace en cada recuperacion. No es columna:
  la unica fuente de verdad es `memory_links`, y asi cambiar el umbral cambia el
  comportamiento sin migrar dato alguno.
- Contrato publico: `stated_by` aparece en lo que devuelve `memory.recall` y se
  acepta en `memory.write`. Adicion compatible -> MINOR.
- La politica de write-back cambia y se actualiza `docs/POLITICA_WRITEBACK.md`.

## Enmienda (2026-09-12): la contradiccion no vive en un cajon

Hallado al cruzar dos ejecutores en la puerta de laboratorio, sobre un
despliegue natural. La anotacion disparaba unas veces si y otras no -6 de 9
repeticiones- sin que nada cambiara en el producto.

La causa no es la banda de similitud, que era la sospecha obvia. Es que
`record_contradiction` compara dentro del MISMO namespace
(`WHERE type_name = ? AND user_id = ? AND namespace = ?`), y el namespace lo
elige el modelo de extraccion. Medido: la frase del usuario cayo en
`episodic/tasks` y la del modelo en `episodic/facts`, misma frase y distinto
cajon, asi que el candidato ni siquiera entro en la comparacion.

Era un supuesto no escrito de esta decision: que las dos versiones del mismo
hecho caen en el mismo namespace. Depende de un modelo, luego no se sostiene.

**Se corrige:** la deteccion compara dentro del TIPO y del usuario, sin filtrar
por namespace. Una contradiccion es sobre el CONTENIDO, no sobre el cajon donde
el extractor lo puso. El riesgo de comparar mas candidatos esta acotado por dos
cosas que ya decidio este ADR: la banda de similitud sigue gateando, y la accion
no es destructiva -anota y despriorza, no retira-.

**Y se recorta su papel.** Medido en nueve repeticiones, la linea que mide el
comportamiento corregido (L4a de la puerta) paso 3 de 3 en todas ellas, tambien
cuando la anotacion no disparo. Lo que sostiene que el modelo acepte la
correccion es marcar la PROCEDENCIA; la anotacion es refuerzo. Por eso deja de
ser criterio de la puerta y pasa a observacion medida, con su tasa registrada.
La decision 4 no cambia: el candidato del modelo se anota, nunca se retira.

## Lo que esta decision NO resuelve

La contradiccion se corrige cuando el usuario la corrige. Un contexto con muchos
candidatos del modelo sigue siendo un contexto ruidoso, solo que ahora marcado.
La sintesis que da DIRECCION al hilo -integrar "esto reemplazo a aquello" en vez
de acumular items sueltos- es la sintesis de cluster diferida en el ADR 0007, y
se aborda por su propia via.
