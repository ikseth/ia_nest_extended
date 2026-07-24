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
