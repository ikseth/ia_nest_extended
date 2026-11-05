import json
from uuid import uuid4

import pytest

from ianest_extended import (
    CoreClient,
    CoreConnectionError,
    EntityProfile,
    CoreResult,
    EngramStatus,
    ExtendedConfig,
    EngramWrite,
    MemoryEnricher,
    Principal,
    RecallItem,
    StatedBy,
    TelemetryWriter,
)
from ianest_extended.enrichment import (
    _compose_context,
    _extraction_prompt,
    _lines,
    _parse_extraction,
    _validate_item,
)

from .fakes import InMemoryStore, identity


def _enricher(tmp_path, local_service_stub, store, **overrides):
    config = ExtendedConfig(
        telemetry_dir=tmp_path,
        embedding_dimension=2,
        memory_budget_tokens=1500,
        **overrides,
    )
    return MemoryEnricher(
        store=store,
        core=CoreClient(local_service_stub.base_url, connect_timeout_seconds=2),
        telemetry=TelemetryWriter(tmp_path),
        config=config,
    )


def _events(tmp_path):
    path = next(tmp_path.glob("extended-*.jsonl"))
    return [json.loads(line) for line in path.read_text().splitlines()]


class ExtractionCore:
    def __init__(self, extraction_responses):
        self._extraction_responses = iter(extraction_responses)
        self.calls = []

    def prompt_run(self, prompt, identity, model=None, domain=None):
        self.calls.append((prompt, identity, model, domain))
        response = next(self._extraction_responses)
        if isinstance(response, Exception):
            raise response
        return CoreResult(
            response=response,
            trace={"request_id": "core-extraction", "finish_reason": "stop"},
            payload={"response": response},
        )


def _write_back_enricher(tmp_path, store, core):
    return MemoryEnricher(
        store=store,
        core=core,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(
            telemetry_dir=tmp_path,
            embedding_dimension=2,
            memory_budget_tokens=1500,
        ),
    )


def _write_back_core_result():
    return CoreResult(
        response="the user prefers blue",
        trace={"request_id": "core-answer", "finish_reason": "stop"},
        payload={"response": "the user prefers blue"},
    )


def _valid_extraction():
    return json.dumps(
        {
            "from_user": [
                {
                    "namespace": "preferences",
                    "content": "the user prefers blue",
                    "confidence": 0.95,
                    "mentions": [],
                }
            ],
            "from_assistant": [],
        }
    )


def test_vertical_thread_continuity_antinoise_and_telemetry(
    tmp_path,
    local_service_stub,
):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    first = enricher.enrich(identity(session="A"), "remember-blue")
    second = enricher.enrich(identity(session="A"), "smalltalk")
    other_session = enricher.recall(identity(session="B"), "remember-blue")

    assert "the user prefers blue" in second.context
    assert "the user prefers blue" not in other_session.context
    assert "[dialog/raw] (fuente: usuario) remember-blue" in second.context
    thread_artifacts = [item for item in store.engrams if item.type_name == "thread_artifacts"]
    dialog = [item for item in store.engrams if item.type_name == "dialog"]
    assert len(thread_artifacts) == 1
    assert len(dialog) == 4
    assert first.trace["finish_reason"] == "stop"

    events = _events(tmp_path)
    assert [event["event"] for event in events] == [
        "enrich.recall",
        "enrich.write_back",
        "enrich.recall",
        "enrich.write_back",
    ]
    assert events[0]["request_id"] == events[1]["request_id"]
    assert events[0]["downstream_request_id"] == events[1]["downstream_request_id"]
    assert events[3]["counters"]["items_written"] == 0


