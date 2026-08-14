"""Composition-root de la capa: construccion PEREZOSA y cacheada.

Cada dependencia (cliente del core, embedder, store de memoria, store RAG,
telemetria) se construye solo cuando la operacion invocada la necesita. Motivo
duro (fase 7a): `memory.maintain` debe poder ejecutarse con el core y Ollama
inalcanzables; un root avido rompe ese caso.

La migracion es EXPLICITA (ADR 0011, punto 6): el root VERIFICA el esquema y
falla con error tipado indicando el comando; nunca migra por su cuenta.
"""

from __future__ import annotations

from typing import Any

from .clients import CoreClient, OllamaEmbedder
from .config import ExtendedConfig
from .enrichment import MemoryEnricher
from .errors import (
    ExternalServiceConnectionError,
    RagUnavailableError,
    SchemaMigrationRequiredError,
)
from .ports import Embedder, MemoryStore, RagStore
from .telemetry import TelemetryWriter


class ExtendedComposition:
    """Factoria unica del servicio, compartida por todas las pieles."""

    def __init__(
        self,
        config: ExtendedConfig,
        *,
        core: CoreClient | None = None,
        embedder: Embedder | None = None,
        memory_store: MemoryStore | None = None,
        rag_store: RagStore | None = None,
        telemetry: TelemetryWriter | None = None,
    ) -> None:
        self._config = config
        self._core = core
        self._embedder = embedder
        self._memory_store = memory_store
        self._rag_store = rag_store
        self._telemetry = telemetry
        self._memory_verified = False
        self._rag_verified = False

    @property
    def config(self) -> ExtendedConfig:
        return self._config

    @property
    def core_constructed(self) -> bool:
        """Util para verificar la pereza sin tocar la red."""
        return self._core is not None

    def core(self) -> CoreClient:
        if self._core is None:
            self._core = CoreClient(
                self._config.core_url,
                connect_timeout_seconds=self._config.connect_timeout_seconds,
                inactivity_timeout_seconds=(
                    self._config.inactivity_timeout_seconds
                ),
            )
        return self._core

    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = OllamaEmbedder(
                self._config.ollama_url,
                self._config.embedding_model,
                self._config.embedding_dimension,
                self._config.connect_timeout_seconds,
                self._config.inactivity_timeout_seconds,
            )
        return self._embedder

    def telemetry(self) -> TelemetryWriter:
        if self._telemetry is None:
            self._telemetry = TelemetryWriter(self._config.telemetry_dir)
        return self._telemetry

    def memory_store(self, *, verify: bool = True) -> MemoryStore:
        if self._memory_store is None:
            from .adapters import PostgresMemoryStore

            self._memory_store = PostgresMemoryStore(
                self._config.database_dsn,
                self.embedder(),
            )
        if verify and not self._memory_verified:
            self._verify(self._memory_store, "memoria")
            self._memory_verified = True
        return self._memory_store

    def rag_store(self, *, verify: bool = True) -> RagStore:
        """Cablea el store RAG SIEMPRE que sea posible.

        Si se pide RAG y el sustrato no esta, el fallo es tipado; nunca un
        enriquecimiento vacio en silencio.
        """
        if self._rag_store is None:
            from .adapters import PostgresRagStore

            self._rag_store = PostgresRagStore(
                self._config.database_dsn,
                self.embedder(),
            )
        if verify and not self._rag_verified:
            try:
                self._rag_store.verify_schema()
            except SchemaMigrationRequiredError:
                raise
            except RagUnavailableError:
                raise
            except Exception as exc:
                raise RagUnavailableError(
                    f"el sustrato RAG no esta disponible: {exc}",
                    "use_rag",
                ) from exc
            self._rag_verified = True
        return self._rag_store

    def enricher(
        self,
        *,
        memory_store: MemoryStore,
        rag_store: RagStore | None,
    ) -> MemoryEnricher:
        return MemoryEnricher(
            store=memory_store,
            core=self.core(),
            telemetry=self.telemetry(),
            config=self._config,
            rag_store=rag_store,
        )

    def migrate(self) -> dict[str, Any]:
        """Unico camino que MUTA el esquema (comando `runtime migrate`)."""
        memory_store = self.memory_store(verify=False)
        memory_store.migrate()
        self._memory_verified = True
        rag_store = self.rag_store(verify=False)
        rag_store.migrate()
        self._rag_verified = True
        return {"memory_schema": "migrated", "rag_schema": "migrated"}

    @staticmethod
    def _verify(store, label: str) -> None:
        try:
            store.verify_schema()
        except SchemaMigrationRequiredError:
            raise
        except Exception as exc:
            raise ExternalServiceConnectionError(
                f"no se pudo verificar el esquema de {label}: {exc}",
                "database_dsn",
            ) from exc
