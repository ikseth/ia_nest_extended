# Handoff de implementacion: los subcomandos heredan sus parametros del catalogo

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus, con reconciliacion del usuario. NUNCA quien implementa.
Fecha: 2026-08-19
Base: `main`, su ultimo commit.

Estado de contrato: reconciliado. Continua `extended ADR 0012`, ya implementado:
el catalogo fusionado existe y de el sale la ayuda. Falta que salgan tambien los
PARAMETROS.

## Lectura obligatoria

1. `AGENTS.md` y su orden de lectura.
2. `docs/decision_records/0012-capacidades-reflexivas.md`.
3. `docs/handoff/catalogo_fusionado_brief.md`: lo ya entregado, sobre lo que se
   construye.
4. `core docs/CORE_CONTRACT.md`, seccion `capability.list`: que publica por
   capacidad. NO se copia; se referencia.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## El problema, medido

Una capacidad reenviada solo se puede invocar con banderas genericas:

    hoy      ianest-extended task plan --param effort=high
    objetivo ianest-extended task plan --effort high

El catalogo ya trae lo necesario -nombre, tipo, obligatoriedad, valores
admitidos, defecto y metavar de cada parametro, y las entradas de CLI que
rellenan varios parametros a la vez-. Hoy no se usa: la piel exige
`--param CLAVE=VALOR`, sin validacion, sin ayuda y sin defectos.

## Dentro de esta tarea

### 1. Parametros declarados, banderas reales

Para cada capacidad del catalogo fusionado que se exponga en CLI, sus parametros
se convierten en banderas propias, con su tipo, sus valores admitidos, su defecto
y su texto de ayuda. Vale igual para las propias, las sobreescritas y las
reenviadas: el mecanismo es UNO, derivado del dato, sin ramas por capacidad.

Un valor fuera de los admitidos se rechaza en la piel con error tipado, sin
llegar al core.

### 2. Entradas de CLI que rellenan varios parametros

El catalogo declara entradas que rellenan varios parametros a la vez -el fichero
de plan del core rellena `plan`, `requirements` y `effort`-. Se implementan como
lo que son: una bandera que lee un fichero JSON y reparte su contenido entre los
parametros declarados.

Consecuencia util y buscada: `task run --plan-file` pasa a existir tambien aqui,
de modo que un operador puede ejecutar un plan que edito a mano.

**Precedencia, y es contrato**: si una entrada de fichero y una bandera explicita
rellenan el mismo parametro, es error tipado, no precedencia silenciosa. Es la
misma regla que ya gobierna las banderas de enriquecimiento
(`docs/PLAN.md`, fase 7a).

### 3. `--param` sobrevive, como escape

Se conserva para lo que el catalogo no declare -una capacidad de un core mas
nuevo que el catalogo que se obtuvo, o un parametro anadido en caliente-. Deja de
ser la via normal y pasa a ser la valvula.

Un `--param` que pise un parametro ya declarado como bandera es error tipado.

## Fuera de esta tarea (NO implementar)

- **Render de lo reenviado.** No es implementable con lo que el catalogo publica
  hoy; se ha pedido por `extended CR-0004`. Lo reenviado sigue saliendo en JSON, y
  el contrato debe decirlo.
- **`--verbose` y `--quiet` de `task run`.** No son parametros de la capacidad:
  son opciones de como el CLI del core pinta un flujo de eventos que por REST no
  existe -`/task/run` devuelve un JSON unico y el flujo vive en `task.stream`, que
  no acepta plan suministrado-. No inventes un equivalente.
- REST y MCP (fase 7c), aunque el mismo catalogo las alimentara.
- Cambiar el comportamiento de ninguna capacidad: esto mueve la PIEL.
- Tocar el core o el laboratorio.

## Criterios de aceptacion (falsables)

1. **Parametro declarado, bandera real.** Contra un stub cuyo catalogo declare un
   parametro con valores admitidos, la piel ofrece la bandera y RECHAZA un valor
   fuera de la lista sin llamar al core.
2. **Defectos.** Un parametro con defecto declarado no obliga a escribirlo, y lo
   que llega al core es el valor por defecto declarado.
3. **Tipos.** Un parametro entero declarado llega como numero en el cuerpo, no
   como texto.
4. **Sin codigo por capacidad.** Una capacidad desconocida que el stub declare con
   parametros obtiene sus banderas SIN tocar codigo de la capa. Es el invariante.
5. **Entrada de fichero.** Una entrada declarada que rellena varios parametros los
   rellena todos desde un solo fichero JSON.
6. **Colision.** Fichero y bandera explicita sobre el mismo parametro: error
   tipado, no precedencia.
7. **`--param` como escape.** Sigue funcionando para lo no declarado, y colisionar
   con una bandera declarada es error tipado.
8. **Sin catalogo tampoco se rompe.** Con el core inalcanzable, las capacidades
   propias conservan sus banderas -salen del catalogo local- y un `GRUPO ACCION`
   desconocido se sigue resolviendo con `--param`.
9. **Sin regresion.** La suite sigue en verde mas las pruebas nuevas.

## Entrega

Deja el trabajo STAGED sobre `main`, con `git add` por ruta explicita. **No crees
rama, no commitees, no hagas push.**

Actualiza `docs/EXTENDED_CONTRACT.md` -declarando que la presentacion de lo
reenviado es JSON mientras `CR-0004` no se resuelva- y `CHANGELOG.md` bajo
`[No publicado]`.

No entres al laboratorio (ninguna direccion 192.168.x.x).

## Regla que manda sobre las demas

Ante ambiguedad, PARA y pregunta. No rellenes huecos por inferencia.
