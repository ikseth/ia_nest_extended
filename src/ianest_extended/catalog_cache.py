"""Cache local del catalogo remoto: estado, no configuracion, no red.

Resuelve la tension entre dos cosas ciertas a la vez: el parser tiene que
conocer los parametros del core para ofrecer sus banderas, y construir el
parser no puede depender de la red (fase anterior, defecto 2 del retrabajo de
herencia de parametros).

La cache la ESCRIBE `capability.list` como efecto de consultar el core en
vivo -es su cometido-. El parser SOLO la lee. Una cache de un core distinto
del configurado no se usa: se declara de que origen es y, si no coincide, se
ignora y el CLI degrada como si la cache no existiera.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_catalog_cache(path: Path, *, core_url: str) -> dict[str, Any] | None:
    """Cache valida para `core_url`, o `None` para cualquier otro caso.

    Ausente, corrupta o de un origen distinto del configurado se tratan
    igual: no es un error, es "no hay cache", y quien llama degrada.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(document, dict):
        return None
    if document.get("core_url") != core_url:
        return None
    capabilities = document.get("capabilities")
    if not isinstance(capabilities, list):
        return None
    return document


def write_catalog_cache(
    path: Path,
    *,
    core_url: str,
    core_version: str | None,
    capabilities: list[dict[str, Any]],
) -> None:
    """Persiste la cache, declarando su origen.

    Mejor esfuerzo: no rompe `capability.list` si el estado local no se
    puede escribir (permisos, disco lleno); esa consulta ya obtuvo su
    respuesta del core y eso es lo que importa a quien la invoco.
    """
    document = {
        "core_url": core_url,
        "core_version": core_version,
        "capabilities": capabilities,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        return
