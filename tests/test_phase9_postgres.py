from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ianest_extended import (
    EngramStatus,
    EngramWrite,
    ExtendedConfig,
    MemoryEnricher,
    MemoryIdentity,
    Principal,
    RecallQuery,
    StatedBy,
    TelemetryWriter,
    WriteAuthorityError,
)
from ianest_extended.maintain import run_maintenance


def _identity():
    return MemoryIdentity(
        user_id=f"phase9-{uuid4()}",
        session_id="thread",
        service="test",
    )


def _dialog(postgres_store, identity, content, stated_by, trace):
    return postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content=content,
            identity=identity,
            stated_by=stated_by,
            source_trace_id=trace,
        ),
    )


def test_phase9_type_authority_window_links_and_replacement(postgres_store):
    declared = {item.name: item for item in postgres_store.list_types()}
    memory_type = declared["thread_summary"]
    assert memory_type.scope.value == "session"
    assert memory_type.writer_principal is Principal.EXTENDED

    identity = _identity()
    sources = []
    for turn in range(2):
        trace = f"trace-{turn}"
        sources.extend(
            (
                _dialog(postgres_store, identity, f"user {turn}", StatedBy.USER, trace),
                _dialog(postgres_store, identity, f"model {turn}", StatedBy.MODEL, trace),
            )
        )
    assert postgres_store.find_thread_synthesis_window(
        identity=identity, window_turns=3
    ) == ()
    window = postgres_store.find_thread_synthesis_window(
        identity=identity, window_turns=2
    )
    assert {item.id for item in window} == {item.id for item in sources}

    with pytest.raises(WriteAuthorityError):
        postgres_store.write_thread_summary(
            Principal.CONSCIENCE,
            identity=identity,
            content="invalid",
            source_ids=tuple(item.id for item in window),
            source_trace_id="summary",
        )

    first = postgres_store.write_thread_summary(
        Principal.EXTENDED,
        identity=identity,
        content="user zero, then user one",
        source_ids=tuple(item.id for item in window),
        source_trace_id="summary-1",
    )
    assert first.links_created == len(window)
    assert first.summary.stated_by is StatedBy.UNKNOWN
    with postgres_store._connect() as connection:
        links = connection.execute(
            """
            SELECT count(*) AS count FROM memory_links
            WHERE source_id = %s AND link_kind = 'summarizes'
            """,
            (first.summary.id,),
        ).fetchone()["count"]
    assert links == len(window)

    for turn in range(2, 4):
        trace = f"trace-{turn}"
        _dialog(postgres_store, identity, f"user {turn}", StatedBy.USER, trace)
        _dialog(postgres_store, identity, f"model {turn}", StatedBy.MODEL, trace)
    second_window = postgres_store.find_thread_synthesis_window(
        identity=identity, window_turns=2
    )
    second = postgres_store.write_thread_summary(
        Principal.EXTENDED,
        identity=identity,
        content="four turns summarized",
        source_ids=tuple(item.id for item in second_window),
        source_trace_id="summary-2",
    )
    assert postgres_store.get_engram(first.summary.id).status is EngramStatus.ARCHIVED
    assert second.summary.status is EngramStatus.ACTIVE
    assert all(postgres_store.get_engram(item.id).status is EngramStatus.ACTIVE for item in sources)


def test_phase9_maintain_archives_summary_and_never_promotes_it(
    postgres_store,
    tmp_path,
):
    identity = _identity()
    user = _dialog(postgres_store, identity, "martes", StatedBy.USER, "trace")
    model = _dialog(postgres_store, identity, "jueves", StatedBy.MODEL, "trace")
    summary = postgres_store.write_thread_summary(
        Principal.EXTENDED,
        identity=identity,
        content="martes fue reemplazado por jueves",
        source_ids=(user.id, model.id),
        source_trace_id="summary",
    ).summary
    old = datetime.now(UTC) - timedelta(hours=5)
    with postgres_store._connect() as connection:
        connection.execute(
            "UPDATE engrams SET created_at = %s WHERE id = ANY(%s::uuid[])",
            (old, [user.id, model.id, summary.id]),
        )

    run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
    )

    assert postgres_store.get_engram(summary.id).status is EngramStatus.ARCHIVED
    semantic = postgres_store.recall(
        RecallQuery(
            type_names=("semantic",),
            identity=identity,
            namespace="facts",
            text="martes jueves",
            top_k=100,
        )
    )
    assert all(item.engram.content != summary.content for item in semantic)
    with postgres_store._connect() as connection:
        promoted = connection.execute(
            """
            SELECT count(*) AS count
            FROM memory_links ml
            JOIN engrams target ON target.id = ml.target_engram_id
            WHERE ml.source_id = %s
              AND ml.link_kind = 'consolidated_from'
              AND target.type_name = 'semantic'
            """,
            (summary.id,),
        ).fetchone()["count"]
    assert promoted == 0