def test_d4_floor_only_reaches_thread_artifacts(tmp_path):
    """D4: MemoryEnricher solo pasa el suelo a `thread_artifacts`.

    `semantic`, `dialog` y los delegados no reciben `min_similarity` desde
    esta capa (criterios 3, 4 y 5 del brief). Esta prueba verifica el
    cableado -que RecallQuery recibe cada tipo-, no el gateo en si: eso lo
    cubren las pruebas de PostgreSQL con similitud controlada, porque
    `InMemoryStore` (el fake de estas pruebas) ignora `min_similarity`.
    """
    store = InMemoryStore()
    enricher = MemoryEnricher(
        store=store,
        core=CoreClient("http://127.0.0.1:1"),
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path, embedding_dimension=2),
    )
    identity_value = identity()
    for type_name, namespace in (
        ("identity", "persona"),
        ("principles", "principles"),
        ("safety", "safety"),
    ):
        store.write(
            Principal.CONSCIENCE,
            EngramWrite(
                type_name=type_name,
                content=f"{type_name} con similitud arbitrariamente baja",
                identity=identity_value,
                namespace=namespace,
            ),
        )
    store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content="turno previo poco similar",
            identity=identity_value,
        ),
    )

    bundle = enricher.recall(identity_value, "consulta sin relacion")
    floor_by_type = {
        query.type_names[0]: query.min_similarity
        for query in store.recall_queries
    }

    assert {item.type_name for item in bundle.delegated} == {
        "identity",
        "principles",
        "safety",
    }
    assert bundle.dialog
    assert floor_by_type["thread_artifacts"] == 0.10
    assert floor_by_type["semantic"] is None
    assert floor_by_type["dialog"] is None
    assert all(
        floor_by_type[type_name] is None
        for type_name in ("identity", "principles", "safety")
    )


def test_write_back_reinforces_duplicate(tmp_path, local_service_stub):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    enricher.enrich(identity(session="A"), "repeat-fact")
    enricher.enrich(identity(session="A"), "repeat-fact")

    thread_artifacts = [item for item in store.engrams if item.type_name == "thread_artifacts"]
    assert len(thread_artifacts) == 1
    assert thread_artifacts[0].stability == 1
    assert thread_artifacts[0].unresolved_mentions == ("PostgreSQL",)
    assert _events(tmp_path)[-1]["counters"]["items_reinforced"] == 1


def test_write_back_does_not_deduplicate_across_sessions(
    tmp_path,
    local_service_stub,
):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    enricher.enrich(identity(session="A"), "repeat-fact")
    enricher.enrich(identity(session="B"), "repeat-fact")

    artifacts = [
        item for item in store.engrams if item.type_name == "thread_artifacts"
    ]
    assert len(artifacts) == 2
    assert {item.session_id for item in artifacts} == {"A", "B"}
    assert all(item.stability == 0 for item in artifacts)


def test_invalid_extraction_is_discarded_and_traced(
    tmp_path,
    local_service_stub,
):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    enricher.enrich(identity(), "invalid-json")

    assert not [item for item in store.engrams if item.type_name == "thread_artifacts"]
    event = _events(tmp_path)[-1]
    assert event["status"] == "invalid_extraction_json"
    assert event["counters"]["invalid_json"] == 1
    assert event["counters"]["extraction_retried"] == 1
    extraction_calls = [
        request
        for path, request in local_service_stub.requests
        if path == "/prompt/run" and request.get("model")
    ]
    assert len(extraction_calls) == 2


def test_invalid_extraction_retries_once_and_writes_valid_items(tmp_path):
    store = InMemoryStore()
    core = ExtractionCore(["not-json", _valid_extraction()])
    enricher = _write_back_enricher(tmp_path, store, core)

    counters, status = enricher.write_back(
        request_id="request-1",
        identity=identity(),
        prompt="the user prefers blue",
        core_result=_write_back_core_result(),
    )

    assert status == "ok"
    assert counters["extraction_retried"] == 1
    assert counters["invalid_json"] == 0
    assert counters["items_written"] == 1
    assert len(core.calls) == 2
    assert core.calls[0] == core.calls[1]


def test_valid_extraction_does_not_retry(tmp_path):
    store = InMemoryStore()
    core = ExtractionCore([_valid_extraction()])
    enricher = _write_back_enricher(tmp_path, store, core)

    counters, status = enricher.write_back(
        request_id="request-1",
        identity=identity(),
        prompt="the user prefers blue",
        core_result=_write_back_core_result(),
    )

    assert status == "ok"
    assert counters["extraction_retried"] == 0
    assert len(core.calls) == 1


def test_core_error_during_extraction_does_not_retry(tmp_path):
    store = InMemoryStore()
    core = ExtractionCore([CoreConnectionError("core unavailable")])
    enricher = _write_back_enricher(tmp_path, store, core)

    with pytest.raises(CoreConnectionError):
        enricher.write_back(
            request_id="request-1",
            identity=identity(),
            prompt="the user prefers blue",
            core_result=_write_back_core_result(),
        )

    assert len(core.calls) == 1
    assert _events(tmp_path)[-1]["counters"]["extraction_retried"] == 0


