import math

import pytest

from ianest_extended import (
    CoreClient,
    InvalidEmbeddingDimensionError,
    MemoryIdentity,
    OllamaEmbedder,
)


def test_core_client_propagates_complete_identity(local_service_stub):
    identity = MemoryIdentity(
        user_id="u1",
        session_id="s1",
        service="test",
        domain_tag="linux.ops",
        namespace="facts",
    )
    client = CoreClient(local_service_stub.base_url, timeout_seconds=2)

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
        timeout_seconds=2,
    )

    vector = embedder.embed("hola")

    assert vector == pytest.approx((0.6, 0.8))
    assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1)
    _, payload = local_service_stub.requests[-1]
    assert payload == {"model": "test-embed", "input": "hola"}

    wrong = OllamaEmbedder(
        local_service_stub.base_url,
        "test-embed",
        3,
        timeout_seconds=2,
    )
    with pytest.raises(InvalidEmbeddingDimensionError):
        wrong.embed("hola")


def test_core_client_routes_domain(local_service_stub):
    client = CoreClient(local_service_stub.base_url, timeout_seconds=2)

    result = client.domain_route("administra linux", MemoryIdentity(user_id="u"))

    assert result.domain == "linux"
    assert result.confidence == 0.9
    path, payload = local_service_stub.requests[-1]
    assert path == "/domain/route"
    assert payload == {"prompt": "administra linux", "identity": {"user_id": "u"}}


def test_core_client_lists_domains_once_per_client(local_service_stub):
    client = CoreClient(local_service_stub.base_url, timeout_seconds=2)

    assert client.list_domains() == ("general", "linux")
    assert client.list_domains() == ("general", "linux")

    requests = [
        request
        for request in local_service_stub.requests
        if request[0] == "/domain/list"
    ]
    assert requests == [("/domain/list", None)]
