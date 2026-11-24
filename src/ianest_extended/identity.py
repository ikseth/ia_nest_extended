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
from .errors import EnrichmentParameterError, ExtendedConfigError, ExtendedRequestError
from .models import MemoryIdentity


def remembered_session_id(path: Path) -> str:
    """Devuelve la sesion recordada; la crea y persiste la primera vez."""
    try:
        if path.is_file():
            stored = path.read_text(encoding="utf-8").strip()
            if stored:
                return stored
    except OSError as exc:
        raise ExtendedConfigError(
            f"no se pudo leer el estado de sesion: {exc}",
            "session_state_path",
        ) from exc
    return replace_remembered_session_id(path)


def replace_remembered_session_id(path: Path) -> str:
    """Genera una sesion nueva y sustituye el estado recordado por la CLI."""
    session_id = str(uuid4())
    remember_session_id(path, session_id)
    return session_id


def remember_session_id(path: Path, session_id: str) -> None:
    """Sustituye el estado recordado por una sesion ya declarada."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{session_id}\n", encoding="utf-8")
    except OSError as exc:
        raise ExtendedConfigError(
            f"no se pudo persistir el estado de sesion: {exc}",
            "session_state_path",
        ) from exc


def resolve_identity(
    config: ExtendedConfig,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    service: str | None = None,
    namespace: str | None = None,
    domain: str | None = None,
    interlocutor_profile: str | None = None,
    audience: str | None = None,
    frame_facts: object = None,
    remember_session: bool = True,
) -> MemoryIdentity:
    resolved_session = session_id
    if resolved_session is None and remember_session:
        resolved_session = config.cli_session_id
    if resolved_session is None and remember_session:
        resolved_session = remembered_session_id(config.session_state_path)
    incoming_profile = _value(interlocutor_profile, None)
    return MemoryIdentity(
        user_id=_value(user_id, config.default_user_id),
        session_id=resolved_session,
        service=_value(service, config.default_service),
        domain_tag=_value(domain, None),
        namespace=_value(namespace, config.default_namespace),
        interlocutor_profile=normalize_interlocutor_profile(incoming_profile),
        audience=normalize_audience(audience, incoming_profile),
        frame_facts=normalize_frame_facts(frame_facts),
    )


def _value(explicit: str | None, default: str | None) -> str | None:
    value = explicit if explicit is not None else default
    if value is None:
        return None
    value = value.strip()
    return value or None


def normalize_interlocutor_profile(value: str | None) -> str | None:
    """Normaliza el dato de procedencia que el core acepta para el interlocutor."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise EnrichmentParameterError(
            "interlocutor_profile debe ser texto", "interlocutor_profile"
        )
    normalized = value.strip()
    if not normalized:
        return None
    if normalized not in ("adult", "restricted", "child"):
        raise EnrichmentParameterError(
            "interlocutor_profile debe ser 'adult', 'restricted' o 'child'",
            "interlocutor_profile",
        )
    return "restricted" if normalized == "child" else normalized


def normalize_audience(value: str | None, incoming_profile: str | None) -> str | None:
    """Valida el tono y conserva la compatibilidad del perfil antiguo."""
    if value is None:
        return {
            "child": "child",
            "restricted": "general",
            "adult": "adult",
        }.get(incoming_profile)
    if not isinstance(value, str):
        raise EnrichmentParameterError("audience debe ser texto", "audience")
    normalized = value.strip()
    if normalized not in {"adult", "general", "child"}:
        raise EnrichmentParameterError(
            "audience debe ser 'adult', 'general' o 'child'", "audience"
        )
    return normalized


def normalize_frame_facts(
    value: object,
) -> dict[str, dict[str, str | None]] | None:
    """Valida la forma exacta afirmada por edge ADR 0004."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"account", "person", "device"}:
        raise ExtendedRequestError(
            "identity.frame_facts debe contener account, person y device",
            "identity.frame_facts",
        )
    allowed_origins = {
        "account": {"authenticated"},
        "person": {"validated", "absent"},
        "device": {"asserted", "absent"},
    }
    normalized: dict[str, dict[str, str | None]] = {}
    for part in ("account", "person", "device"):
        fact = value[part]
        field = f"identity.frame_facts.{part}"
        if not isinstance(fact, dict) or set(fact) != {"value", "origin"}:
            raise ExtendedRequestError(
                f"{field} debe contener value y origin", field
            )
        fact_value = fact["value"]
        origin = fact["origin"]
        if fact_value is not None and not isinstance(fact_value, str):
            raise ExtendedRequestError(f"{field}.value debe ser texto o null", field)
        if isinstance(fact_value, str) and not fact_value:
            raise ExtendedRequestError(f"{field}.value no puede estar vacio", field)
        if origin not in allowed_origins[part]:
            raise ExtendedRequestError(f"{field}.origin no es valido", field)
        if (origin == "absent") != (fact_value is None):
            raise ExtendedRequestError(
                f"{field} debe usar absent solo con value null", field
            )
        normalized[part] = {"value": fact_value, "origin": origin}
    return normalized
