import json
from datetime import UTC, datetime
from uuid import uuid4

from ianest_extended import (
    CoreClient,
    EngramWrite,
    ExtendedConfig,
    MemoryEnricher,
    Principal,
    RagChunk,
    TelemetryWriter,
)
from ianest_extended.enrichment import (
    _ContextLine,
    _compose_context,
    compose_prompt,
)

from .fakes import InMemoryStore, identity


class InMemoryRagStore:
    def __init__(self, chunks):
        self.chunks = tuple(chunks)
        self.domains = []

    def retrieve(self, query_text, *, domain=None, top_k=3):
        self.domains.append(domain)
        selected = [
            chunk
            for chunk in self.chunks
            if domain is None or chunk.domain == domain
        ]
        return tuple(selected[:top_k])


def _chunk(content, *, domain="linux", score=0.9):
    return RagChunk(
        id=uuid4(),
        corpus_id=uuid4(),
        corpus_name=f"manual-{domain}",
        domain=domain,
        content=content,
        source_ref="guide.md",
        ordinal=0,
        score=score,
        created_at=datetime.now(UTC),
    )


def _enricher(tmp_path, local_service_stub, memory_store, rag_store, **changes):
    config = ExtendedConfig(
        telemetry_dir=tmp_path,
        embedding_dimension=2,
        **changes,
    )
    return MemoryEnricher(
        store=memory_store,
        rag_store=rag_store,
        core=CoreClient(local_service_stub.base_url, timeout_seconds=2),
        telemetry=TelemetryWriter(tmp_path),
        config=config,
    )


def test_budget_drops_rag_before_episodic_and_preserves_required_text():
    lines = [
        _ContextLine("delegated", "identity " + ("i" * 80), 1.0, True),
        _ContextLine("rag", "rag " + ("r" * 180), 0.1),
        _ContextLine("episodic", "episodic " + ("e" * 60), 0.1),
    ]

    context = _compose_context(lines, token_budget=70, rag_token_budget=500)
    prompt = compose_prompt(context, "USER PROMPT MUST STAY")

    assert "## rag" not in context
    assert "## delegated" in context
    assert "## episodic" in context
    assert prompt.endswith("USER PROMPT MUST STAY")


def test_upfront_rag_is_injected_only_for_matching_domain(
    tmp_path,
    local_service_stub,
):
    memory_store = InMemoryStore()
    rag_store = InMemoryRagStore([_chunk("use systemctl restart")])
    enricher = _enricher(
        tmp_path,
        local_service_stub,
        memory_store,
        rag_store,
    )

    linux_identity = identity().__class__(
        user_id="u",
        session_id="A",
        service="test",
        domain_tag="linux",
    )
    found = enricher.enrich(linux_identity, "smalltalk")
    missing = enricher.enrich(
        identity().__class__(
            user_id="u",
            session_id="B",
            service="test",
            domain_tag="cocina",
        ),
        "smalltalk",
    )

    assert "## rag" in found.context
    assert "use systemctl restart" in found.context
    assert "## rag" not in missing.context
    prompt_requests = [
        payload
        for path, payload in local_service_stub.requests
        if path == "/prompt/run" and "model" not in payload
    ]
    assert prompt_requests[0]["domain"] == "linux"
    assert "## rag" not in missing.context


def test_auto_route_uses_confident_domain_and_falls_back_to_global(
    tmp_path,
    local_service_stub,
):
    memory_store = InMemoryStore()
    memory_store.write(
        Principal.CONSCIENCE,
        EngramWrite(
            type_name="identity",
            content="delegated identity",
            namespace="persona",
        ),
    )
    rag_store = InMemoryRagStore(
        [_chunk("linux reference"), _chunk("cocina reference", domain="cocina")]
    )
    enricher = _enricher(
        tmp_path,
        local_service_stub,
        memory_store,
        rag_store,
        rag_auto_domain=True,
        rag_auto_domain_min_confidence=0.7,
    )
    no_domain = identity().__class__(user_id="u", session_id="A", service="test")

    confident = enricher.enrich(no_domain, "route this")
    low = enricher.enrich(no_domain, "low-route")

    assert rag_store.domains == ["linux", None]
    assert "linux reference" in confident.context
    assert "delegated identity" in low.context
    events = []
    for path in tmp_path.glob("extended-*.jsonl"):
        events.extend(json.loads(line) for line in path.read_text().splitlines())
    rag_events = [event for event in events if event["event"] == "rag.retrieve"]
    assert rag_events[0]["domain"] == "linux"
    assert rag_events[0]["auto_route_confidence"] == 0.9
    assert rag_events[1]["domain"] is None
    assert rag_events[1]["auto_route_confidence"] == 0.2
