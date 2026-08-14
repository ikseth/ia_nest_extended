"""Errores tipados de la capa.

La FORMA (campos y propagacion entre saltos) la fija el ente en
`ia_nest_meta/docs/FORMA_DE_ERRORES_Y_TRAZA.md` (meta ADR 0009). El CATALOGO de
tipos es de esta capa y vive aqui.
"""

from __future__ import annotations

from typing import Any

ORIGIN = "ia_nest_extended"


class ExtendedError(Exception):
    """Base de todos los errores propios de la capa."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        *,
        origin: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.field = field
        self.origin = ORIGIN if origin is None else origin
        self.request_id = request_id

    @property
    def type(self) -> str:
        return type(self).__name__

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "message": self.message,
            "field": self.field,
            "origin": self.origin,
            "request_id": self.request_id,
        }


class DownstreamError(ExtendedError):
    """Error originado por una capa inferior.

    NO se re-envuelve ni se traduce (meta ADR 0009, punto 2): esta clase es solo
    el transporte en proceso del error ajeno. `to_dict()` devuelve el payload
    recibido tal cual, sin anadir ni quitar campos.
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = dict(payload)
        super().__init__(
            str(payload.get("message", "")),
            payload.get("field"),
            request_id=payload.get("request_id"),
        )
        self.origin = payload.get("origin")

    @property
    def type(self) -> str:
        declared = self._payload.get("type")
        return str(declared) if declared else "DownstreamError"

    def to_dict(self) -> dict[str, Any]:
        return dict(self._payload)


class MemoryError(ExtendedError):
    """Base de los errores de memoria."""


class MemoryTypeValidationError(MemoryError):
    """Base de los errores de declaracion."""


class InvalidMemoryTypeError(MemoryTypeValidationError):
    """La declaracion de tipo no es internamente coherente."""


class AliasedDeclarationError(MemoryTypeValidationError):
    """Dos declaraciones coinciden en todos sus ejes."""


class AliasedTierError(MemoryTypeValidationError):
    """Dos tiers ranked tienen el mismo comportamiento."""


class UnknownMemoryTypeError(MemoryError):
    """El tipo solicitado no existe en el registro."""


class InvalidNamespaceError(MemoryError):
    """El namespace no pertenece al tipo de memoria."""


class ScopeViolationError(MemoryError):
    """La identidad no satisface el scope del tipo."""


class WriteAuthorityError(MemoryError):
    """El principal no posee la capacidad de escritura."""


class UnsupportedWriteError(MemoryError):
    """El modo de almacenamiento requiere otro contrato de escritura."""


class InvalidEngramError(MemoryError):
    """El contenido o los metadatos del engrama no son validos."""


class InvalidEmbeddingDimensionError(MemoryError):
    """La dimension de embedding no es valida."""


class EngramNotFoundError(MemoryError):
    """El engrama solicitado no existe."""


class InvalidConsolidationEventError(MemoryError):
    """El evento de consolidacion no satisface sus invariantes."""


class ExtendedConfigError(ExtendedError):
    """La configuracion de la capa no es valida."""


class SchemaMigrationRequiredError(ExtendedError):
    """El esquema local no esta migrado; el operador debe migrarlo."""


class EnrichmentParameterError(ExtendedError):
    """Los parametros de enriquecimiento son contradictorios o invalidos."""


class ExternalServiceError(ExtendedError):
    """Base de los errores al consumir servicios locales."""


class ExternalServiceConnectionError(ExternalServiceError):
    """No fue posible conectar con un servicio local."""


class ExternalServiceResponseError(ExternalServiceError):
    """El servicio local devolvio una respuesta no valida."""


class CoreClientError(ExternalServiceError):
    """Base de los errores del cliente REST del core."""


class CoreConnectionError(CoreClientError, ExternalServiceConnectionError):
    """No fue posible conectar con el core."""


class CoreResponseError(CoreClientError, ExternalServiceResponseError):
    """El core devolvio una respuesta no valida."""


class InvalidCoreDomainError(CoreClientError):
    """El dominio explicito no pertenece al catalogo del core."""


class OllamaEmbedderError(ExternalServiceError):
    """Base de los errores del adaptador de embeddings."""


class OllamaConnectionError(
    OllamaEmbedderError,
    ExternalServiceConnectionError,
):
    """No fue posible conectar con Ollama."""


class OllamaResponseError(OllamaEmbedderError, ExternalServiceResponseError):
    """Ollama devolvio una respuesta no valida."""


class RagError(ExtendedError):
    """Base de los errores del sustrato RAG."""


class InvalidRagInputError(RagError):
    """La ingesta o consulta RAG no satisface sus invariantes."""


class RagSchemaError(RagError):
    """El esquema RAG no coincide con la configuracion activa."""


class RagUnavailableError(RagError):
    """Se pidio RAG y su sustrato no esta disponible."""


class KnowledgeWorkflowError(RagError):
    """Base de los errores del workflow de conocimiento."""


class CorpusNotFoundError(KnowledgeWorkflowError):
    """El corpus solicitado no existe."""


class KnowledgeLinkNotFoundError(KnowledgeWorkflowError):
    """El vinculo solicitado no existe."""


class ProtectedKnowledgeLinkError(KnowledgeWorkflowError):
    """La operacion intentaria borrar curacion confirmada o manual."""