def test_extraction_prompt_uses_concrete_values_and_json_only():
    prompt = _extraction_prompt("hola", "hola")

    assert '"namespace":"preferences"' in prompt
    assert '"confidence":0.9' in prompt
    assert '{"from_user":[],"from_assistant":[]}' in prompt
    assert "facts|preferences|tasks" not in prompt
    assert "no markdown fences or text outside the JSON" in prompt


def test_extraction_prompt_separates_the_two_emitters():
    prompt = _extraction_prompt("hola", "hola")

    assert "from_user" in prompt and "from_assistant" in prompt
    assert "Never move an item from one list to the other." in prompt


def test_extraction_prompt_forbids_translating_the_item():
    """Si el extractor traduce, el anclaje no reconoce su propio bloque.

    Medido en el lab el 2026-08-22: sin esta linea, mistral-nemo devolvia el
    item en ingles -o con `content` nulo- ante una conversacion en espanol, y
    toda la atribucion caia a `unknown`.
    """
    prompt = _extraction_prompt("hola", "hola")

    assert "SAME LANGUAGE" in prompt
    assert "never translate it" in prompt


def test_dialog_records_who_said_each_turn(tmp_path, local_service_stub):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    enricher.enrich(identity(), "smalltalk")

    dialog = [item for item in store.engrams if item.type_name == "dialog"]
    assert [item.stated_by for item in dialog] == [
        StatedBy.USER,
        StatedBy.MODEL,
    ]


def test_context_lines_put_user_before_unknown_and_model_stably():
    store = InMemoryStore()
    identity_value = identity()
    model = store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="thread_artifacts",
            content="model first by relevance",
            identity=identity_value,
            namespace="facts",
            stated_by=StatedBy.MODEL,
        ),
    )
    user_first = store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="thread_artifacts",
            content="user first",
            identity=identity_value,
            namespace="facts",
            stated_by=StatedBy.USER,
        ),
    )
    unknown = store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="thread_artifacts",
            content="unknown between users and model",
            identity=identity_value,
            namespace="facts",
        ),
    )
    user_second = store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="thread_artifacts",
            content="user second",
            identity=identity_value,
            namespace="facts",
            stated_by=StatedBy.USER,
        ),
    )
    entity = EntityProfile(
        id=uuid4(),
        kind="project",
        name="entity between unknown and model",
    )

    lines = _lines(
        "thread_artifacts",
        (
            RecallItem("thread_artifacts", 1.0, engram=model),
            RecallItem("thread_artifacts", 0.1, engram=user_first),
            RecallItem("thread_artifacts", 0.2, engram=unknown),
            RecallItem("thread_artifacts", 0.5, entity=entity),
            RecallItem("thread_artifacts", 0.3, engram=user_second),
        ),
    )

    assert [line.text.rsplit(") ", 1)[-1] for line in lines] == [
        "user first",
        "user second",
        "unknown between users and model",
        "[thread_artifacts/entities] entity between unknown and model: {}",
        "model first by relevance",
    ]


def test_context_lines_apply_source_order_to_semantic_and_thread_artifacts_only():
    store = InMemoryStore()
    identity_value = identity()
    for tier in (
        "semantic",
        "thread_artifacts",
        "dialog",
        "delegated",
        "thread_summary",
    ):
        user = store.write(
            Principal.EXTENDED,
            EngramWrite(
                type_name=tier,
                content=f"{tier} user",
                identity=identity_value,
                namespace="thread" if tier == "thread_summary" else "facts",
                stated_by=StatedBy.USER,
            ),
        )
        model = store.write(
            Principal.EXTENDED,
            EngramWrite(
                type_name=tier,
                content=f"{tier} model",
                identity=identity_value,
                namespace="thread" if tier == "thread_summary" else "facts",
                stated_by=StatedBy.MODEL,
            ),
        )

        lines = _lines(
            tier,
            (
                RecallItem(tier, 1.0, engram=model),
                RecallItem(tier, 0.1, engram=user),
            ),
        )

        contents = [line.text.rsplit(") ", 1)[-1] for line in lines]
        expected = (
            [f"{tier} user", f"{tier} model"]
            if tier in {"semantic", "thread_artifacts"}
            else [f"{tier} model", f"{tier} user"]
        )
        assert contents == expected


