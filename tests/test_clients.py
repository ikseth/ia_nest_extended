import math

import pytest

from ianest_extended import (
    CoreClient,
    CoreConnectionError,
    CoreTimeoutError,
    InvalidEmbeddingDimensionError,
    MemoryIdentity,
    OllamaEmbedder,
    write_catalog_cache,
)


def test_core_client_propagates_complete_identity(local_service_stub):
    identity = MemoryIdentity(
        user_id="u1",
        session_id="s1",
        service="test",
        domain_tag="linux.ops",
        namespace="facts",
    )
    client = CoreClient(local_service_stub.base_url, connect_timeout_seconds=2)

    result = client.prompt_run("hola", identity, model="extractor")

    _, payload = local_service_stub.requests[-1]
    assert payload == {
        "prompt": "hola",
        "identity": {
            "user_id": "u1",
            "service": "test",
            "session_id": "s1",
            "domain_tag": "linux.ops",
            "namespace": "facts",
        },
        "model": "extractor",
    }
    assert result.request_id == "core-1"
    assert result.finish_reason == "stop"


def test_ollama_embedder_normalizes_and_validates_dimension(
    local_service_stub,
):
    embedder = OllamaEmbedder(
        local_service_stub.base_url,
        "test-embed",
        2,
        connect_timeout_seconds=2,
    )

    vector = embedder.embed("hola")

    assert vector == pytest.approx((0.6, 0.8))
    assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1)
    _, payload = local_service_stub.requests[-1]
    assert payload == {"model": "test-embed", "input": ["hola"]}

    wrong = OllamaEmbedder(
        local_service_stub.base_url,
        "test-embed",
        3,
        connect_timeout_seconds=2,
    )
    with pytest.raises(InvalidEmbeddingDimensionError):
        wrong.embed("hola")


def test_core_client_routes_domain(local_service_stub):
    client = CoreClient(local_service_stub.base_url, connect_timeout_seconds=2)

    result = client.domain_route("administra linux", MemoryIdentity(user_id="u"))

    assert result.domain == "linux"
    assert result.confidence == 0.9
    path, payload = local_service_stub.requests[-1]
    assert path == "/domain/route"
    assert payload == {"prompt": "administra linux", "identity": {"user_id": "u"}}


def test_turn_context_only_when_declared_in_cached_catalog(
    local_service_stub, tmp_path
):
    cache = tmp_path / "catalog.json"
    client = CoreClient(
        local_service_stub.base_url,
        connect_timeout_seconds=2,
        catalog_cache_path=cache,
        trusted_providers=lambda: ("zeta", "casa_ha"),
    )
    write_catalog_cache(
        cache,
        core_url=local_service_stub.base_url,
        core_version="next",
        capabilities=[
            {"name": "prompt.run", "params": []},
            {"name": "prompt.stream", "params": [{"name": "turn_context"}]},
            {"name": "domain.route", "params": [{"name": "turn_context"}]},
        ],
    )

    client.prompt_run("hola", MemoryIdentity(user_id="u"))
    assert "turn_context" not in local_service_stub.requests[-1][1]

    stream = client.prompt_stream("hola", MemoryIdentity(user_id="u"))
    list(stream)
    stream_payload = next(
        payload for path, payload in reversed(local_service_stub.requests)
        if path == "/prompt/stream"
    )
    assert stream_payload["turn_context"] == {
        "trusted_providers": ["casa_ha", "zeta"]
    }

    client.domain_route("linux", MemoryIdentity(user_id="u"))
    assert local_service_stub.requests[-1][1]["turn_context"] == {
        "trusted_providers": ["casa_ha", "zeta"]
    }

    write_catalog_cache(
        cache,
        core_url=local_service_stub.base_url,
        core_version="next",
        capabilities=[
            {"name": "prompt.run", "params": [{"name": "turn_context"}]},
        ],
    )
    client.prompt_run("hola", MemoryIdentity(user_id="u"))
    assert local_service_stub.requests[-1][1]["turn_context"] == {
        "trusted_providers": ["casa_ha", "zeta"]
    }


def test_core_client_lists_domains_once_per_client(local_service_stub):
    client = CoreClient(local_service_stub.base_url, connect_timeout_seconds=2)

    assert client.list_domains() == ("general", "linux", "codigo")
    assert client.list_domains() == ("general", "linux", "codigo")

    requests = [
        request
        for request in local_service_stub.requests
        if request[0] == "/domain/list"
    ]
    assert requests == [("/domain/list", None)]


def test_task_run_uses_its_own_long_operation_timeout(local_service_stub):
    client = CoreClient(
        local_service_stub.base_url,
        connect_timeout_seconds=1,
        inactivity_timeout_seconds=0.05,
        task_timeout_seconds=0.5,
    )

    result = client.task_run("tarea lenta", MemoryIdentity(user_id="u"))

    assert result.response == "tarea lenta completada"


def test_prompt_run_keeps_the_short_inactivity_timeout(local_service_stub):
    client = CoreClient(
        local_service_stub.base_url,
        connect_timeout_seconds=1,
        inactivity_timeout_seconds=0.05,
        task_timeout_seconds=0.5,
    )

    with pytest.raises(CoreTimeoutError):
        client.prompt_run("slow-prompt", MemoryIdentity(user_id="u"))
