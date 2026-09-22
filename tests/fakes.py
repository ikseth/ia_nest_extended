from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from ianest_extended import (
    Engram,
    EngramStatus,
    EngramWrite,
    MemoryIdentity,
    RecallItem,
    SchemaMigrationRequiredError,
    Session,
    SessionNotActiveError,
    SessionStatus,
    StatedBy,
    ThreadSynthesisResult,
)


def _word_overlap(left: str, right: str) -> float:
    left_words = set(left.casefold().split())
    right_words = set(right.casefold().split())
    if not left_words or not right_words:
        return 0.0
    union = left_words | right_words
    return len(left_words & right_words) / len(union)


class InMemoryStore:
    def __init__(self):
        self.engrams = []
        self.recall_queries = []
        self.migrated = False
        self.verified = 0
        self.summary_links = {}
        self.contradiction_links = set()
        self.sessions = {}

    def write(self, principal, request):
        session_scoped = request.type_name in {"dialog", "thread_summary"}
        now = datetime.now(UTC)
        if session_scoped:
            key = (request.identity.user_id, request.identity.session_id)
            session = self.sessions.get(key)
            if request.type_name == "dialog" and session is None:
                session = Session(
                    user_id=key[0],
                    session_id=key[1],
                    created_at=now,
                    last_activity_at=now,
                    status=SessionStatus.ACTIVE,
                    archived_at=None,
                    closed_at=None,
                )
                self.sessions[key] = session
            elif session is None:
                # Varias pruebas unitarias de composicion construyen una
                # sintesis aislada, sin ejercitar el ciclo de sesion. El
                # adaptador PostgreSQL conserva el invariante real: alli una
                # sintesis exige dialogos y una sesion ya declarada.
                session = Session(
                    user_id=key[0],
                    session_id=key[1],
                    created_at=now,
                    last_activity_at=now,
                    status=SessionStatus.ACTIVE,
                    archived_at=None,
                    closed_at=None,
                )
                self.sessions[key] = session
            if session.status is not SessionStatus.ACTIVE:
                raise SessionNotActiveError(
                    f"la sesion {key[1]!r} esta {session.status.value} "
                    "y no admite escrituras",
                    "session_id",
                )
            if request.type_name == "dialog":
                self.sessions[key] = replace(session, last_activity_at=now)
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
            created_at=now,
            last_reinforced_at=None,
            stated_by=request.stated_by,
        )
        self.engrams.append(engram)
        return engram

    def recall(self, query):
        self.recall_queries.append(query)
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
            elif engram.type_name == "thread_summary":
                if (
                    engram.user_id != query.identity.user_id
                    or engram.session_id != query.identity.session_id
                    or engram.namespace != query.namespace
                ):
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

    def record_contradiction(
        self,
        principal,
        *,
        stated_by_user,
        conflict_threshold,
        dedup_threshold,
    ):
        """Sin pgvector, la banda se aproxima por solapamiento de palabras."""
        marked = []
        for index, engram in enumerate(self.engrams):
            if (
                engram.id == stated_by_user.id
                or engram.stated_by != StatedBy.MODEL
            ):
                continue
            if (
                engram.type_name != stated_by_user.type_name
                or engram.user_id != stated_by_user.user_id
                or engram.status != EngramStatus.ACTIVE
            ):
                continue
            similarity = _word_overlap(engram.content, stated_by_user.content)
            if conflict_threshold <= similarity < dedup_threshold:
                # El estado NO cambia: solo se anota (ADR 0013).
                annotated = replace(
                    engram,
                    contradicted=True,
                    contradiction_involved=True,
                )
                self.engrams[index] = annotated
                self.contradiction_links.add((engram.id, stated_by_user.id))
                marked.append(annotated)
        if marked:
            for index, engram in enumerate(self.engrams):
                if engram.id == stated_by_user.id:
                    self.engrams[index] = replace(
                        engram,
                        contradiction_involved=True,
                    )
                    break
        return tuple(marked)

    def find_thread_synthesis_window(self, *, identity, window_turns):
        summaries = [
            item
            for item in self.engrams
            if item.type_name == "thread_summary"
            and item.user_id == identity.user_id
            and item.session_id == identity.session_id
        ]
        latest_at = max(
            (item.created_at for item in summaries),
            default=None,
        )
        dialogs = [
            item
            for item in self.engrams
            if item.type_name == "dialog"
            and item.user_id == identity.user_id
            and item.session_id == identity.session_id
            and item.status is EngramStatus.ACTIVE
        ]
        new_dialogs = [
            item
            for item in dialogs
            if latest_at is None or item.created_at > latest_at
        ]
        if len(new_dialogs) < window_turns * 2:
            return ()
        trace_ids = {
            item.source_trace_id
            for item in dialogs
            if item.source_trace_id is not None
        }
        episodic = [
            item
            for item in self.engrams
            if item.type_name == "episodic"
            and item.user_id == identity.user_id
            and item.status is EngramStatus.ACTIVE
            and item.source_trace_id in trace_ids
        ]
        return tuple(sorted((*dialogs, *episodic), key=lambda item: item.created_at))

    def write_thread_summary(
        self,
        principal,
        *,
        identity,
        content,
        source_ids,
        source_trace_id,
    ):
        sources = [self.get_engram(source_id) for source_id in source_ids]
        stated_bys = {source.stated_by for source in sources}
        stated_by = (
            stated_bys.pop() if len(stated_bys) == 1 else StatedBy.UNKNOWN
        )
        summary = self.write(
            principal,
            EngramWrite(
                type_name="thread_summary",
                content=content,
                identity=identity,
                namespace="thread",
                source_trace_id=source_trace_id,
                stated_by=stated_by,
            ),
        )
        summary = replace(summary, summarized_ids=tuple(source_ids))
        self.engrams[-1] = summary
        self.summary_links[summary.id] = tuple(source_ids)
        for index, item in enumerate(self.engrams[:-1]):
            if (
                item.type_name == "thread_summary"
                and item.user_id == identity.user_id
                and item.session_id == identity.session_id
                and item.status is EngramStatus.ACTIVE
            ):
                self.engrams[index] = replace(
                    item,
                    status=EngramStatus.ARCHIVED,
                    archived_at=datetime.now(UTC),
                    archived_reason="replaced_by_thread_summary",
                    version=item.version + 1,
                )
        return ThreadSynthesisResult(summary, len(source_ids))

    def archive_thread_summaries(self, principal, *, sessions, reason):
        session_set = set(sessions)
        archived = []
        for index, item in enumerate(self.engrams):
            if (
                item.type_name == "thread_summary"
                and (item.user_id, item.session_id) in session_set
                and item.status is EngramStatus.ACTIVE
            ):
                changed = replace(
                    item,
                    status=EngramStatus.ARCHIVED,
                    archived_at=datetime.now(UTC),
                    archived_reason=reason,
                    version=item.version + 1,
                )
                self.engrams[index] = changed
                archived.append(changed)
        return tuple(archived)

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
        self.migrated = True

    def verify_schema(self):
        self.verified += 1

    def get_session(self, user_id, session_id):
        return self.sessions.get((user_id, session_id))

    def find_dialogs_to_archive(self, *, now, inactivity_seconds):
        cutoff = now.timestamp() - inactivity_seconds
        return tuple(
            item
            for item in self.engrams
            if item.type_name == "dialog"
            and item.status is EngramStatus.ACTIVE
            and self.sessions[(item.user_id, item.session_id)].status
            is SessionStatus.ACTIVE
            and self.sessions[(item.user_id, item.session_id)]
            .last_activity_at.timestamp()
            < cutoff
        )

    def archive_inactive_sessions(
        self,
        *,
        now,
        inactivity_seconds,
        reason,
    ):
        cutoff = now.timestamp() - inactivity_seconds
        inactive = {
            key
            for key, session in self.sessions.items()
            if session.status is SessionStatus.ACTIVE
            and session.last_activity_at.timestamp() < cutoff
        }
        for key in inactive:
            self.sessions[key] = replace(
                self.sessions[key],
                status=SessionStatus.ARCHIVED,
                archived_at=now,
            )
        archived = []
        for index, item in enumerate(self.engrams):
            if (
                (item.user_id, item.session_id) in inactive
                and item.type_name in {"dialog", "thread_summary"}
                and item.status is EngramStatus.ACTIVE
            ):
                changed = replace(
                    item,
                    status=EngramStatus.ARCHIVED,
                    archived_at=now,
                    archived_reason=reason,
                    version=item.version + 1,
                )
                self.engrams[index] = changed
                archived.append(changed)
        return tuple(archived)

    def find_episodic_to_promote(
        self,
        *,
        now,
        recency_max,
        min_stability,
        min_score,
    ):
        return ()

    def execute_consolidation(self, event):
        raise NotImplementedError

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


class UnmigratedStore(InMemoryStore):
    """Store cuyo esquema no esta migrado: verificar falla, no muta nada."""

    def verify_schema(self):
        self.verified += 1
        raise SchemaMigrationRequiredError(
            "el esquema de memoria no esta migrado (falta 'engrams'); "
            "ejecuta 'ianest-extended runtime migrate'",
            "engrams",
        )


class InMemoryRagStore:
    def __init__(self, chunks=()):
        self.chunks = tuple(chunks)
        self.domains = []
        self.min_scores = []
        self.migrated = False

    def migrate(self):
        self.migrated = True

    def verify_schema(self):
        return None

    def retrieve(self, query_text, *, domain=None, top_k=3, min_score=0.0):
        self.domains.append(domain)
        self.min_scores.append(min_score)
        selected = [
            chunk
            for chunk in self.chunks
            if (domain is None or domain in chunk.domains)
            and chunk.score >= min_score
        ]
        return tuple(selected[:top_k])


def identity(user="u", session="A"):
    return MemoryIdentity(
        user_id=user,
        session_id=session,
        service="test",
        domain_tag="linux",
        namespace="preferences",
    )
