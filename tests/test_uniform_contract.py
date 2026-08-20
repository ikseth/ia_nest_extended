"""Criterios 1-3 y 12: reenvio generico, opacidad, streaming y error ajeno."""

import threading

import pytest

from ianest_extended import (
    DownstreamError,
    EnrichmentParameterError,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
)


def _service(tmp_path, local_service_stub, **changes):
    config = ExtendedConfig(
        core_url=local_service_stub.base_url,
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        embedding_dimension=2,
        connect_timeout_seconds=5,
        inactivity_timeout_seconds=5,
        **changes,
    )
    return ExtendedService(ExtendedComposition(config))


def test_unknown_capability_is_reachable_without_touching_layer_code(
    tmp_path,
    local_service_stub,
):
    """Criterio 1: conformidad con meta ADR 0007."""
    service = _service(tmp_path, local_service_stub)

    result = service.forward("capability.nueva", {"algo": "valor"})

    path, payload = local_service_stub.requests[-1]
    assert path == "/capability/nueva"
    assert payload == {"algo": "valor"}
    assert result.payload["eco"] == {"algo": "valor"}


def test_forwarded_response_reaches_caller_intact(tmp_path, local_service_stub):
    """Criterio 2: reenvio opaco, sin validar ni reescribir."""
    service = _service(tmp_path, local_service_stub)

    result = service.forward("capability.nueva", {"algo": 1})

    assert result.payload == {
        "eco": {"algo": 1},
        "campo_desconocido": ["a", "b"],
        "anidado": {"otro_campo": 42},
    }


def test_forwarded_get_capability_is_opaque(tmp_path, local_service_stub):
    service = _service(tmp_path, local_service_stub)

    result = service.forward("runtime.health")

    assert result.payload == {
        "status": "ok",
        "campo_desconocido": {"anidado": [1, 2, 3]},
    }


def test_stream_is_retransmitted_event_by_event(tmp_path, local_service_stub):
    """Criterio 3: no se acumula el flujo ni se convierte a JSON."""
    gate = threading.Event()
    local_service_stub.stream_gate = gate
    service = _service(tmp_path, local_service_stub)

    # `prompt.stream` dejo de reenviarse: ahora esta sobreescrita y enriquecida.
    # La propiedad que esta prueba defiende -que el REENVIO generico retransmite
    # sin acumular- se comprueba sobre una capacidad que sigue reenviada.
    stream = service.forward("flujo.nuevo", {"prompt": "hola"})
    events = iter(stream)
    first = next(events)
    second = next(events)

    # Los dos primeros eventos llegaron con el ultimo aun sin emitir.
    assert (first.event, first.data) == ("token", '{"chunk": "uno"}')
    assert (second.event, second.data) == ("token", '{"chunk": "dos"}')
    gate.set()
    third = next(events)
    assert (third.event, third.data) == ("done", '{"stop_reason": "stop"}')
    with pytest.raises(StopIteration):
        next(events)
    stream.close()


def test_core_error_is_propagated_without_rewrapping(
    tmp_path,
    local_service_stub,
):
    """Criterio 12a: el error ajeno, con origin declarado, llega intacto."""
    service = _service(tmp_path, local_service_stub)

    with pytest.raises(DownstreamError) as exc_info:
        service.forward("eval.run", {"suite": "no-existe"})

    error = exc_info.value
    assert error.type == "ConfigError"
    assert error.origin == "ia_nest_core"
    assert error.field == "suite"
    assert error.request_id == "core-error-1"
    assert error.to_dict() == {
        "type": "ConfigError",
        "message": "suite desconocida",
        "field": "suite",
        "origin": "ia_nest_core",
        "request_id": "core-error-1",
    }


def test_absent_origin_is_completed_with_the_layer_called(
    tmp_path,
    local_service_stub,
):
    """Criterio 12: `origin` ausente se COMPLETA (meta ADR 0009, punto 2)."""
    service = _service(tmp_path, local_service_stub)

    with pytest.raises(DownstreamError) as exc_info:
        service.forward("config.validate", {"config": "core.yaml"})

    error = exc_info.value
    assert error.origin == "ia_nest_core"
    assert error.to_dict() == {
        "type": "ConfigValidationError",
        "message": "modelo declarado inexistente",
        "field": "models",
        "origin": "ia_nest_core",
    }


def test_declared_origin_is_never_overwritten():
    """Completar es rellenar un hueco; sobrescribir seria falsificar."""
    declarado = DownstreamError(
        {
            "type": "AdapterError",
            "message": "fallo de una capa mas profunda",
            "field": None,
            "origin": "otra_capa",
        },
        "ia_nest_core",
    )
    ausente = DownstreamError(
        {"type": "AdapterError", "message": "fallo sin procedencia"},
        "ia_nest_core",
    )
    sin_vecino = DownstreamError(
        {"type": "AdapterError", "message": "fallo sin procedencia"}
    )

    assert declarado.origin == "otra_capa"
    assert declarado.to_dict()["origin"] == "otra_capa"
    assert ausente.origin == "ia_nest_core"
    assert ausente.type == "AdapterError"
    assert ausente.message == "fallo sin procedencia"
    assert sin_vecino.origin is None


def test_own_failure_carries_this_layer_origin(tmp_path, local_service_stub):
    """Criterio 12b: un fallo propio lleva el origin de esta capa."""
    service = _service(tmp_path, local_service_stub)

    with pytest.raises(EnrichmentParameterError) as exc_info:
        service.plan_enrichment(
            enrich=False,
            use_memory=None,
            use_rag=True,
            write_back=None,
            domain=None,
            auto_domain=None,
            model=None,
        )

    error = exc_info.value
    assert error.to_dict() == {
        "type": "EnrichmentParameterError",
        "message": "enriquecimiento desactivado junto a 'use_rag' activado",
        "field": "use_rag",
        "origin": "ia_nest_extended",
        "request_id": None,
    }


def test_overridden_and_own_capabilities_are_not_forwarded(
    tmp_path,
    local_service_stub,
):
    service = _service(tmp_path, local_service_stub)

    with pytest.raises(Exception):
        service.forward("prompt.run", {"prompt": "hola"})
    with pytest.raises(Exception):
        service.forward("memory.recall", {"prompt": "hola"})
