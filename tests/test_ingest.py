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


def _chunk_spans(text, chunks):
    content = text.strip()
    spans = []
    search_from = 0
    for chunk in chunks:
        position = content.find(chunk, search_from)
        if position < 0:
            position = content.find(chunk)
        assert position >= 0
        spans.append((position, position + len(chunk)))
        search_from = position + 1
    return content, spans


@pytest.mark.parametrize(
    "text",
    (
        "\n\n".join(
            f"Parrafo {index}. Primera idea {index}. Segunda idea {index}."
            for index in range(12)
        ),
        " ".join(f"palabra{index:02d}" for index in range(50)),
    ),
)
def test_chunk_text_never_splits_normal_words_and_covers_input(text):
    chunks = chunk_text(text, chunk_tokens=20, overlap=0.5)
    content, spans = _chunk_spans(text, chunks)
    covered = [False] * len(content)

    assert len(chunks) > 1
    assert all(chunks)
    assert all(len(chunk) <= 70 for chunk in chunks)
    for start, end in spans:
        assert start == 0 or content[start - 1].isspace()
        assert end == len(content) or content[end].isspace()
        covered[start:end] = [True] * (end - start)
    assert all(
        is_covered
        for char, is_covered in zip(content, covered)
        if not char.isspace()
    )


def test_chunk_text_aligns_overlap_to_natural_boundaries():
    text = "\n\n".join(
        f"Parrafo {index}. Primera idea numero {index}. Segunda idea numero {index}."
        for index in range(8)
    )

    chunks = chunk_text(text, chunk_tokens=20, overlap=0.5)

    assert len(chunks) > 1
    assert all(
        chunk.startswith(("Parrafo ", "Primera idea ", "Segunda idea "))
        for chunk in chunks[1:]
    )


def test_chunk_text_prefers_paragraph_boundary_inside_overlap():
    text = (
        "Inicio uno. Frase dos.\n\n"
        "Parrafo preferido contiene muchas palabras para continuar con mas "
        "texto hasta terminar."
    )

    chunks = chunk_text(text, chunk_tokens=20, overlap=0.8)

    assert chunks[1].startswith("Parrafo preferido")


def test_chunk_text_without_overlap_boundary_continues_at_previous_end():
    giant = "x" * 65
    chunks = chunk_text(
        f"prefijo {giant} final",
        chunk_tokens=20,
        overlap=0.5,
    )

    assert chunks == ("prefijo", giant, "final")


def test_chunk_text_splits_only_a_word_larger_than_the_window_and_terminates():
    chunks = chunk_text("x" * 180, chunk_tokens=20, overlap=0.9)

    assert chunks == ("x" * 70, "x" * 70, "x" * 40)


def test_chunk_text_does_not_split_a_word_equal_to_the_window():
    word = "x" * 70

    chunks = chunk_text(f"prefijo {word} final", chunk_tokens=20, overlap=0.5)

    assert chunks == ("prefijo", word, "final")


def test_chunk_text_is_deterministic():
    text = " ".join(f"termino{index}" for index in range(40))

    first = chunk_text(text, chunk_tokens=20, overlap=0.15)
    second = chunk_text(text, chunk_tokens=20, overlap=0.15)

    assert second == first


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
    core = CoreClient(local_service_stub.base_url, connect_timeout_seconds=2)

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
