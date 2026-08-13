from types import SimpleNamespace
from uuid import uuid4

import pytest

from ianest_extended import ProtectedKnowledgeLinkError, RagChunkWrite
from ianest_extended.knowledge import (
    confirm_domain,
    knowledge_status,
    reject_domain,
    suggest_domains,
)


class StubCore:
    def __init__(self, domains, route=None):
        self._domains = tuple(domains)
        self._route = route

    def list_domains(self):
        return self._domains

    def domain_route(self, prompt, identity):
        assert prompt
        assert identity.service == "knowledge"
        return self._route


def _write(content):
    return (RagChunkWrite(content=content, source_ref="source.md", ordinal=0),)


def test_phase5c_status_reports_only_real_domain_gaps(postgres_rag_store):
    marker = uuid4().hex
    covered = f"covered_{marker}"
    gap = f"gap_{marker}"
    postgres_rag_store.ingest(
        corpus_name=f"status-{marker}",
        domains=[covered],
        chunks=_write(f"status content {marker}"),
    )

    result = knowledge_status(
        store=postgres_rag_store,
        core=StubCore(("general", covered, gap)),
    )

    assert [(item.domain, item.confirmed_corpora) for item in result] == [
        (covered, 1),
        (gap, 0),
    ]


def test_phase5c_suggest_is_idempotent_and_does_not_overwrite_manual(
    postgres_rag_store,
):
    marker = uuid4().hex
    selected = f"selected_{marker}"
    alternative = f"alternative_{marker}"
    below = f"below_{marker}"
    manual = f"manual_{marker}"
    corpus = f"suggest-{marker}"
    result = postgres_rag_store.ingest(
        corpus_name=corpus,
        domains=[manual],
        chunks=_write(f"sample knowledge {marker}"),
    )
    core = StubCore(
        ("general", selected, alternative, below, manual),
        SimpleNamespace(
            domain=selected,
            confidence=0.9,
            alternatives=(
                {"domain": alternative, "confidence": 0.7},
                {"domain": below, "confidence": 0.59},
                {"domain": manual, "confidence": 0.99},
            ),
        ),
    )

    first = suggest_domains(
        store=postgres_rag_store,
        core=core,
        corpus_name=corpus,
        min_confidence=0.6,
        sample_chars=2000,
    )
    second = suggest_domains(
        store=postgres_rag_store,
        core=core,
        corpus_name=corpus,
        min_confidence=0.6,
        sample_chars=2000,
    )

    assert [(item.domain, item.stored) for item in first] == [
        (selected, True),
        (alternative, True),
        (manual, False),
    ]
    assert [(item.domain, item.stored) for item in second] == [
        (selected, True),
        (alternative, True),
        (manual, False),
    ]
    with postgres_rag_store._connect() as connection:
        rows = connection.execute(
            """
            SELECT domain, source, confidence, confirmed
            FROM rag_corpus_domains
            WHERE corpus_id = %s
            ORDER BY domain
            """,
            (result.corpus_id,),
        ).fetchall()
    links = {
        row["domain"]: (row["source"], row["confidence"], row["confirmed"])
        for row in rows
    }
    assert links[selected] == ("auto", 0.9, False)
    assert links[alternative] == ("auto", 0.7, False)
    assert below not in links
    assert links[manual] == ("manual", None, True)


def test_phase5c_confirm_enables_existing_retrieval_gate(postgres_rag_store):
    marker = uuid4().hex
    domain = f"confirm_{marker}"
    corpus = f"confirm-{marker}"
    content = f"confirmed gated content {marker}"
    postgres_rag_store.ingest(corpus_name=corpus, domains=[], chunks=_write(content))
    postgres_rag_store.propose_domain(corpus, domain, 0.88)
    core = StubCore(("general", domain))

    assert not any(
        item.content == content
        for item in postgres_rag_store.retrieve(content, domain=domain, top_k=1000)
    )
    assert confirm_domain(
        store=postgres_rag_store,
        core=core,
        corpus_name=corpus,
        domain=domain,
    )
    assert not confirm_domain(
        store=postgres_rag_store,
        core=core,
        corpus_name=corpus,
        domain=domain,
    )
    assert any(
        item.content == content
        for item in postgres_rag_store.retrieve(content, domain=domain, top_k=1000)
    )


def test_phase5c_reject_only_removes_unconfirmed_auto(postgres_rag_store):
    marker = uuid4().hex
    auto = f"auto_{marker}"
    manual = f"manual_{marker}"
    corpus = f"reject-{marker}"
    postgres_rag_store.ingest(
        corpus_name=corpus,
        domains=[manual],
        chunks=_write(f"reject content {marker}"),
    )
    postgres_rag_store.propose_domain(corpus, auto, 0.75)
    core = StubCore(("general", auto, manual))

    assert reject_domain(
        store=postgres_rag_store,
        core=core,
        corpus_name=corpus,
        domain=auto,
    )
    assert not reject_domain(
        store=postgres_rag_store,
        core=core,
        corpus_name=corpus,
        domain=auto,
    )
    with pytest.raises(ProtectedKnowledgeLinkError):
        reject_domain(
            store=postgres_rag_store,
            core=core,
            corpus_name=corpus,
            domain=manual,
        )
