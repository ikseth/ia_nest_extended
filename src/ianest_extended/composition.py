"""Composition-root de la capa: construccion PEREZOSA y cacheada.

Cada dependencia (cliente del core, embedder, store de memoria, store RAG,
telemetria) se construye solo cuando la operacion invocada la necesita. Motivo
duro (fase 7a): `memory.maintain` debe poder ejecutarse con el core y Ollama
inalcanzables; un root avido rompe ese caso.

La migracion es EXPLICITA (ADR 0011, punto 6): el root VERIFICA el esquema y
falla con error tipado indicando el comando; nunca migra por su cuenta.
"""

from __future__ import annotations

from threading import Lock
from typing import Any

from .catalog_cache import (
    catalog_refresh_due,
    record_catalog_refresh_attempt,
    write_catalog_cache,
)
from .clients import CoreClient, OllamaEmbedder
from .config import ExtendedConfig
from .enrichment import MemoryEnricher
from .errors import (
    ExternalServiceConnectionError,
    RagUnavailableError,
    SchemaMigrationRequiredError,
)
from .ports import Embedder, MemoryStore, RagStore
from .knowledge_gate import KnowledgeGate
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
        knowledge_gate: KnowledgeGate | None = None,
    ) -> None:
        self._config = config
        self._core = core
        self._embedder = embedder
        self._memory_store = memory_store
        self._rag_store = rag_store
        self._telemetry = telemetry
        self._knowledge_gate = knowledge_gate
        self._memory_verified = False
        self._rag_verified = False
        self._catalog_refresh_lock = Lock()
        self._catalog_auto_refresh_enabled = False

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
                task_timeout_seconds=self._config.task_timeout_seconds,
                catalog_cache_path=self._config.catalog_cache_path,
                trusted_providers=lambda: self.memory_store().trusted_providers(
                    self._config.provider_ceiling
                ),
                ensure_catalog_fresh=self.refresh_core_catalog_if_due,
            )
        return self._core

    def refresh_core_catalog(self, *, force: bool = False) -> dict[str, Any] | None:
        """Consulta y escribe el catalogo del core en un unico camino.

        El error se propaga al llamador que pidio explicitamente
        ``capability.list``. Los refrescos automaticos lo degradan a ``None``
        despues de registrar el intento, para que un turno no falle ni golpee
        al core una vez por peticion.
        """
        with self._catalog_refresh_lock:
            if not force and not catalog_refresh_due(
                self._config.catalog_cache_path,
                core_url=self._config.core_url,
                ttl_seconds=self._config.core_catalog_ttl_seconds,
            ):
                return None
            try:
                downstream = self.core().list_capabilities()
            except Exception:
                record_catalog_refresh_attempt(
                    self._config.catalog_cache_path,
                    core_url=self._config.core_url,
                )
                if force:
                    raise
                return None
            write_catalog_cache(
                self._config.catalog_cache_path,
                core_url=self._config.core_url,
                core_version=downstream["core_version"],
                capabilities=downstream["capabilities"],
            )
            return downstream

    def refresh_core_catalog_if_due(self) -> None:
        """Mejor esfuerzo para el camino que necesita ``turn_context``."""
        if not self._catalog_auto_refresh_enabled:
            return
        self.refresh_core_catalog()

    def enable_catalog_auto_refresh(self) -> None:
        """Activa el refresco automatico para una piel de servicio."""
        self._catalog_auto_refresh_enabled = True

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

    def knowledge_gate(self) -> KnowledgeGate:
        if self._knowledge_gate is None:
            self._knowledge_gate = KnowledgeGate(
                embedder=self.embedder(),
                enabled=self._config.knowledge_gate_enabled,
                threshold=self._config.knowledge_gate_threshold,
                phrases_file=self._config.knowledge_gate_phrases_file,
            )
        return self._knowledge_gate

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
            knowledge_gate=self.knowledge_gate() if rag_store is not None else None,
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
