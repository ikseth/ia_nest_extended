"""Registro y validacion de tipos de memoria."""

from __future__ import annotations

from collections.abc import Iterable

from .errors import (
    AliasedDeclarationError,
    AliasedTierError,
    InvalidMemoryTypeError,
    InvalidNamespaceError,
    ScopeViolationError,
    UnknownMemoryTypeError,
)
from .models import (
    MemoryClass,
    MemoryIdentity,
    MemoryKey,
    MemoryType,
    Principal,
    RetrievalMode,
    Scope,
)


class MemoryTypeRegistry:
    def __init__(self, memory_types: Iterable[MemoryType] = ()) -> None:
        self._types: dict[str, MemoryType] = {}
        for memory_type in memory_types:
            self.register(memory_type)

    def register(self, memory_type: MemoryType) -> None:
        self._validate_shape(memory_type)
        if memory_type.name in self._types:
            raise InvalidMemoryTypeError(
                f"el tipo {memory_type.name!r} ya esta registrado"
            )

        for existing in self._types.values():
            if memory_type.declaration_axes == existing.declaration_axes:
                raise AliasedDeclarationError(
                    f"{memory_type.name!r} aliasa la declaracion "
                    f"{existing.name!r}"
                )
            if (
                memory_type.retrieval_mode is RetrievalMode.RANKED
                and existing.retrieval_mode is RetrievalMode.RANKED
                and memory_type.scope is existing.scope
                and memory_type.weight_vector == existing.weight_vector
                and memory_type.half_life_seconds == existing.half_life_seconds
            ):
                raise AliasedTierError(
                    f"{memory_type.name!r} aliasa el tier {existing.name!r}"
                )

        self._types[memory_type.name] = memory_type

    def get(self, name: str) -> MemoryType:
        try:
            return self._types[name]
        except KeyError as exc:
            raise UnknownMemoryTypeError(f"tipo desconocido: {name!r}") from exc

    def list(self) -> tuple[MemoryType, ...]:
        return tuple(self._types.values())

    @staticmethod
    def _validate_shape(memory_type: MemoryType) -> None:
        if not memory_type.name or memory_type.name != memory_type.name.strip():
            raise InvalidMemoryTypeError("name no puede estar vacio ni tener bordes")
        if len(set(memory_type.namespaces)) != len(memory_type.namespaces):
            raise InvalidMemoryTypeError("namespaces contiene duplicados")
        if memory_type.version < 1:
            raise InvalidMemoryTypeError("version debe ser mayor que cero")

        weights = memory_type.weight_vector
        if memory_type.retrieval_mode is RetrievalMode.RANKED:
            if any(weight is None for weight in weights):
                raise InvalidMemoryTypeError(
                    "un tipo ranked exige los cuatro pesos"
                )
            if any(weight is not None and weight < 0.0 for weight in weights):
                raise InvalidMemoryTypeError("los pesos no pueden ser negativos")
        elif any(weight is not None for weight in weights):
            raise InvalidMemoryTypeError(
                "un tipo no ranked no admite pesos de ranking"
            )
        if (
            memory_type.half_life_seconds is not None
            and memory_type.half_life_seconds <= 0
        ):
            raise InvalidMemoryTypeError(
                "half_life_seconds debe ser positivo o null"
            )

        expected_principal = (
            Principal.EXTENDED
            if memory_type.memory_class is MemoryClass.STRICT
            else Principal.CONSCIENCE
        )
        if memory_type.writer_principal is not expected_principal:
            raise InvalidMemoryTypeError(
                "memory_class y writer_principal no son coherentes"
            )
        if memory_type.scope is Scope.SESSION and memory_type.namespaces:
            raise InvalidMemoryTypeError(
                "el tipo de sesion dialog usa namespace crudo"
            )
        if memory_type.scope is not Scope.SESSION and not memory_type.namespaces:
            raise InvalidMemoryTypeError(
                "los tipos no conversacionales exigen namespaces"
            )


