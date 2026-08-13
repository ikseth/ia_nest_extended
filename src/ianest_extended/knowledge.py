"""Workflow de operador para conocimiento por dominio."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from .adapters import PostgresRagStore
from .clients import CoreClient, OllamaEmbedder
from .config import ExtendedConfig
from .errors import CoreResponseError, InvalidCoreDomainError, InvalidRagInputError
from .models import KnowledgeDomainStatus, KnowledgeSuggestion, MemoryIdentity
from .ports import RagStore


def knowledge_status(
    *,
    store: RagStore,
    core: CoreClient,
) -> tuple[KnowledgeDomainStatus, ...]:
    domains = tuple(domain for domain in core.list_domains() if domain != "general")
    counts = store.confirmed_corpus_counts(domains)
    return tuple(
        KnowledgeDomainStatus(domain=domain, confirmed_corpora=counts[domain])
        for domain in domains
    )


def suggest_domains(
    *,
    store: RagStore,
    core: CoreClient,
    corpus_name: str,
    min_confidence: float,
    sample_chars: int,
) -> tuple[KnowledgeSuggestion, ...]:
    if not 0.0 <= min_confidence <= 1.0:
        raise InvalidRagInputError("min_confidence debe estar entre 0 y 1")
    sample = store.sample_corpus(corpus_name, sample_chars)
    route = core.domain_route(sample, MemoryIdentity(service="knowledge"))
    valid_domains = set(core.list_domains())
    if route.domain not in valid_domains:
        raise CoreResponseError(
            f"domain.route devolvio un dominio fuera del catalogo: '{route.domain}'"
        )

    candidates: dict[str, float] = {route.domain: route.confidence}
    for alternative in route.alternatives:
        parsed = _parse_alternative(alternative)
        if parsed is None:
            continue
        domain, confidence = parsed
        if domain not in valid_domains:
            continue
        candidates[domain] = max(confidence, candidates.get(domain, 0.0))

    suggestions: list[KnowledgeSuggestion] = []
    for domain, confidence in candidates.items():
        if domain == "general" or confidence < min_confidence:
            continue
        stored = store.propose_domain(corpus_name, domain, confidence)
        suggestions.append(
            KnowledgeSuggestion(
                domain=domain,
                confidence=confidence,
                stored=stored,
            )
        )
    return tuple(suggestions)


def confirm_domain(
    *,
    store: RagStore,
    core: CoreClient,
    corpus_name: str,
    domain: str,
) -> bool:
    value = _validate_core_domain(core, domain)
    return store.confirm_domain(corpus_name, value)


def reject_domain(
    *,
    store: RagStore,
    core: CoreClient,
    corpus_name: str,
    domain: str,
) -> bool:
    value = _validate_core_domain(core, domain)
    return store.reject_domain(corpus_name, value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ianest_extended.knowledge",
        description="Gestiona conocimiento por dominio bajo control del operador.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Muestra cobertura por dominio del core.")

    suggest = commands.add_parser("suggest", help="Propone dominios para un corpus.")
    suggest.add_argument("--corpus", required=True)

    for command in ("confirm", "reject"):
        link = commands.add_parser(command, help=f"{command} un vinculo de dominio.")
        link.add_argument("--corpus", required=True)
        link.add_argument("--domain", required=True)
    args = parser.parse_args(argv)

    config = ExtendedConfig.from_env()
    embedder = OllamaEmbedder(
        config.ollama_url,
        config.embedding_model,
        config.embedding_dimension,
        config.request_timeout_seconds,
    )
    store = PostgresRagStore(config.database_dsn, embedder)
    core = CoreClient(config.core_url, config.request_timeout_seconds)
    store.migrate()

    if args.command == "status":
        statuses = knowledge_status(store=store, core=core)
        for status in statuses:
            label = "OK" if status.confirmed_corpora else "HUECO"
            print(
                f"domain={status.domain} confirmed_corpora="
                f"{status.confirmed_corpora} status={label}"
            )
        return 0
    if args.command == "suggest":
        suggestions = suggest_domains(
            store=store,
            core=core,
            corpus_name=args.corpus,
            min_confidence=config.rag_suggest_min_confidence,
            sample_chars=config.rag_suggest_sample_chars,
        )
        if not suggestions:
            print(f"corpus={args.corpus} proposals=0")
        for item in suggestions:
            action = "stored" if item.stored else "protected"
            print(
                f"corpus={args.corpus} domain={item.domain} "
                f"confidence={item.confidence:.3f} proposal={action}"
            )
        return 0
    if args.command == "confirm":
        changed = confirm_domain(
            store=store,
            core=core,
            corpus_name=args.corpus,
            domain=args.domain,
        )
        print(
            f"corpus={args.corpus} domain={args.domain} "
            f"confirmed={'yes' if changed else 'already'}"
        )
        return 0

    removed = reject_domain(
        store=store,
        core=core,
        corpus_name=args.corpus,
        domain=args.domain,
    )
    print(
        f"corpus={args.corpus} domain={args.domain} "
        f"rejected={'yes' if removed else 'absent'}"
    )
    return 0


def _validate_core_domain(core: CoreClient, domain: str) -> str:
    value = domain.strip()
    valid = core.list_domains()
    if not value or value not in valid:
        catalog = ", ".join(valid) or "(ninguno)"
        raise InvalidCoreDomainError(
            f"dominio del core no valido '{value}'; dominios validos: {catalog}"
        )
    return value


def _parse_alternative(item: dict[str, Any]) -> tuple[str, float] | None:
    domain = item.get("domain", item.get("id"))
    confidence = item.get("confidence")
    if not isinstance(domain, str) or not domain.strip():
        return None
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0.0 <= float(confidence) <= 1.0
    ):
        return None
    return domain.strip(), float(confidence)


if __name__ == "__main__":
    raise SystemExit(main())
