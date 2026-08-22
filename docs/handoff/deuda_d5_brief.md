# Handoff de implementacion: deuda D5, dos regimenes para el suelo del RAG

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-21 (reescrito el 2026-08-21 tras medir; sustituye a la version
anterior de ese mismo dia, cuyo argumento la medida desmintio).
Base: `main`, su ultimo commit, con `v0.1.0` publicada y las fases 7 y 8 cerradas.

Estado de contrato: la deuda esta declarada y MEDIDA en `docs/PLAN.md`, D5. La
evidencia completa esta en `local/lab/2026-08-21_bateria_2x2_suelo_rag.md` (no
versionada). El usuario reconcilio este diseno el 2026-08-21.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PLAN.md`, deudas D1, D4 y D5.
3. `docs/VERSIONADO.md`: el esquema de configuracion `IANEST_EXTENDED_*` es
   CONTRATO PUBLICO, y esta capa ya tiene version publicada. Importa como se
   introduce una clave.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## El problema, medido

D1 puso un suelo unico de similitud al RAG. Medido el 2026-08-21 sobre el corpus
del laboratorio (19 corpus, 57 chunks, embebedor `bge-m3`), con sondas escritas
como preguntas de persona y no como ecos del texto del corpus, en las cuatro
combinaciones de relevancia y dominio:

    A  relevante CON dominio     0.327 - 0.783   n=17
    B  relevante SIN dominio     0.430 - 0.783   n=17
    C  ruido     SIN dominio     0.357 - 0.458   n=8
    D  ruido     CON dominio     0.310 - 0.402   n=8
    X  cruzado   CON dominio     0.248 - 0.370   n=5

Las bandas SE SOLAPAN. No existe un valor unico correcto: subirlo silencia
consultas legitimas, bajarlo admite ruido. Con el `0.47` que corre el laboratorio
se pierden cuatro de diecisiete consultas legitimas.

## La causa, y de ahi el diseno

**El gate de dominio deprime la puntuacion, y eso es mecanico.** Recuperar con
dominio busca en un SUBCONJUNTO de lo que se busca sin dominio, asi que para la
misma sonda la similitud con dominio es siempre menor o igual que sin dominio.
Verificado sonda a sonda el 2026-08-21: ni un caso en contra. `codigo` puntua
0.327 con dominio y 0.477 sin el; `educacion` 0.392 contra 0.431; `matematicas`
0.411 contra 0.430.

De ahi el diseno: **un umbral global castiga precisamente a las consultas CON
dominio**, que son las que mas confianza merecen, porque el gate les ha quitado
de la baraja el mejor resultado global. Por eso el suelo con dominio debe poder
ser mas bajo que el suelo sin dominio. No es una intuicion sobre "lo que queda ya
es del tema": es la aritmetica del filtro.

**Lo que este diseno NO hace, y conviene saberlo antes de implementarlo:** no
separa las bandas. El solape sobrevive en los dos regimenes y es peor en el laxo
(margen -0.075) que en el estricto (-0.028). Dos regimenes permiten elegir dos
puntos de operacion mejores que uno solo; no convierten el problema en separable.

**Y una parte del solape no es del umbral.** Los tres aciertos mas bajos con
dominio son `codigo` 0.327, `educacion` 0.392 y `matematicas` 0.411, y los tres
son corpus de uno o pocos chunks que no contienen la respuesta. Quitandolos, la
banda de acierto con dominio arranca en 0.464. Ningun suelo arregla un corpus que
no tiene la respuesta: ahi devolver cero es lo correcto. Eso es deuda de CORPUS,
no de umbral, y no se toca en esta tarea.

## Lo que se pide

Dos umbrales configurables en vez de uno, elegidos por si la recuperacion lleva
dominio efectivo o no.

**Las claves, literales, para que no las inventes:**

    rag_min_score              IANEST_EXTENDED_RAG_MIN_SCORE              (ya existe)
    rag_min_score_domain       IANEST_EXTENDED_RAG_MIN_SCORE_DOMAIN       (nueva)
    rag_min_score_no_domain    IANEST_EXTENDED_RAG_MIN_SCORE_NO_DOMAIN    (nueva)

**Como se resuelven, y esto es contrato:** la clave vigente `rag_min_score` NO se
retira ni se renombra. Sigue siendo la BASE. Las dos nuevas son `float | None` y
su defecto es `None`. La resolucion es:

    suelo del regimen = clave especifica si esta declarada, si no la base

Con las dos sin declarar, ambos regimenes usan la base y el comportamiento es
identico al de hoy, bit a bit. El cambio es adicion compatible, no rotura.

**El defecto de la base NO cambia.** Sigue en `0.50`. Esto es deliberado y va
contra la tentacion obvia, asi que aqui esta el motivo: los valores medidos salen
de UN corpus y UN embebedor, con n=17 relevantes. No son portables a otro
despliegue. Meterlos como defectos del codigo seria vender como universal una
medida local. Los valores medidos son configuracion recomendada, no constante.

**Valores medidos, con su coste, para el CHANGELOG y la documentacion.** Son
PROVISIONALES y de este corpus:

    sin dominio (estricto)   0.46   por encima de todo el ruido medido (max 0.458)
                                    pierde 2/17: matematicas 0.430, educacion 0.431
                                    margen sobre el ruido: 0.002

    con dominio (laxo)       0.41   por encima del ruido con dominio (max 0.402)
                                    y de todo cruzado (max 0.370)
                                    pierde 2/17: codigo 0.327, educacion 0.392

**No inventes precision y no maquilles el coste.** No hay punto limpio; cualquier
valor pierde algo. El margen del estricto son dos milesimas: escribelo tal cual,
no lo presentes como un umbral holgado.

Al laxo lo ata el CRUZADO -pregunta legitima de otro tema forzada a un dominio,
que llega a 0.370- mas que la cortesia. La cortesia con dominio es poco danina,
porque devuelve material del tema que el propio usuario pidio.

**Dato que acota el riesgo del suelo laxo:** medido el 2026-08-21, las seis
sondas de cortesia rutean a `general` con confianza 0.95, y `general` deja el
dominio a `None`. Cero de seis alcanzan el regimen laxo por auto-ruteo. Al laxo
solo llega el ruido si quien pregunta DECLARA un dominio a mano. n=6 y el router
es un modelo: acota el riesgo, no lo elimina.

## Tres precisiones sobre el codigo, para no dejarlas a inferencia

Verificadas sobre `main` el 2026-08-21.

**1. Que decide el regimen.** El dominio EFECTIVO que se le pasa al almacen, no
lo que haya escrito quien llama. Si el auto-ruteo asigno dominio, esa recuperacion
es "con dominio", porque el gate ya ha recortado los candidatos y la puntuacion ya
esta deprimida por esa causa. Sin dominio efectivo, regimen estricto. Ojo con dos
casos que `_resolve_domain` ya resuelve y que NO debes cambiar: un `domain_tag`
igual a `general` se convierte en `None` (luego, estricto), y un auto-ruteo por
debajo de la confianza minima deja el dominio en `None` (luego, estricto).

**2. Hay DOS sitios que aplican el suelo, no uno.** `rag_min_score` se lee en
`enrichment.py` (la recuperacion del enriquecimiento) y otra vez en `service.py`
(la vista previa de recuerdo, que llama al almacen por su cuenta). Los dos
cambian, con la misma regla. Si solo cambia uno, los dos caminos discrepan y el
criterio 1 se cumple en falso.

**3. La telemetria ya lleva `domain` en sus detalles**, asi que el regimen es
DERIVABLE hoy. No basta: el criterio 6 pide que el evento diga el regimen y el
suelo aplicado en claro. Derivarlo obliga a quien calibre a reconstruir la regla
desde fuera, y la regla puede cambiar.

## Fuera de esta tarea (NO implementar)

- Cambiar el defecto de `rag_min_score`. Se queda en `0.50`.
- Poner los valores medidos como defectos del codigo. Van a documentacion.
- Arreglar los corpus flacos (`codigo`, `educacion`, `matematicas`). Es deuda de
  corpus y se trabaja en laboratorio.
- Tocar el suelo de la memoria (D4). Es otro sustrato y otra calibracion.
- Umbral por dominio concreto, o umbral relativo al mejor resultado. Son las
  alternativas si esta no basta; hoy no se eligen.
- Tocar el ranking, el presupuesto de composicion o el gate de dominio.
- Tocar el core o el laboratorio.

## Criterios de aceptacion (falsables)

1. **Dos regimenes.** Con la misma puntuacion controlada, un fragmento pasa el
   suelo cuando la recuperacion lleva dominio y no lo pasa cuando no lo lleva.
   Prueba automatizada con puntuaciones controladas, NO con un embebedor real: un
   embebedor de hash da similitudes practicamente aleatorias y no sirve para
   probar umbrales.
2. **Compatibilidad.** Una configuracion que solo declare `rag_min_score` se
   comporta EXACTAMENTE como hoy: los dos regimenes caen a esa base. Y una que no
   declare nada tambien, porque el defecto de la base no cambia.
3. **Precedencia.** Declarada una clave especifica, gana sobre la base en su
   regimen y no afecta al otro.
4. **Las claves estan en el esquema** con el resto, se fijan por entorno y su
   ausencia cae a la base.
5. **Cero resultados sigue siendo valido**, no un error, en los dos regimenes.
6. **Telemetria.** El evento de recuperacion dice EN CLARO que regimen se aplico y
   con que suelo, sin obligar a derivarlo de otros campos. Sin eso, la
   calibracion futura es a ciegas.
7. **Los dos caminos coinciden.** El del enriquecimiento y el de la vista previa
   aplican el mismo suelo ante la misma entrada. Verificable sin laboratorio.
8. **Sin regresion.** La suite en verde con PostgreSQL, y dos ejecuciones seguidas
   con el mismo resultado.

## Impacto de version

Adicion compatible: dos claves nuevas que caen a la base cuando no se declaran,
ningun defecto cambiado y ningun comportamiento distinto sin configurarlas. En la
serie pre-1.0 sube PATCH.

Ojo: si se implementara de modo que una configuracion existente -o una vacia-
cambiara de comportamiento sola, dejaria de ser adicion compatible. El criterio 2
esta para impedirlo.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

Marca D5 como cerrada en `docs/PLAN.md` sin borrar su diagnostico, dejando dicho
que la CALIBRACION sigue pendiente y por que. Actualiza `CHANGELOG.md` con los
valores medidos, su procedencia y su coste.

No entres al laboratorio (ninguna direccion 192.168.x.x). La medida ya esta hecha
y esta en este documento: no hace falta que la repitas ni que la compruebes.

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