def test_context_budget_removes_the_same_low_relevance_line_after_reordering():
    store = InMemoryStore()
    identity_value = identity()
    model = store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="thread_artifacts",
            content="model removed by budget",
            identity=identity_value,
            namespace="facts",
            stated_by=StatedBy.MODEL,
        ),
    )
    user = store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="thread_artifacts",
            content="user kept by budget",
            identity=identity_value,
            namespace="facts",
            stated_by=StatedBy.USER,
        ),
    )
    lines = _lines(
        "thread_artifacts",
        (
            RecallItem("thread_artifacts", 0.9, engram=model),
            RecallItem("thread_artifacts", 0.9, engram=user),
        ),
    )

    context = _compose_context(lines, token_budget=40, rag_token_budget=100)

    assert "user kept by budget" in context
    assert "model removed by budget" not in context


def test_model_claim_is_stored_as_model_not_as_user_fact(
    tmp_path,
    local_service_stub,
):
    """El hallazgo del 2026-08-21: una afirmacion del modelo entraba como hecho."""
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    enricher.enrich(identity(), "carpenter-claim")

    thread_artifacts = [item for item in store.engrams if item.type_name == "thread_artifacts"]
    assert len(thread_artifacts) == 1
    assert thread_artifacts[0].stated_by is StatedBy.MODEL


def test_unanchored_attribution_falls_back_to_unknown(
    tmp_path,
    local_service_stub,
):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    enricher.enrich(identity(), "misattributed")

    thread_artifacts = [item for item in store.engrams if item.type_name == "thread_artifacts"]
    assert len(thread_artifacts) == 1
    assert thread_artifacts[0].stated_by is StatedBy.UNKNOWN
    assert _events(tmp_path)[-1]["counters"]["items_unattributed"] == 1


def test_old_single_list_extraction_is_left_unattributed(
    tmp_path,
    local_service_stub,
):
    """El formato antiguo se tolera, pero no se le inventa emisor."""
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    enricher.enrich(identity(), "remember-blue")

    thread_artifacts = [item for item in store.engrams if item.type_name == "thread_artifacts"]
    assert thread_artifacts[0].stated_by is StatedBy.UNKNOWN


def test_user_version_annotates_the_model_claim_without_retiring_it(
    tmp_path,
    local_service_stub,
):
    """Regresion del envenenamiento medido: las dos versiones coexistian mudas.

    Lo que el usuario dice NO retira lo que el modelo afirmo -la separacion
    medida entre contradecir y compartir tema es de centesimas, y no da para
    una accion destructiva-: lo anota, y el recall lo despriorza y lo etiqueta.

    El umbral se baja respecto al de produccion porque el almacen en memoria
    aproxima la banda por solapamiento de palabras, no por coseno de vectores.
    """
    store = InMemoryStore()
    enricher = _enricher(
        tmp_path,
        local_service_stub,
        store,
        conflict_threshold=0.5,
    )

    enricher.enrich(identity(), "carpenter-claim")
    enricher.enrich(
        identity(),
        "carpenter-correction: la pelicula de carpenter si tiene precuela",
    )

    thread_artifacts = [item for item in store.engrams if item.type_name == "thread_artifacts"]
    from_model = [item for item in thread_artifacts if item.stated_by is StatedBy.MODEL]
    from_user = [item for item in thread_artifacts if item.stated_by is StatedBy.USER]

    assert len(from_user) == 1
    assert "si tiene precuela" in from_user[0].content
    assert len(from_model) == 1
    # Sigue vivo y sin archivar; lo unico que cambia es que consta anotado.
    assert from_model[0].status == EngramStatus.ACTIVE
    assert from_model[0].contradicted is True
    assert from_user[0].contradicted is False
    assert _events(tmp_path)[-1]["counters"]["items_contradicted"] == 1


def test_annotated_claim_is_labelled_and_demoted_in_the_context(
    tmp_path,
    local_service_stub,
):
    store = InMemoryStore()
    enricher = _enricher(
        tmp_path,
        local_service_stub,
        store,
        conflict_threshold=0.5,
    )

    enricher.enrich(identity(session="A"), "carpenter-claim")
    enricher.enrich(
        identity(session="A"),
        "carpenter-correction: la pelicula de carpenter si tiene precuela",
    )
    third = enricher.enrich(identity(session="A"), "smalltalk")

    lines = [
        line
        for line in third.context.splitlines()
        if line.startswith("[thread_artifacts/facts]")
    ]
    annotated = [line for line in lines if "version del usuario" in line]

    assert len(annotated) == 1
    assert "no tiene precuela" in annotated[0]
    assert "fuente: modelo, sin verificar" in annotated[0]
    # Despriorizado: el anotado va por detras del resto de su tier.
    assert lines[-1] == annotated[0]


