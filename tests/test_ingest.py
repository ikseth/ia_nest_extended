import pytest

from ianest_extended import CoreClient, InvalidCoreDomainError
from ianest_extended.ingest import chunk_text, ingest_path


class CapturingRagStore:
    def ingest(self, **request):
        self.request = request
        return request


class DomainCatalog:
    def __init__(self):
        self.calls = 0

    def list_domains(self):
        self.calls += 1
        return ("general", "linux", "codigo")


def test_chunk_text_uses_overlap_without_empty_chunks():
    chunks = chunk_text(
        "uno dos tres cuatro cinco seis siete ocho nueve diez " * 10,
        chunk_tokens=20,
        overlap=0.15,
    )

    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_ingest_directory_uses_stable_relative_source_refs(
    tmp_path,
    local_service_stub,
):
    (tmp_path / "a.md").write_text("contenido a", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("contenido b", encoding="utf-8")
    (tmp_path / "ignored.json").write_text("{}", encoding="utf-8")
    store = CapturingRagStore()
    core = CoreClient(local_service_stub.base_url, timeout_seconds=2)

    result = ingest_path(
        store=store,
        core=core,
        path=tmp_path,
        corpus_name="manual",
        domains=("linux", "codigo", "linux"),
        source_ref="docs",
        chunk_tokens=300,
        overlap=0.15,
    )

    assert result["corpus_name"] == "manual"
    assert result["domains"] == ("linux", "codigo")
    assert [
        request
        for request in local_service_stub.requests
        if request[0] == "/domain/list"
    ] == [("/domain/list", None)]
    assert [chunk.source_ref for chunk in result["chunks"]] == [
        "docs/a.md",
        "docs/nested/b.txt",
    ]


def test_ingest_rejects_domain_outside_core_catalog(tmp_path):
    source = tmp_path / "manual.md"
    source.write_text("contenido", encoding="utf-8")

    with pytest.raises(InvalidCoreDomainError):
        ingest_path(
            store=CapturingRagStore(),
            core=DomainCatalog(),
            path=source,
            corpus_name="manual",
            domains=("cocina",),
            source_ref=None,
            chunk_tokens=300,
            overlap=0.15,
        )


def test_ingest_without_domain_skips_core_catalog(tmp_path):
    source = tmp_path / "manual.md"
    source.write_text("contenido", encoding="utf-8")
    core = DomainCatalog()

    result = ingest_path(
        store=CapturingRagStore(),
        core=core,
        path=source,
        corpus_name="manual-global",
        domains=(),
        source_ref=None,
        chunk_tokens=300,
        overlap=0.15,
    )

    assert result["domains"] == ()
    assert core.calls == 0