def test_phase9_recall_composes_summary_with_both_contradiction_sides(
    postgres_store,
    tmp_path,
):
    identity = _identity()
    model = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="la clave del refugio es Cobalto",
            identity=identity,
            namespace="facts",
            stated_by=StatedBy.MODEL,
        ),
    )
    user = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="la clave del refugio es Ambar",
            identity=identity,
            namespace="facts",
            stated_by=StatedBy.USER,
        ),
    )
    ordinary = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="el inventario tiene tres mantas",
            identity=identity,
            namespace="facts",
            stated_by=StatedBy.USER,
        ),
    )
    dimension = postgres_store._embedder.dimension
    user_vector = [1.0, 0.0] + [0.0] * (dimension - 2)
    model_vector = [0.8, 0.6] + [0.0] * (dimension - 2)
    with postgres_store._connect() as connection:
        connection.execute(
            "UPDATE engrams SET embedding = %s::vector WHERE id = %s",
            (str(user_vector), user.id),
        )
        connection.execute(
            "UPDATE engrams SET embedding = %s::vector WHERE id = %s",
            (str(model_vector), model.id),
        )
    postgres_store.record_contradiction(
        Principal.EXTENDED,
        stated_by_user=postgres_store.get_engram(user.id),
        conflict_threshold=0.70,
        dedup_threshold=0.92,
    )
    # El enlace ya esta fijado. Igualar ahora los vectores aisla la prueba de
    # orden: la version mas reciente del usuario debe quedar delante sin que
    # la consulta concreta favorezca semanticamente a uno de los dos lados.
    with postgres_store._connect() as connection:
        connection.execute(
            "UPDATE engrams SET embedding = %s::vector WHERE id = %s",
            (str(user_vector), model.id),
        )
    # La ventana real de una sintesis incluye los turnos de su sesion: el
    # almacen exige al menos un `dialog` propio, porque el hilo es la sesion.
    turnos = [
        _dialog(postgres_store, identity, "cual es la clave?", StatedBy.USER, "t1"),
        _dialog(postgres_store, identity, "la clave es Cobalto", StatedBy.MODEL, "t1"),
    ]
    postgres_store.write_thread_summary(
        Principal.EXTENDED,
        identity=identity,
        content="La clave vigente es Ambar y hay tres mantas.",
        source_ids=(model.id, user.id, ordinary.id, *(x.id for x in turnos)),
        source_trace_id="summary",
    )
    enricher = MemoryEnricher(
        store=postgres_store,
        core=None,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(
            telemetry_dir=tmp_path,
            embedding_dimension=dimension,
            rag_enabled=False,
            memory_min_similarity=0.0,
            thread_synthesis_enabled=True,
        ),
    )

    context = enricher.recall(identity, "cual es la clave?").context

    assert "[thread_summary/thread]" in context
    assert "el inventario tiene tres mantas" not in context
    user_line = (
        "[episodic/facts] (fuente: usuario) "
        "la clave del refugio es Ambar"
    )
    model_line = (
        "[episodic/facts] (fuente: modelo, sin verificar; "
        "hay una version del usuario sobre esto) "
        "la clave del refugio es Cobalto"
    )
    assert user_line in context
    assert model_line in context
    assert context.index(user_line) < context.index(model_line)


def test_migrate_is_idempotent_with_summarizes_links_present(postgres_store):
    """Reaplicar las migraciones no debe estrechar lo que una posterior ensancho.

    Regresion medida el 2026-09-21 en el laboratorio: con un enlace
    `summarizes` ya escrito, reejecutar el instalador fallaba con
    CheckViolation, porque la 0004 volvia a poner el CHECK sin ese valor. Las
    migraciones se reaplican TODAS en cada arranque, asi que cada una debe
    poder correr despues de las que vienen detras.
    """

    identity = _identity()
    fuentes = [
        _dialog(postgres_store, identity, "turno del usuario", StatedBy.USER, "t1"),
        _dialog(postgres_store, identity, "turno del modelo", StatedBy.MODEL, "t1"),
    ]
    sintesis = postgres_store.write_thread_summary(
        Principal.EXTENDED,
        identity=identity,
        content="resumen del hilo",
        source_ids=tuple(item.id for item in fuentes),
        source_trace_id="summary-idempotencia",
    )

    assert sintesis.links_created == len(fuentes)

    # El fallo medido ocurria AQUI: la segunda pasada de migraciones estrechaba
    # el CHECK y reventaba con CheckViolation por el enlace recien escrito.
    postgres_store.migrate()
    postgres_store.migrate()

    recuperada = postgres_store.get_engram(sintesis.summary.id)
    assert recuperada is not None
    assert recuperada.status is EngramStatus.ACTIVE
