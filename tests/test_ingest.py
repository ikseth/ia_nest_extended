from ianest_extended.ingest import chunk_text, ingest_path


class CapturingRagStore:
    def ingest(self, **request):
        self.request = request
        return request


def test_chunk_text_uses_overlap_without_empty_chunks():
    chunks = chunk_text(
        "uno dos tres cuatro cinco seis siete ocho nueve diez " * 10,
        chunk_tokens=20,
        overlap=0.15,
    )

    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_ingest_directory_uses_stable_relative_source_refs(tmp_path):
    (tmp_path / "a.md").write_text("contenido a", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("contenido b", encoding="utf-8")
    (tmp_path / "ignored.json").write_text("{}", encoding="utf-8")
    store = CapturingRagStore()

    result = ingest_path(
        store=store,
        path=tmp_path,
        corpus_name="manual",
        domain="linux",
        source_ref="docs",
        chunk_tokens=300,
        overlap=0.15,
    )

    assert result["corpus_name"] == "manual"
    assert [chunk.source_ref for chunk in result["chunks"]] == [
        "docs/a.md",
        "docs/nested/b.txt",
    ]
