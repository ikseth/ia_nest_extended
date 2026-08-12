from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from ianest_extended import (
    Engram,
    EngramStatus,
    MemoryIdentity,
    RecallItem,
)


class InMemoryStore:
    def __init__(self):
        self.engrams = []

    def write(self, principal, request):
        session_scoped = request.type_name == "dialog"
        engram = Engram(
            id=uuid4(),
            type_name=request.type_name,
            user_id=request.identity.user_id,
            session_id=request.identity.session_id if session_scoped else None,
            namespace=request.namespace,
            content=request.content,
            embedding=(),
            score=request.score,
            stability=request.stability,
            service=request.service,
            domain_tag=request.domain_tag,
            entity_refs=request.entity_refs,
            unresolved_mentions=request.unresolved_mentions,
            status=EngramStatus.ACTIVE,
            archived_at=None,
            archived_reason=None,
            source_trace_id=request.source_trace_id,
            version=1,
            created_at=datetime.now(UTC),
            last_reinforced_at=None,
        )
        self.engrams.append(engram)
        return engram

    def recall(self, query):
        items = []
        for engram in reversed(self.engrams):
            if engram.type_name not in query.type_names:
                continue
            if engram.domain_tag is not None and engram.domain_tag != query.domain_tag:
                continue
            if engram.type_name == "dialog":
                if (
                    engram.user_id != query.identity.user_id
                    or engram.session_id != query.identity.session_id
                ):
                    continue
            elif engram.type_name in {"episodic", "semantic", "safety"}:
                if engram.user_id != query.identity.user_id:
                    continue
                if engram.namespace != query.namespace:
                    continue
            elif engram.namespace != query.namespace:
                continue
            items.append(
                RecallItem(
                    type_name=engram.type_name,
                    relevance=1.0,
                    engram=engram,
                )
            )
        return tuple(items[: query.top_k])

    def find_similar(self, *, user_id, namespace, text, threshold):
        return next(
            (
                engram
                for engram in self.engrams
                if engram.type_name == "episodic"
                and engram.user_id == user_id
                and engram.namespace == namespace
                and engram.content == text
            ),
            None,
        )

    def reinforce(self, principal, engram_id):
        for index, engram in enumerate(self.engrams):
            if engram.id == engram_id:
                reinforced = replace(
                    engram,
                    stability=engram.stability + 1,
                    last_reinforced_at=datetime.now(UTC),
                    version=engram.version + 1,
                )
                self.engrams[index] = reinforced
                return reinforced
        raise AssertionError("engrama no encontrado")

    def migrate(self):
        return None

    def register_type(self, memory_type):
        return None

    def list_types(self):
        return ()

    def write_entity(self, principal, type_name, entity):
        raise NotImplementedError

    def archive(self, principal, engram_id, reason):
        raise NotImplementedError

    def get_engram(self, engram_id):
        return next(item for item in self.engrams if item.id == engram_id)


def identity(user="u", session="A"):
    return MemoryIdentity(
        user_id=user,
        session_id=session,
        service="test",
        domain_tag="linux",
        namespace="preferences",
    )
