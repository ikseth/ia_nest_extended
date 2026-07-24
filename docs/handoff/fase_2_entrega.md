# Entrega de implementacion: fase 2

Fecha: 2026-07-24
Rama indicada por el usuario: `fase-2-memoria-registro`
Impacto de version: ninguno; no hay contrato publico cortado.

## Decisiones tomadas

- El paquete usa layout `src`, Python 3.13 y PEP 621. La version inicial de
  empaquetado queda en `0.0.0`; no se ha cortado ni cambiado una version
  publica.
- `MemoryStore` y `Embedder` son protocols. `PostgresMemoryStore` es el
  adaptador de referencia y `FakeEmbedder` produce un vector determinista,
  normalizado y de dimension configurable.
- La migracion `0001_memory_registry.sql` usa el marcador
  `{{embedding_dimension}}`. El adaptador exige una dimension positiva,
  sustituye solo ese entero y despues carga el roster semilla de forma
  idempotente.
- La derivacion de clave vive en una sola funcion, `derive_memory_key`, usada
  tanto por escritura como por lectura. Para scope `user`, el `session_id`
  recibido no entra en la clave; para scope `session`, se exigen `user_id` y
  `session_id`.
- La autoridad se comprueba antes de escribir engramas, versionar perfiles o
  archivar. `entities` usa `write_entity` y la tabla de perfiles; los otros
  tipos delegados usan el mismo contrato de engramas que los estrictos.
- Para `half_life_seconds = NULL`, la senal de recencia vale 1: no hay
  decaimiento. El resto de la formula coincide con el brief.
- `always_inject` no aplica `top_k`: devuelve todos los registros activos que
  pasan scope y gates. `top_k` limita solo el modo `ranked`.
- Como el roster no declara namespace para todos los delegados, se usaron
  `principles` y `safety` como namespaces homonimos. `entities` conserva
  `entities` como namespace declarativo aunque sus perfiles viven en su tabla.
- Los tests solo aceptan un DSN con host loopback. Sin DSN o sin postgres local
  se saltan con aviso y nunca intentan un host remoto.

## Dudas abiertas

- Falta reconciliar los namespaces oficiales de `principles`, `safety` y
  `entities`. Los valores usados son una decision de implementacion reversible.
- El modelo real de embeddings y la dimension de produccion siguen pendientes
  de fase 3. La prueba local usa dimension 16 por defecto.
- La ruta postgres no pudo ejecutarse en este sandbox porque no hay Docker ni
  `IANEST_EXTENDED_TEST_DSN`. Debe verificarse con
  `docker-compose.dev.yml` antes de integrar.

## Inconsistencias o tensiones detectadas

- `docs/FORMA_ENRIQUECIMIENTO.md` dice que `user_id` forma parte de la clave
  siempre, mientras `docs/ROSTER_MEMORIA.md` y el brief dan scope `global` a
  `identity` y `principles`. La implementacion sigue el roster reconciliado:
  esos dos tipos tienen clave global sin `user_id`. No se corrigio ningun doc.
- El esquema del brief dice que `namespace` solo puede ser null para `dialog`,
  pero el roster delegado solo explicita `persona` para `identity`; no asigna
  namespaces a `principles`, `safety` ni `entities`. Se aplico la decision
  reversible descrita arriba sin modificar el roster.
- A4 pide ordenar "el mismo conjunto de engramas" con `dialog` y `semantic`,
  pero esos tipos tienen scopes y namespaces incompatibles y una fila solo
  puede pertenecer a un tipo. La prueba aplica ambos vectores al mismo conjunto
  abstracto de senales de candidatos, que comprueba la diferencia de orden sin
  duplicar una fila entre tipos. No se corrigio el criterio.

## Estado de pytest

Comando:

    .venv/bin/python -m pytest

Resultado final:

    10 passed, 6 skipped in 0.08s

Los seis skips son tests de `PostgresMemoryStore` y muestran:

    IANEST_EXTENDED_TEST_DSN no definido; tests postgres omitidos

Tambien se ejecuto:

    .venv/bin/python -m compileall -q src tests
    .venv/bin/python -m pip check

La compilacion termino sin error y `pip check` indico que no hay dependencias
rotas.

## Entrada anadida a CHANGELOG bajo No publicado

Se anadio bajo `### Anadido`:

    - Sustrato de memoria de la Fase 2: paquete Python con ports `MemoryStore` y
      `Embedder`, registro y validacion V1-V4 con errores tipados, autoridad de
      escritura por principal, `FakeEmbedder`, adaptador postgres+pgvector,
      migracion parametrizada, semillas del roster, recuperacion multi-espacio,
      archivo sin borrado, entorno postgres local y pruebas A1-A5. Sin contrato
      publico cortado; impacto de version: ninguno.
