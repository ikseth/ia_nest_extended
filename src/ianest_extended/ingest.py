"""Ingesta curada de texto en corpus RAG (capacidad knowledge.ingest)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

from .clients import CoreClient
from .errors import InvalidCoreDomainError, InvalidRagInputError
from .models import RagChunkWrite, RagIngestResult
from .ports import RagStore

CHARS_PER_TOKEN = 3.5
SUPPORTED_SUFFIXES = {".md", ".txt"}


def chunk_text(
    text: str,
    *,
    chunk_tokens: int,
    overlap: float,
) -> tuple[str, ...]:
    if chunk_tokens <= 0:
        raise InvalidRagInputError("chunk_tokens debe ser mayor que cero")
    if not 0.0 <= overlap < 1.0:
        raise InvalidRagInputError("overlap debe estar entre 0 y 1")
    content = text.strip()
    if not content:
        return ()
    chunk_chars = max(1, math.floor(chunk_tokens * CHARS_PER_TOKEN))
    overlap_chars = math.floor(chunk_chars * overlap)
    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(len(content), start + chunk_chars)
        if end < len(content):
            boundary = content.rfind("\n", start + (chunk_chars // 2), end)
            if boundary <= start:
                boundary = content.rfind(" ", start + (chunk_chars // 2), end)
            if boundary > start:
                end = boundary
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(content):
            break
        next_start = max(start + 1, end - overlap_chars)
        start = next_start
    return tuple(chunks)


def ingest_path(
    *,
    store: RagStore,
    core: CoreClient,
    path: Path,
    corpus_name: str,
    domains: Sequence[str],
    source_ref: str | None,
    chunk_tokens: int,
    overlap: float,
) -> RagIngestResult:
    validated_domains = _validate_domains(core, domains)
    files = _source_files(path)
    chunks: list[RagChunkWrite] = []
    for source in files:
        reference = _source_reference(path, source, source_ref)
        for ordinal, content in enumerate(
            chunk_text(
                source.read_text(encoding="utf-8"),
                chunk_tokens=chunk_tokens,
                overlap=overlap,
            )
        ):
            chunks.append(
                RagChunkWrite(
                    content=content,
                    source_ref=reference,
                    ordinal=ordinal,
                )
            )
    return store.ingest(
        corpus_name=corpus_name,
        domains=validated_domains,
        chunks=chunks,
    )


def _source_files(path: Path) -> tuple[Path, ...]:
    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise InvalidRagInputError("el fichero debe ser .txt o .md")
        return (path,)
    if path.is_dir():
        files = tuple(
            candidate
            for candidate in sorted(path.rglob("*"))
            if candidate.is_file()
            and candidate.suffix.lower() in SUPPORTED_SUFFIXES
        )
        if not files:
            raise InvalidRagInputError("el directorio no contiene .txt ni .md")
        return files
    raise InvalidRagInputError(f"la ruta no existe: {path}")


def _source_reference(root: Path, source: Path, requested: str | None) -> str:
    if root.is_file():
        return requested or root.name
    relative = source.relative_to(root).as_posix()
    return f"{requested.rstrip('/')}/{relative}" if requested else relative


def _validate_domains(
    core: CoreClient,
    requested: Sequence[str],
) -> tuple[str, ...]:
    domains: list[str] = []
    for domain in requested:
        value = domain.strip()
        if not value:
            raise InvalidRagInputError("domain no puede estar vacio")
        if value not in domains:
            domains.append(value)
    if not domains:
        return ()
    valid_domains = core.list_domains()
    for domain in domains:
        if domain not in valid_domains:
            valid = ", ".join(valid_domains) or "(ninguno)"
            raise InvalidCoreDomainError(
                f"dominio del core no valido '{domain}'; "
                f"dominios validos: {valid}"
            )
    return tuple(domains)

