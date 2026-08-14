"""Workflow de conocimiento por dominio (capacidades knowledge.*)."""

from __future__ import annotations

from typing import Any

from .clients import CoreClient
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

