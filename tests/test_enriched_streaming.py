"""Criterios falsables de prompt.stream y reasoning.stream enriquecidos."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ianest_extended import (
    CoreResult,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    ForwardedStream,
    MemoryIdentity,
    RagChunk,
    SseEvent,
    cli,
)
from ianest_extended.rest import _stream_events

from .fakes import InMemoryRagStore, InMemoryStore


def _event(name, data):
    encoded = json.dumps({"type": name, "data": data}, sort_keys=True)
    return SseEvent(name, encoded, f"event: {name}\ndata: {encoded}")


class StreamingCore:
    def __init__(self, *, slow=False, fail=False):
        self.calls = []
        self.closed = 0
        self.slow = slow
        self.fail = fail
        self.finished = False

    def prompt_stream(self, prompt, identity, model=None, domain=None):
        self.calls.append(("prompt.stream", prompt, identity, model, domain))
        anchored = "dato exclusivo" in prompt
        response = "respuesta anclada" if anchored else "respuesta sin corpus"

        def events():
            yield _event("token", {"text": response})
            if self.fail:
                raise RuntimeError("corte del core")
            if self.slow:
                time.sleep(0.12)
            yield _event(
                "done",
                {
                    "text": response,
                    "finish_reason": "stop",
                    "model": "stub",
                    "tokens_in": 2,
                    "tokens_out": 2,
                },
            )
            self.finished = True

        return ForwardedStream(events(), self._close)

    def reasoning_stream(self, prompt, identity, model=None, domain=None):
        self.calls.append(("reasoning.stream", prompt, identity, model, domain))
        anchored = "dato exclusivo" in prompt
        response = (
            "razonamiento anclado" if anchored else "razonamiento sin corpus"
        )

        def events():
            yield _event("step", {"iteration": 1, "output": "borrador"})
            if self.fail:
                raise RuntimeError("corte del core")
            if self.slow:
                time.sleep(0.12)
            yield _event(
                "done",
                {
                    "output": response,
                    "stop_reason": "model_done",
                    "trace": {"request_id": "core-reasoning-stream"},
                },
            )
            self.finished = True

        return ForwardedStream(events(), self._close)

    def prompt_run(self, prompt, identity, model=None, domain=None):
        self.calls.append(("prompt.run", prompt, identity, model, domain))
        return CoreResult(
            response=json.dumps(
                {
                    "items": [
                        {
                            "namespace": "facts",
                            "content": "dato durable",
                            "confidence": 0.9,
                            "mentions": [],
                        }
                    ]
                }
            ),
            trace={"request_id": "core-extraction", "finish_reason": "stop"},
        )

    def list_domains(self):
        return ("general", "linux")

    def forward(self, capability, payload=None, method=None):
        self.calls.append(("forward", capability, payload, method))
        return ForwardedStream(iter((_event("task_done", {"response": "ok"}),)), self._close)

    def _close(self):
        self.closed += 1


def _chunk():
    return RagChunk(
        id=uuid4(),
        corpus_id=uuid4(),
        corpus_name="manual-linux",
        domains=("linux",),
        content="dato exclusivo del corpus",
        source_ref="linux.md",
        ordinal=0,
        score=0.9,
        created_at=datetime.now(UTC),
    )


def _service(tmp_path, core, store=None, rag_store=None):
    store = store or InMemoryStore()
    rag_store = rag_store or InMemoryRagStore((_chunk(),))
    config = ExtendedConfig(
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        embedding_dimension=2,
        rag_enabled=False,
        auto_domain=False,
    )
    service = ExtendedService(
        ExtendedComposition(
            config,
            core=core,
            memory_store=store,
            rag_store=rag_store,
        )
    )
    return service, store, rag_store


def _identity():
    return MemoryIdentity(user_id="u", session_id="s", service="test")


def _telemetry(tmp_path):
    path = next(tmp_path.glob("extended-*.jsonl"))
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]


def test_prompt_stream_is_enriched_and_passthrough_is_not(tmp_path):
    core = StreamingCore()
    service, store, rag = _service(tmp_path, core)

    enriched = list(
        service.prompt_stream(
            "pregunta",
            _identity(),
            domain="linux",
            use_memory=False,
            use_rag=True,
            write_back=False,
        )
    )
    plain = list(service.prompt_stream("pregunta", _identity(), enrich=False))

    assert "respuesta anclada" in enriched[0].data
    assert "respuesta sin corpus" in plain[0].data
    assert "dato exclusivo" in core.calls[0][1]
    assert core.calls[1][1] == "pregunta"
    assert rag.domains == ["linux"]
    assert store.engrams == []


def test_first_event_arrives_before_slow_stream_finishes_and_shape_is_intact(
    tmp_path,
):
    core = StreamingCore(slow=True)
    service, _, _ = _service(tmp_path, core)
    stream = service.prompt_stream(
        "pregunta",
        _identity(),
        use_memory=False,
        use_rag=False,
        write_back=False,
    )
    events = iter(stream)

    started = time.monotonic()
    first = next(events)

    assert time.monotonic() - started < 0.05
    assert core.finished is False
    assert first == _event("token", {"text": "respuesta sin corpus"})
    remaining = list(events)
    assert remaining == [
        _event(
            "done",
            {
                "text": "respuesta sin corpus",
                "finish_reason": "stop",
                "model": "stub",
                "tokens_in": 2,
                "tokens_out": 2,
            },
        )
    ]


def test_reasoning_stream_has_the_same_enrichment_and_non_buffering(tmp_path):
    core = StreamingCore(slow=True)
    service, _, rag = _service(tmp_path, core)
    stream = service.reasoning_stream(
        "pregunta",
        _identity(),
        domain="linux",
        use_memory=False,
        use_rag=True,
        write_back=False,
    )
    events = iter(stream)

    started = time.monotonic()
    first = next(events)

    assert time.monotonic() - started < 0.05
    assert core.finished is False
    assert first == _event("step", {"iteration": 1, "output": "borrador"})
    assert list(events) == [
        _event(
            "done",
            {
                "output": "razonamiento anclado",
                "stop_reason": "model_done",
                "trace": {"request_id": "core-reasoning-stream"},
            },
        )
    ]
    assert "dato exclusivo" in core.calls[0][1]
    assert rag.domains == ["linux"]


@pytest.mark.parametrize(
    ("capability", "expected_trace"),
    [
        ("prompt.stream", None),
        ("reasoning.stream", "core-reasoning-stream"),
    ],
)
def test_clean_stream_writes_both_turns_extracts_and_uses_honest_trace(
    tmp_path,
    capability,
    expected_trace,
):
    core = StreamingCore()
    service, store, _ = _service(tmp_path, core)

    stream = getattr(service, capability.replace(".", "_"))(
        "pregunta original",
        _identity(),
        use_memory=False,
        use_rag=False,
        write_back=True,
    )
    list(stream)

    dialog = [item for item in store.engrams if item.type_name == "dialog"]
    episodic = [item for item in store.engrams if item.type_name == "episodic"]
    assert len(dialog) == 2
    assert [item.content for item in dialog][0] == "pregunta original"
    assert len(episodic) == 1
    assert {item.source_trace_id for item in store.engrams} == {expected_trace}


@pytest.mark.parametrize("capability", ["prompt.stream", "reasoning.stream"])
def test_client_cut_does_not_write_and_is_traced(tmp_path, capability):
    core = StreamingCore()
    service, store, _ = _service(tmp_path, core)
    stream = getattr(service, capability.replace(".", "_"))(
        "pregunta",
        _identity(),
        use_memory=False,
        use_rag=False,
        write_back=True,
    )

    assert next(iter(stream)).event in {"token", "step"}
    stream.close()

    assert store.engrams == []
    event = next(item for item in _telemetry(tmp_path) if item["event"] == capability)
    assert event["status"] == "interrupted"
    assert event["counters"]["write_back"] == 1


def test_stream_error_does_not_write_and_is_traced(tmp_path):
    core = StreamingCore(fail=True)
    service, store, _ = _service(tmp_path, core)
    stream = service.prompt_stream(
        "pregunta",
        _identity(),
        use_memory=False,
        use_rag=False,
        write_back=True,
    )
    events = iter(stream)
    next(events)

    with pytest.raises(RuntimeError, match="corte del core"):
        next(events)

    assert store.engrams == []
    event = next(item for item in _telemetry(tmp_path) if item["event"] == "prompt.stream")
    assert event["status"] == "error"


def test_rest_client_disconnect_closes_without_write_back(tmp_path):
    core = StreamingCore()
    service, store, _ = _service(tmp_path, core)
    stream = service.prompt_stream(
        "pregunta",
        _identity(),
        use_memory=False,
        use_rag=False,
        write_back=True,
    )
    response_body = _stream_events(stream)

    assert next(response_body).startswith(b"event: token\n")
    response_body.close()

    assert store.engrams == []
    event = next(item for item in _telemetry(tmp_path) if item["event"] == "prompt.stream")
    assert event["status"] == "interrupted"


def test_passthrough_has_no_recall_injection_or_write_but_has_own_trace(tmp_path):
    core = StreamingCore()
    service, store, rag = _service(tmp_path, core)

    events = list(service.reasoning_stream("literal", _identity(), enrich=False))

    assert events[-1].event == "done"
    assert core.calls[0][1] == "literal"
    assert store.recall_queries == []
    assert store.engrams == []
    assert rag.domains == []
    event = next(item for item in _telemetry(tmp_path) if item["event"] == "reasoning.stream")
    assert event["status"] == "ok"
    assert event["counters"] == {
        "enrich": 0,
        "use_memory": 0,
        "use_rag": 0,
        "write_back": 0,
    }


def test_task_stream_remains_forwarded(tmp_path):
    core = StreamingCore()
    service, _, _ = _service(tmp_path, core)

    stream = service.forward("task.stream", {"prompt": "tarea"})

    assert [event.event for event in stream] == ["task_done"]
    assert core.calls[0] == (
        "forward",
        "task.stream",
        {"prompt": "tarea"},
        None,
    )


def test_cli_handler_uses_shared_enriched_stream(tmp_path, capsys):
    core = StreamingCore()
    service, _, _ = _service(tmp_path, core)
    args = SimpleNamespace(
        prompt="pregunta",
        enrich=True,
        use_memory=False,
        use_rag=False,
        write_back=False,
        domain=None,
        auto_domain=False,
        model=None,
        json=False,
        user_id=None,
        session_id=None,
        service=None,
        namespace=None,
    )

    code = cli._prompt_stream(service, service.config, args)

    assert code == 0
    assert capsys.readouterr().out.splitlines() == [
        _event("token", {"text": "respuesta sin corpus"}).data,
        _event(
            "done",
            {
                "text": "respuesta sin corpus",
                "finish_reason": "stop",
                "model": "stub",
                "tokens_in": 2,
                "tokens_out": 2,
            },
        ).data,
    ]