def derive_memory_key(
    memory_type: MemoryType,
    identity: MemoryIdentity,
    namespace: str | None,
    entity_id=None,
) -> MemoryKey:
    """Unica derivacion de clave para lectura y escritura."""

    if memory_type.scope is Scope.SESSION:
        if not identity.user_id or not identity.session_id:
            raise ScopeViolationError(
                "scope session exige user_id y session_id"
            )
        if namespace is not None:
            raise InvalidNamespaceError("dialog exige namespace null")
        return MemoryKey(identity.user_id, identity.session_id, None, None)

    if namespace not in memory_type.namespaces:
        raise InvalidNamespaceError(
            f"namespace {namespace!r} no permitido para {memory_type.name!r}"
        )

    if memory_type.scope is Scope.USER:
        if not identity.user_id:
            raise ScopeViolationError("scope user exige user_id")
        return MemoryKey(identity.user_id, None, None, namespace)
    if memory_type.scope is Scope.ENTITY:
        if entity_id is None:
            raise ScopeViolationError("scope entity exige entity_id")
        return MemoryKey(None, None, entity_id, namespace)
    if memory_type.scope is Scope.GLOBAL:
        return MemoryKey(None, None, None, namespace)
    raise ScopeViolationError(f"scope no soportado: {memory_type.scope!r}")


def seed_memory_types() -> tuple[MemoryType, ...]:
    """Declaraciones reconciliadas del roster de fase 2."""

    return (
        MemoryType(
            name="dialog",
            memory_class=MemoryClass.STRICT,
            writer_principal=Principal.EXTENDED,
            retrieval_mode=RetrievalMode.RANKED,
            scope=Scope.SESSION,
            namespaces=(),
            w_recency=1.0,
            w_similarity=0.0,
            w_stability=0.0,
            w_score=0.0,
            half_life_seconds=4 * 60 * 60,
        ),
        MemoryType(
            name="episodic",
            memory_class=MemoryClass.STRICT,
            writer_principal=Principal.EXTENDED,
            retrieval_mode=RetrievalMode.RANKED,
            scope=Scope.USER,
            namespaces=("facts", "tasks", "preferences"),
            w_recency=0.5,
            w_similarity=0.35,
            w_stability=0.05,
            w_score=0.10,
            half_life_seconds=30 * 24 * 60 * 60,
        ),
        MemoryType(
            name="semantic",
            memory_class=MemoryClass.STRICT,
            writer_principal=Principal.EXTENDED,
            retrieval_mode=RetrievalMode.RANKED,
            scope=Scope.USER,
            namespaces=("facts", "preferences"),
            w_recency=0.05,
            w_similarity=0.50,
            w_stability=0.25,
            w_score=0.20,
            half_life_seconds=None,
        ),
        MemoryType(
            name="entities",
            memory_class=MemoryClass.DELEGATED,
            writer_principal=Principal.CONSCIENCE,
            retrieval_mode=RetrievalMode.PROFILE_LOOKUP,
            scope=Scope.ENTITY,
            namespaces=("entities",),
        ),
        MemoryType(
            name="identity",
            memory_class=MemoryClass.DELEGATED,
            writer_principal=Principal.CONSCIENCE,
            retrieval_mode=RetrievalMode.ALWAYS_INJECT,
            scope=Scope.GLOBAL,
            namespaces=("persona",),
        ),
        MemoryType(
            name="principles",
            memory_class=MemoryClass.DELEGATED,
            writer_principal=Principal.CONSCIENCE,
            retrieval_mode=RetrievalMode.ALWAYS_INJECT,
            scope=Scope.GLOBAL,
            namespaces=("principles",),
        ),
        MemoryType(
            name="safety",
            memory_class=MemoryClass.DELEGATED,
            writer_principal=Principal.CONSCIENCE,
            retrieval_mode=RetrievalMode.ALWAYS_INJECT,
            scope=Scope.USER,
            namespaces=("safety",),
        ),
    )
