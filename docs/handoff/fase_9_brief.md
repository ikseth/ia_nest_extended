# Handoff de implementacion: Fase 9, sintesis de hilo

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus sobre el banco y el laboratorio. NUNCA quien implementa.
Fecha: 2026-09-21.
Base: `main`, su ultimo commit, con `v0.2.3` publicada.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PLAN.md`, Fase 9 entera: alcance, lo que NO entra y el criterio de
   salida reconciliado el 2026-09-12.
3. `docs/decision_records/0007-mecanismo-de-consolidacion.md`, sus dos ultimas
   enmiendas. La del 2026-09-12 -"recordar no es sostener un hilo"- fija los
   limites que mas importan aqui.
4. `docs/decision_records/0013-...md` (procedencia) y `docs/ROSTER_MEMORIA.md`.
5. `docs/POLITICA_WRITEBACK.md` y `docs/PUERTA_LABORATORIO.md`, linea L4b.

## Por que existe esta fase, medido

Un conjunto de engramas atomicos **no puede expresar que uno reemplaza a otro**:
solo coexistir. Medido en laboratorio el 2026-08-21: con cuatro turnos y siete
engramas el contexto ya llevaba dos hechos incompatibles del mismo asunto.

Y medido otra vez el 2026-09-12 y el 2026-09-21, con la puerta de laboratorio:
la linea **L4b** -el interlocutor dice "la reunion es el martes", se corrige a
"jueves", y despues se le pregunta- va **2 aciertos de 15** repeticiones
limpias. El modelo responde "Martes" trece de quince veces.

Lo que da DIRECCION a un hilo es una frase con estructura temporal. Eso es
sintesis, y es lo que falta.

## Lo que se pide, en una frase

Que el hilo de una sesion tenga, ademas de sus engramas anclados, **un resumen
mecanico por ventana de turnos**, y que ese resumen ocupe en el contexto el
sitio de lo que resume.

## Decisiones de diseno (reconciliadas; no las reabras)

### 1. Un tipo de memoria nuevo: `thread_summary`

Se declara en `seed_memory_types()` (`registry.py`), junto a los demas:

- `memory_class`: STRICT. `writer_principal`: EXTENDED.
- `retrieval_mode`: RANKED. `scope`: **SESSION**, como `dialog`: el hilo es la
  sesion.
- Pesos dominados por recencia, del orden de `dialog`; `half_life_seconds` igual
  que `dialog` (4 h).
- Namespace: uno propio y unico.

NO se reaprovecha `dialog` con un namespace especial: seria aliasar dos tiers, y
la leccion 1 del roster lo prohibe expresamente.

### 2. Se genera en el write-back, no en el recall

Al terminar de persistir los items de un turno (`enrichment.py`, donde hoy
termina el bucle que escribe `episodic` y anota contradicciones), si el hilo
acumula al menos `thread_synthesis_window_turns` turnos desde la ultima
sintesis, se genera una nueva y **sustituye** a la anterior de ese hilo.

No se genera al recuperar: meteria una llamada al modelo dentro de la latencia
del turno del interlocutor.

### 3. Tres claves de configuracion

    thread_synthesis_enabled       IANEST_EXTENDED_THREAD_SYNTHESIS_ENABLED   bool, default false
    thread_synthesis_window_turns  IANEST_EXTENDED_THREAD_SYNTHESIS_WINDOW_TURNS  int, default 4
    synthesis_model                IANEST_EXTENDED_SYNTHESIS_MODEL            str, default: el de extraccion

Apagado por defecto, y es deliberado: una instalacion existente no cambia de
comportamiento sola, y el criterio de salida exige medir con y sin. Encenderlo
por defecto sera otra decision, DESPUES de medir.

La ventana es configurable porque el 4 es un punto de partida medido, no una
constante: es donde aparecio el problema.

### 4. Anclaje por enlaces, no por texto

Cada sintesis registra en `memory_links` un enlace **`summarizes`** hacia CADA
engrama de su ventana. Migracion **0005**, que amplia el CHECK de `link_kind`
como hizo la 0004 con `contradicted_by`. No edites migraciones publicadas.

Esto es lo que hace verificable el criterio de anclaje: se cuentan enlaces
contra items de la ventana, no se lee el resumen.

### 5. Procedencia heredada del ADR 0013

La sintesis registra su `stated_by`. Si la ventana mezcla emisores -lo normal-,
queda **`unknown`**: una sintesis que mezcla emisores NO puede presentarse como
dicha por ninguno. No se inventa atribucion.

### 6. Composicion: combinado en el almacen, sustitucion en el presupuesto

Los engramas resumidos **siguen en el almacen y siguen siendo direccionables**.
Lo que cambia es lo que se INYECTA: cuando el hilo tiene sintesis, las lineas de
contexto de los engramas que ella resume -los alcanzables por `summarizes`- no
se componen, y en su lugar va la sintesis.

Punto de enganche: la construccion de lineas de contexto y `_compose_context` en
`enrichment.py`, con su orden de recorte por tier.

### 7. Vive y muere con el hilo

- `maintain` archiva la sintesis **cuando archiva el `dialog` de esa sesion**.
- `maintain` **NUNCA** la promociona a `semantic`. Hoy la promocion solo mira
  `episodic`, asi que basta con no anadirla; el criterio exige que exista prueba
  de que no ocurre.

Motivo, y es el limite mas importante de la fase: la sintesis es ESTADO DE
TRABAJO, no un recuerdo. Un resumen alucinado en memoria duradera envenenaria el
yo del ente de forma permanente.

### 8. Traza propia

Evento de telemetria nuevo para cada sintesis: identidad, turnos de la ventana,
items resumidos, modelo usado, latencia y estado. Sin el, calibrar la ventana es
a ciegas.

## Lo que NO entra (y si lo haces, esta mal)

- **Que la sintesis ELIJA que merece recordarse.** Eso es juicio y es de
  conscience (ADR 0002, test de frontera del ADR 0007). Aqui la ventana es
  temporal y mecanica: resume lo que hay, no lo que importa.
- Tocar el dedup, la anotacion de contradiccion, los umbrales o sus defectos.
- Tocar los tipos delegados, el core, el instalador o el laboratorio.
- Promocionar, retirar o modificar engramas existentes. La sintesis se SUMA.

## Criterios de aceptacion (falsables)

Los de PostgreSQL se ejecutan; hay banco. No los declares "no ejecutados" sin
intentarlo.

1. **Apagada, nada cambia.** Con `thread_synthesis_enabled=false` -el defecto-
   no se genera ninguna sintesis, no se escriben enlaces y el contexto compuesto
   es identico al actual, bit a bit.
2. **Ventana.** Con la ventana en N, la sintesis aparece al cumplirse N turnos
   del hilo y no antes; al siguiente bloque de N, la anterior se sustituye.
3. **Tipo declarado.** `memory_type.list` publica `thread_summary` con
   `scope=session` y `writer_principal=extended`; una escritura de otro
   principal se rechaza.
4. **Anclaje.** Cada sintesis tiene tantos enlaces `summarizes` como items
   resume, comprobado por CONSULTA. Sin enlaces no hay sintesis valida.
5. **Sustitucion.** Con sintesis, las lineas de los engramas resumidos no
   aparecen en el contexto y si aparece la sintesis. Los engramas siguen en el
   almacen y `memory.recall` los alcanza por consulta directa.
6. **Coste.** Para el mismo hilo, el contexto compuesto con sintesis no ocupa
   mas tokens que sin ella.
7. **Procedencia.** Una ventana con items de dos emisores produce una sintesis
   `unknown`; nunca `user` ni `model`.
8. **No promocion.** Tras `maintain`, ninguna sintesis aparece en `semantic`.
   Prueba explicita, porque es el limite que protege la memoria duradera.
9. **Ciclo de vida.** Cuando `maintain` archiva el `dialog` de una sesion,
   archiva tambien su sintesis.
10. **Claves en el esquema**, fijables por entorno, con sus defectos, y
    rechazando valores invalidos (ventana <= 0).
11. **Traza.** El evento declara ventana, items resumidos y modelo.
12. **Sin regresion.** Suite completa en verde CON PostgreSQL y sin skips.

## Lo que NO verifica este encargo

El criterio de salida de la fase -coherencia >= 8 de 9 contra una linea base de
2 de 15- se mide en el laboratorio con la puerta, por dos ejecutores, y NO forma
parte de esta entrega. Aqui se entrega el mecanismo; la fase se cierra con la
medida.

## Impacto de version

Un tipo de memoria nuevo que `memory_type.list` publica, tres claves de
configuracion nuevas y un `link_kind` nuevo: **adicion compatible, MINOR** en la
serie pre-1.0. Nada cambia con la fase apagada, que es su defecto.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x, banco incluido).
