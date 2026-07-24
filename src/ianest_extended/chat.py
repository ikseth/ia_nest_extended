"""CLI minima del vertical de memoria."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .adapters import PostgresMemoryStore
from .clients import CoreClient, OllamaEmbedder
from .config import ExtendedConfig
from .enrichment import MemoryEnricher
from .models import MemoryIdentity
from .telemetry import TelemetryWriter


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ianest_extended.chat",
        description="Ejecuta prompt.run con enriquecimiento de memoria.",
    )
    parser.add_argument("--user", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--domain")
    parser.add_argument("--show-context", action="store_true")
    parser.add_argument("prompt")
    args = parser.parse_args(argv)

    config = ExtendedConfig.from_env()
    embedder = OllamaEmbedder(
        config.ollama_url,
        config.embedding_model,
        config.embedding_dimension,
        config.request_timeout_seconds,
    )
    store = PostgresMemoryStore(config.database_dsn, embedder)
    store.migrate()
    enricher = MemoryEnricher(
        store=store,
        core=CoreClient(
            config.core_url,
            config.request_timeout_seconds,
        ),
        telemetry=TelemetryWriter(config.telemetry_dir),
        config=config,
    )
    result = enricher.enrich(
        MemoryIdentity(
            user_id=args.user,
            session_id=args.session,
            service="local_cli",
            domain_tag=args.domain,
        ),
        args.prompt,
    )
    if args.show_context:
        print(result.context or "(sin memoria recuperada)")
        print()
    print(result.response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
