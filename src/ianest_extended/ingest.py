"""Ingesta curada de texto en corpus RAG (capacidad knowledge.ingest)."""

from __future__ import annotations

import math
import re
from bisect import bisect_left
from collections.abc import Iterator, Sequence
from pathlib import Path

from .clients import CoreClient
from .errors import InvalidCoreDomainError, InvalidRagInputError
from .models import RagChunkWrite, RagIngestResult
from .ports import RagStore

CHARS_PER_TOKEN = 3.5
SUPPORTED_SUFFIXES = {".md", ".txt"}
_PARAGRAPH_BOUNDARY = re.compile(r"(?:\r?\n[ \t]*){2,}")
_SENTENCE_BOUNDARY = re.compile(r"[.?!] ")


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
    overlap_boundaries = _overlap_boundaries(content)
    chunks: list[str] = []
    start = 0
    while start < len(content):
        while start < len(content) and content[start].isspace():
            start += 1
        if start >= len(content):
            break
        end = _chunk_end(content, start, chunk_chars)
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(content):
            break
        overlap_start = max(start + 1, end - overlap_chars)
        start = _overlap_boundary(
            overlap_boundaries,
            overlap_start,
            end,
        ) or end
    return tuple(chunks)


def _chunk_end(content: str, start: int, chunk_chars: int) -> int:
    end = min(len(content), start + chunk_chars)
    if end >= len(content):
        return end

    middle = start + (chunk_chars // 2)
    for lower, upper in ((middle, end), (start, middle)):
        for separator in ("\n", " "):
            boundary = content.rfind(separator, lower, upper)
            if boundary > start:
                return boundary
    return end


def _overlap_boundaries(content: str) -> tuple[tuple[int, ...], ...]:
    return (
        tuple(match.end() for match in _PARAGRAPH_BOUNDARY.finditer(content)),
        tuple(index + 1 for index in _separator_positions(content, "\n")),
        tuple(match.end() for match in _SENTENCE_BOUNDARY.finditer(content)),
        tuple(index + 1 for index in _separator_positions(content, " ")),
    )


def _overlap_boundary(
    boundaries: tuple[tuple[int, ...], ...],
    start: int,
    end: int,
) -> int | None:
    if start >= end:
        return None

    for positions in boundaries:
        index = bisect_left(positions, start)
        if index < len(positions) and positions[index] < end:
            return positions[index]
    return None


def _separator_positions(content: str, separator: str) -> Iterator[int]:
    position = content.find(separator)
    while position >= 0:
        yield position
        position = content.find(separator, position + 1)


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

