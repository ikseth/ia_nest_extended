"""Errores tipados del sustrato de memoria."""


class MemoryError(Exception):
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


class ExtendedConfigError(Exception):
    """La configuracion de la capa no es valida."""


class ExternalServiceError(Exception):
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


class OllamaEmbedderError(ExternalServiceError):
    """Base de los errores del adaptador de embeddings."""


class OllamaConnectionError(
    OllamaEmbedderError,
    ExternalServiceConnectionError,
):
    """No fue posible conectar con Ollama."""


class OllamaResponseError(OllamaEmbedderError, ExternalServiceResponseError):
    """Ollama devolvio una respuesta no valida."""


class RagError(Exception):
    """Base de los errores del sustrato RAG."""


class InvalidRagInputError(RagError):
    """La ingesta o consulta RAG no satisface sus invariantes."""


class RagSchemaError(RagError):
    """El esquema RAG no coincide con la configuracion activa."""
