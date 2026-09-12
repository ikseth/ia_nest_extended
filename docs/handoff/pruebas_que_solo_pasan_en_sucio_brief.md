# Handoff: tres pruebas que solo pasan en un entorno sucio

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude (Opus), rol disenador.
Verificacion: Opus sobre el banco de laboratorio. NUNCA quien implementa.
Fecha: 2026-09-12.
Base: `main`, su ultimo commit.

Ante ambiguedad: PARA y pregunta. No rellenes huecos por inferencia.

## Contexto

Se ha montado una maquina de banco, limpia, con PostgreSQL local en contenedor.
Es la primera vez que la suite corre ENTERA, sin los 34 skips de siempre.
Resultado: **3 fallos, 244 pasadas**. Los tres son defectos de las PRUEBAS, no
del producto, y los tres eran invisibles en los entornos de desarrollo actuales.

Que fuera invisible tiene causa, y conviene tenerla presente al arreglar: el
venv del disenador declaraba `ianest-extended 0.0.0` mientras `pyproject.toml`
decia `0.2.2`. Un entorno con metadatos viejos hacia pasar una prueba que en
limpio falla.

## 1. La prueba de contradiccion escribe con el principal equivocado

`tests/test_postgres_store.py::test_contradiction_crosses_namespace_but_not_type_user_or_band`

    WriteAuthorityError: 'conscience' no puede escribir 'semantic'

El caso "otro tipo no se anota" escribe un candidato en `semantic` con
`Principal.CONSCIENCE`, y la autoridad de escritura de `semantic` es
`extended` (ADR 0002).

**Que se pide.** Conservar la INTENCION de la prueba -que un candidato de otro
tipo no reciba la anotacion- escribiendo con el principal que ese tipo admite.
No relajes la autoridad ni cambies el roster para que la prueba pase: la
autoridad es la que esta bien y la prueba la que estaba mal.

Es una prueba nueva que se entrego sin ejecutar, con el skip por delante. No se
reprocha; se corrige y se aprende: **ahora hay banco y se puede ejecutar**.

## 2. La prueba del catalogo fija la version en el texto

`tests/test_capability_catalog.py::test_fusion_passes_unknown_core_capability_and_preserves_it`

    assert result["extended_version"] == "0.0.0"   ->   AssertionError: '0.2.2' == '0.0.0'

La capa publica su version leyendola de los metadatos del paquete instalado. La
prueba la compara contra un literal, asi que solo pasa donde esos metadatos
estan desactualizados.

**Que se pide.** Que compare contra la MISMA fuente que usa la capa
(`importlib.metadata.version("ianest-extended")`), de modo que la prueba
verifique la FONTANERIA -que el catalogo publica la version instalada- y no el
estado del entorno. Si la version no se puede resolver, la prueba debe fallar
diciendolo, no aceptar cualquier cosa.

Nota de fondo, por si ayuda a no repetirlo: esto es la misma familia de problema
que `extended CR-0003`, la identidad del artefacto servido. Una prueba que fija
la version en el texto es una que miente sobre que codigo esta corriendo.

## 3. La prueba del wheel construye con el interprete del sistema

`tests/test_installed_migrations.py::test_wheel_install_contains_reachable_migrations`

    build_python = Path(sys.base_prefix) / "bin" / "python3.13"
    ...
    BackendUnavailable: Cannot import 'setuptools.build_meta'

En una maquina limpia el python del sistema existe pero no trae `setuptools`,
asi que `pip wheel --no-build-isolation` no puede construir.

**Que se pide.** Construir con un interprete que SI pueda: `sys.executable` -el
del venv, que tiene setuptools- o el del sistema solo si `setuptools` es
importable ahi. El resto de la prueba no cambia: sigue instalando el wheel en un
directorio aparte y comprobando que las migraciones se alcanzan desde el paquete
instalado, que es lo que de verdad protege.

## Fuera de este encargo (NO implementar)

- Tocar el producto. Los tres son defectos de prueba.
- Relajar autoridades, roster o umbrales para que algo pase.
- Tocar el core, el instalador, el laboratorio o el banco.

## Criterios de aceptacion (falsables)

1. **Contradiccion.** La prueba pasa contra PostgreSQL y sigue comprobando las
   cuatro cosas: cruza namespace, y NO cruza tipo, usuario ni banda.
2. **Catalogo.** La prueba pasa con la version instalada sea cual sea, y falla
   si el catalogo publicara una version distinta de la del paquete.
3. **Wheel.** La prueba pasa en un entorno cuyo python de sistema no tiene
   `setuptools`.
4. **Sin regresion.** Suite completa en verde.

## Como se verifica

En el banco, con PostgreSQL local y **sin skips**. Tu no puedes ejecutarlo:
declara como NO EJECUTADO lo que dependa de PostgreSQL y dilo en tu informe, sin
adornarlo. Lo ejecuta el verificador.

## Impacto de version

Ninguno: solo pruebas.

## Entrega

Deja el trabajo en el ARBOL DE TRABAJO, sobre la rama activa. **No cambies de
rama, no crees rama, no commitees, no hagas push.**

**No entres al laboratorio** (ninguna direccion 192.168.x.x), banco incluido.