def test_recall_marks_stated_by_in_the_injected_context(
    tmp_path,
    local_service_stub,
):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    enricher.enrich(identity(session="A"), "carpenter-claim")
    second = enricher.enrich(identity(session="A"), "smalltalk")

    # El artefacto que afirmo el modelo viaja marcado como candidato...
    assert (
        "[thread_artifacts/facts] (fuente: modelo, sin verificar) "
        "la pelicula de carpenter no tiene precuela"
    ) in second.context
    # ...y el turno que dijo el usuario, como suyo.
    assert "[dialog/raw] (fuente: usuario) carpenter-claim" in second.context


def test_unconverged_task_does_not_feed_the_memory(tmp_path, local_service_stub):
    """El core publica `stop_reason`; si no acepto su respuesta, no se memoriza.

    Ese dato ya viaja en la respuesta de `task.run`, asi que no es un cambio de
    contrato que pedir al core: es informacion que esta capa tenia sin usar.
    """
    from ianest_extended.enrichment import _downstream_converged

    assert _downstream_converged({"stop_reason": "task_done"}) is True
    assert _downstream_converged({"stop_reason": "max_iterations"}) is False
    assert _downstream_converged({"stop_reason": "replan_unavailable"}) is False
    # `prompt.run` no declara `stop_reason`: sin informacion en contra, pasa.
    assert _downstream_converged({}) is True


def _core_result(stop_reason):
    return CoreResult(
        response="la pelicula de carpenter no tiene precuela",
        trace={"request_id": "core-x"},
        payload={"stop_reason": stop_reason},
    )


def test_unconverged_response_does_not_reach_thread_artifacts(
    tmp_path,
    local_service_stub,
):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    counters, status = enricher.write_back(
        request_id="req-x",
        identity=identity(),
        prompt="carpenter-claim",
        core_result=_core_result("max_iterations"),
    )

    assert status == "ok"
    assert not [i for i in store.engrams if i.type_name == "thread_artifacts"]
    assert counters["items_unconverged"] == 1
    # Los dos turnos siguen en dialog: lo crudo no depende de la convergencia.
    assert len([i for i in store.engrams if i.type_name == "dialog"]) == 2


def test_converged_response_does_reach_thread_artifacts(tmp_path, local_service_stub):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    counters, _ = enricher.write_back(
        request_id="req-y",
        identity=identity(),
        prompt="carpenter-claim",
        core_result=_core_result("task_done"),
    )

    thread_artifacts = [i for i in store.engrams if i.type_name == "thread_artifacts"]
    assert [item.stated_by for item in thread_artifacts] == [StatedBy.MODEL]
    assert counters["items_unconverged"] == 0


def test_parse_extraction_tolerates_real_qwen_output_defects():
    copied_confidence = (
        '{"items":[{"namespace":"preferences","content":'
        '"mi color favorito es el verde","confidence":0.0,"mentions":[]}]}'
    )
    copied_namespace = (
        '{"items":[{"namespace":"facts|preferences","content":'
        '"trabajo con openSUSE","confidence":0.9,"mentions":["openSUSE"]}]}'
    )
    fenced_with_trailing_text = (
        '```json\n{"items":[{"namespace":"facts","content":'
        '"trabajo con openSUSE","confidence":0.9,"mentions":["openSUSE"]}]}\n'
        "```\nTexto colgante."
    )

    low_confidence_item = _parse_extraction(copied_confidence)[0][1]
    invalid_namespace_item = _parse_extraction(copied_namespace)[0][1]
    fenced_item = _parse_extraction(fenced_with_trailing_text)[0][1]

    assert _validate_item(low_confidence_item)["confidence"] == 0.0
    assert _validate_item(invalid_namespace_item) is None
    assert _validate_item(fenced_item) == {
        "namespace": "facts",
        "content": "trabajo con openSUSE",
        "confidence": 0.9,
        "mentions": ("openSUSE",),
    }
