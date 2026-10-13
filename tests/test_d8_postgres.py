"""Aceptacion de persistencia de D8 contra PostgreSQL real."""

from ianest_extended import (
    CoreResult,
    EngramWrite,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    MemoryIdentity,
    Principal,
    StatedBy,
    TaskPlanResult,
)


class _Core:
    def prompt_run(self, prompt, identity, model=None, domain=None):
        if prompt.startswith("Rewrite the user request"):
            response = "peticion autonoma efimera"
            request_id = "core-condense"
        else:
            response = '{"from_user":[],"from_assistant":[]}'
            request_id = "core-extract"
        return CoreResult(
            response=response,
            trace={"request_id": request_id, "finish_reason": "stop"},
            payload={
                "response": response,
                "trace": {
                    "request_id": request_id,
                    "finish_reason": "stop",
                },
            },
        )

    def task_plan(self, prompt, identity, *, effort=None):
        payload = {
            "plan": [
                {
                    "index": 0,
                    "prompt": prompt,
                    "domain": "general",
                    "depends_on": [],
                }
            ],
            "requirements": [],
            "trace": {"request_id": "core-plan"},
        }
        return TaskPlanResult(
            payload=payload,
            plan=tuple(payload["plan"]),
            trace=payload["trace"],
        )

    def task_run(self, prompt, identity, *, plan_payload=None, effort=None):
        return CoreResult(
            response="respuesta combinada",
            trace={"request_id": "core-task", "stop_reason": "task_done"},
            payload={
                "response": "respuesta combinada",
                "stop_reason": "task_done",
                "trace": {
                    "request_id": "core-task",
                    "stop_reason": "task_done",
                },
            },
        )


def test_task_condensed_request_is_never_persisted_in_postgres(
    postgres_store,
    tmp_path,
):
    """D8 criterio 5: la consulta conserva solo las palabras literales."""
    identity = MemoryIdentity(user_id="d8-user", session_id="d8-session")
    postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content="contexto previo para resolver la referencia",
            identity=identity,
            stated_by=StatedBy.MODEL,
        ),
    )
    config = ExtendedConfig(
        database_dsn=postgres_store._dsn,
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        embedding_dimension=postgres_store._embedder.dimension,
        rag_enabled=False,
    )
    service = ExtendedService(
        ExtendedComposition(
            config,
            core=_Core(),
            memory_store=postgres_store,
        )
    )

    service.task_run(
        "continua",
        identity,
        use_memory=True,
        use_rag=False,
        write_back=True,
    )

    with postgres_store._connect() as connection:
        rows = connection.execute(
            "SELECT content, stated_by FROM engrams ORDER BY created_at, id"
        ).fetchall()
    assert any(
        row["content"] == "continua" and row["stated_by"] == "user"
        for row in rows
    )
    assert not any(row["content"] == "peticion autonoma efimera" for row in rows)
