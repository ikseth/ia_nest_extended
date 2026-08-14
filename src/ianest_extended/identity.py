"""Identidad del request: defaults de configuracion y sesion recordada.

ADR 0011, punto 7: la identidad deja de ser obligatoria. `user_id`, `service`,
`namespace` y `session_id` toman defaults de configuracion; si no se indica
`session_id`, se GENERA UNO Y SE RECUERDA en un fichero local (contexto local,
no versionado, de ruta configurable). Un aleatorio por invocacion romperia la
continuidad del tier `dialog`.

ADR 0011, punto 8: `--domain` es un unico valor -gate de conocimiento, dominio
de ruteo y faceta de lectura-, divergencia deliberada respecto al core.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .config import ExtendedConfig
from .errors import ExtendedConfigError
from .models import MemoryIdentity


def remembered_session_id(path: Path) -> str:
    """Devuelve la sesion recordada; la crea y persiste la primera vez."""
    try:
        if path.is_file():
            stored = path.read_text(encoding="ascii").strip()
            if stored:
                return stored
    except OSError as exc:
        raise ExtendedConfigError(
            f"no se pudo leer el estado de sesion: {exc}",
            "session_state_path",
        ) from exc
    session_id = str(uuid4())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{session_id}\n", encoding="ascii")
    except OSError as exc:
        raise ExtendedConfigError(
            f"no se pudo persistir el estado de sesion: {exc}",
            "session_state_path",
        ) from exc
    return session_id


def resolve_identity(
    config: ExtendedConfig,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    service: str | None = None,
    namespace: str | None = None,
    domain: str | None = None,
    remember_session: bool = True,
) -> MemoryIdentity:
    resolved_session = session_id
    if resolved_session is None and remember_session:
        resolved_session = remembered_session_id(config.session_state_path)
    return MemoryIdentity(
        user_id=_value(user_id, config.default_user_id),
        session_id=resolved_session,
        service=_value(service, config.default_service),
        domain_tag=_value(domain, None),
        namespace=_value(namespace, config.default_namespace),
    )


def _value(explicit: str | None, default: str | None) -> str | None:
    value = explicit if explicit is not None else default
    if value is None:
        return None
    value = value.strip()
    return value or None
