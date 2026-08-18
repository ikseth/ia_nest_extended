# Handoff de implementacion: deudas D1 y D2 del PLAN

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-18
Base: `main`, su ultimo commit (`18164bd`).

Estado de contrato: reconciliado. Las dos deudas estan declaradas en
`docs/PLAN.md`, seccion "Deuda de diseno declarada". D2 estaba marcada como
"propuesta a reconciliar" y el usuario la reconcilio el 2026-08-18 en los terminos
de abajo.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/PLAN.md`, seccion "Deuda de diseno declarada", puntos D1 y D2.
3. `docs/FORMA_ENRIQUECIMIENTO.md`, decision 2 (composicion y presupuesto, regla
   anti-colision de dominios). Es la regla que D2 matiza.
4. `docs/decision_records/0003-modelo-de-relevancia-y-gradiente-de-tiers.md`.

No hace falta releer el resto del corpus doctrinal.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## D1: suelo de similitud en la recuperacion RAG

Hoy la recuperacion devuelve `rag_top_k` chunks SIEMPRE, por poco que se parezcan
al prompt: hay top-k y presupuesto de tokens, pero ningun umbral minimo. Sintoma
registrado en el PLAN: a un "que recuerdas de mi" sin dominio se le inyectaron
primeros auxilios y critica literaria.

**Que se pide.** Un suelo de similitud configurable, aplicado en la recuperacion:
un chunk por debajo del umbral no se devuelve, aunque quede sitio en el top-k y en
el presupuesto. Clave nueva y aditiva, con el prefijo y el estilo de las
existentes (`config.py`).

**Valor por defecto: 0.38.** No es una estimacion; sale de medir en laboratorio el
2026-08-18 contra el corpus de dos dominios, con el embebedor y la metrica que la
capa ya usa:

0.38 cae en el hueco entre la banda del ruido y la de los aciertos: elimina todo
el ruido observado y conserva los relevantes. Las puntuaciones concretas son dato
de laboratorio y no se versionan.

**Declara la limitacion en el codigo o en el CHANGELOG, no la esconda:** el margen
entre las dos bandas es estrecho y la calibracion se hizo con un corpus pequeno. Es un punto de partida afinable en laboratorio
(`docs/POLITICA_WRITEBACK.md`: el lab es el banco de finetuning de estos numeros),
no una constante. Ante la duda, el sesgo correcto es CONSERVADOR: es peor
silenciar un chunk relevante que admitir uno mediocre.

Cero chunks recuperados es un resultado VALIDO y no un error: significa que no hay
conocimiento pertinente. No lo conviertas en excepcion ni en aviso ruidoso; que se
vea en la telemetria, que ya lleva `k_requested` y `k_returned`.

## D2: una memoria sin dominio es neutra, no incompatible

Hoy, con `--domain`, el filtro se aplica tambien a los tiers experienciales
(`semantic`, `episodic`, `dialog`), de modo que una memoria SIN `domain_tag` queda
fuera. Efecto observado: preguntando con dominio, el ente "olvida" lo que sabe de
su interlocutor.

La regla anti-colision de `docs/FORMA_ENRIQUECIMIENTO.md` esta pensada para
dominios INCOMPATIBLES. Un dominio ausente no es incompatible: es neutro.

**Reconciliado por el usuario, y esto es la semantica exacta a implementar:** una
memoria sin `domain_tag` es SIEMPRE candidata; el filtro excluye unicamente las de
un dominio DISTINTO del pedido.

    pedido=linux   memoria linux        -> candidata
    pedido=linux   memoria sin dominio  -> candidata   (hoy NO lo es: es el fallo)
    pedido=linux   memoria matematicas  -> excluida
    sin pedido     cualquiera           -> candidata   (comportamiento actual, no cambia)

El filtro vigente esta en las consultas de recuperacion del adaptador de
PostgreSQL, con la forma `AND (%s::text IS NULL OR e.domain_tag = %s)`
(`src/ianest_extended/adapters/postgres.py`, dos apariciones). Cambia la
SEMANTICA, no solo esa linea: revisa que no quede otro camino de recuperacion con
el filtro estricto.

Los tipos delegados (`identity`, `principles`, `safety`) ya se inyectan de forma
incondicional y NO estan afectados: no los toques.

D2 no cambia el ranking. Una memoria sin dominio compite por relevancia como
cualquier otra; lo que cambia es que entra en la competicion.

## Fuera de este encargo (NO implementar)

- D3 del PLAN (la identidad como fuente conmutable).
- `capability.list` sobreescrita, catalogo fusionado, REST, MCP, tag.
- Tocar el write-back, la consolidacion, el presupuesto por subtarea de la fase 7b
  o el modelo de timeout.
- Tocar el core o el laboratorio.

## Criterios de aceptacion (falsables)

1. **Suelo activo.** Con el umbral por defecto, una consulta cuyo mejor chunk
   puntua por debajo devuelve CERO chunks, aunque `rag_top_k` sea mayor. Prueba
   automatizada con puntuaciones controladas, no con un embebedor real.
2. **Suelo configurable.** La clave aparece en el esquema de configuracion con el
   resto, se fija por entorno, y su ausencia toma el default.
3. **Suelo no rompe lo bueno.** Un chunk por encima del umbral sigue devolviendose
   con el mismo orden de relevancia que hoy.
4. **Cero chunks no es error.** El camino de enriquecimiento con cero chunks
   recuperados completa y emite telemetria con `k_returned` a cero.
5. **D2, los tres casos.** Prueba automatizada que cubre la tabla de arriba:
   memoria del dominio pedido incluida, memoria sin dominio incluida, memoria de
   otro dominio excluida.
6. **D2 no afecta a los delegados.** Los tipos delegados se siguen inyectando con
   dominio pedido y sin el.
7. **Sin regresion.** La suite sigue en verde (84 passed, 26 skipped sin DSN de
   PostgreSQL) mas las pruebas nuevas. Las pruebas de PostgreSQL que cubran D2
   deben ir con las existentes y omitirse igual sin DSN.

## Entrega

Deja el trabajo STAGED sobre `main`, con `git add` por ruta explicita. **No crees
rama, no commitees, no hagas push.**

Anade a `CHANGELOG.md` bajo `[No publicado]` lo corregido, declarando el impacto
de version, y marca D1 y D2 como cerradas en `docs/PLAN.md` sin borrar el
historial de su diagnostico.

No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
