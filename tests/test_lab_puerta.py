"""Criterios falsables del script de puerta de laboratorio."""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).parents[1] / "tools" / "lab" / "puerta.py"
SPEC = importlib.util.spec_from_file_location("lab_puerta", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
puerta = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = puerta
SPEC.loader.exec_module(puerta)


@pytest.fixture
def gate_stub():
    state = SimpleNamespace(
        requests=[],
        version="0.2.1",
        l4a_fail_on=set(),
        l4a_count=0,
        l4b_fail=False,
        l2_answer_contains_witness=True,
        l2_recall_contains_witness=True,
        l2_witnesses={},
        corrections_by_user={},
        l3_annotation=True,
        l3_model_label=True,
        l3_model_first=False,
        l5_empty_domains=set(),
        l5_hide_corpus_names=False,
        l5r_noise=False,
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def _send(self, payload, status=200):
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            state.requests.append(
                (self.command, self.path, None, self.headers.get("X-IA-NEST-Lab-User-Id"))
            )
            if self.path == "/capability/list":
                capabilities = [
                    {"name": name} for name in sorted(puerta.OWN_CAPABILITIES)
                ]
                self._send(
                    {
                        "extended_version": state.version,
                        "core_version": "0.4.0",
                        "capabilities": capabilities,
                    }
                )
                return
            if self.path == "/knowledge/status":
                self._send({"domains": []})
                return
            self._send({"error": "not found"}, 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            state.requests.append(
                (self.command, self.path, payload, self.headers.get("X-IA-NEST-Lab-User-Id"))
            )
            if self.path == "/memory/write":
                identity = payload["request"]["identity"]
                user_id = identity["user_id"]
                incorrect = payload["request"]["content"].split()[-1].rstrip(".")
                state.corrections_by_user.setdefault(user_id, []).append(
                    {"incorrect": incorrect}
                )
                self._send(
                    {
                        "id": "00000000-0000-0000-0000-000000000001",
                        "type_name": "episodic",
                        "namespace": "facts",
                        "status": "active",
                        "stated_by": "model",
                    }
                )
                return
            if self.path == "/prompt/run":
                self._prompt_run(payload)
                return
            if self.path == "/memory/recall":
                self._recall(payload)
                return
            self._send({"error": "not found"}, 404)

        def _prompt_run(self, payload):
            prompt = payload["prompt"]
            user_id = payload["identity"]["user_id"]
            if prompt.startswith("Mi perro se llama "):
                witness = prompt.split()[4].rstrip(".")
                state.l2_witnesses[payload["identity"]["user_id"]] = witness
                self._send({"response": "OK"})
                return
            if prompt.startswith("Como se llama mi perro"):
                witness = state.l2_witnesses[payload["identity"]["user_id"]]
                answer = witness if state.l2_answer_contains_witness else "Xanthe"
                self._send({"response": answer})
                return
            if prompt.startswith("La clave del refugio es Ambar"):
                correct = prompt.split()[-1].rstrip(".")
                state.corrections_by_user[user_id][-1]["correct"] = correct
                self._send({"response": "OK"})
                return
            if prompt.startswith("Cual es la clave del refugio"):
                state.l4a_count += 1
                witnesses = state.corrections_by_user[user_id][-1]
                answer = (
                    witnesses["incorrect"]
                    if state.l4a_count in state.l4a_fail_on
                    else witnesses["correct"]
                )
                self._send({"response": answer})
                return
            if prompt.startswith("Que dia es la reunion"):
                self._send({"response": "martes" if state.l4b_fail else "jueves"})
                return
            self._send({"response": "OK"})

        def _recall(self, payload):
            prompt = payload["prompt"]
            identity = payload["identity"]
            user_id = identity["user_id"]
            if payload.get("use_rag") and not payload.get("use_memory"):
                domain = identity.get("domain_tag")
                if domain is not None:
                    if domain in state.l5_empty_domains:
                        self._send({"context": "", "counters": {"rag": 0}})
                    else:
                        context = (
                            f"fragmento relevante de {domain}"
                            if state.l5_hide_corpus_names
                            else (
                                f"[corpus-{domain}/{domain}/guide.md#0] "
                                f"fragmento relevante de {domain}"
                            )
                        )
                        self._send(
                            {
                                "context": context,
                                "counters": {"rag": 1},
                            }
                        )
                    return
                if state.l5r_noise:
                    self._send(
                        {
                            "context": "[corpus-ruido/global/noise.md#0] ruido",
                            "counters": {"rag": 1},
                        }
                    )
                else:
                    self._send({"context": "", "counters": {"rag": 0}})
                return
            if "perro" in prompt:
                witness = state.l2_witnesses[user_id]
                if not state.l2_recall_contains_witness:
                    self._send({"context": "", "counters": {"episodic": 0}})
                    return
                self._send(
                    {
                        "context": f"[episodic/facts] (fuente: usuario) Mi perro se llama {witness}.",
                        "counters": {"episodic": 1},
                    }
                )
                return
            corrections = state.corrections_by_user[user_id]
            context_lines = []
            for witnesses in reversed(corrections):
                user_line = (
                    "[episodic/tasks] (fuente: usuario) La clave del refugio es "
                    f"{witnesses['correct']}."
                )
                model_source = (
                    "fuente: modelo, sin verificar"
                    if state.l3_model_label
                    else "fuente: no registrada"
                )
                annotation = (
                    "; hay una version del usuario sobre esto"
                    if state.l3_annotation
                    else ""
                )
                model_line = (
                    f"[episodic/facts] ({model_source}{annotation}) "
                    f"La clave del refugio es {witnesses['incorrect']}."
                )
                pair = (
                    [model_line, user_line]
                    if state.l3_model_first
                    else [user_line, model_line]
                )
                context_lines.extend(pair)
            self._send(
                {
                    "context": "\n".join(context_lines),
                    "counters": {"episodic": len(context_lines)},
                }
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        state.base_url = f"http://127.0.0.1:{server.server_port}"
        yield state
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _systemctl_ok(*args, **kwargs):
    return subprocess.CompletedProcess(
        args=args[0],
        returncode=0,
        stdout="2026-09-12T11:00:00+02:00\n",
        stderr="",
    )


def _argv(stub, tmp_path, *, repetitions=3):
    return [
        "--url",
        stub.base_url,
        "--tag",
        "v0.2.1",
        "--instalado",
        "2026-09-12T10:00:00+02:00",
        "--core-smoke-pasa",
        "--parametros-huella",
        "sha256:abc",
        "--setup-exit-code",
        "0",
        "--n",
        str(repetitions),
        "--json",
        str(tmp_path / "evidence.json"),
    ]


def _run(stub, tmp_path, capsys, *, repetitions=3):
    code = puerta.main(
        _argv(stub, tmp_path, repetitions=repetitions),
        systemctl_run=_systemctl_ok,
    )
    output = capsys.readouterr().out
    report = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    return code, output, report


def _line(report, name):
    return next(item for item in report["lines"] if item["line"] == name)


def test_green_verdict_executes_all_executable_lines(gate_stub, tmp_path, capsys):
    code, output, report = _run(gate_stub, tmp_path, capsys)

    assert code == 0
    assert report["verdict"] == "PASA"
    assert all(
        _line(report, name)["verdict"] == "PASA"
        for name in ("L1", "L2", "L3", "L4a", "L4b", "L5", "L5r")
    )
    assert "VEREDICTO: PASA (codigo 0)" in output


def test_l2_passes_by_recall_when_answer_omits_witness(gate_stub, tmp_path, capsys):
    gate_stub.l2_answer_contains_witness = False

    code, _, report = _run(gate_stub, tmp_path, capsys, repetitions=1)

    attempt = _line(report, "L2")["attempts"][0]
    assert code == 0
    assert attempt["verdict"] == "PASA"
    assert attempt["checks"]["answer_contains_witness"] is False
    assert attempt["checks"]["recall_contains_witness_stated_by_user"] is True
    assert "answer" in attempt
    assert "recall" in attempt


def test_l2_fails_without_recall_even_when_answer_has_witness(
    gate_stub, tmp_path, capsys
):
    gate_stub.l2_recall_contains_witness = False

    code, _, report = _run(gate_stub, tmp_path, capsys, repetitions=1)

    attempt = _line(report, "L2")["attempts"][0]
    assert code == 1
    assert attempt["verdict"] == "NO PASA"
    assert attempt["checks"]["answer_contains_witness"] is True
    assert attempt["checks"]["recall_contains_witness_stated_by_user"] is False


def test_l3_passes_without_annotation_and_reports_its_rate(
    gate_stub, tmp_path, capsys
):
    gate_stub.l3_annotation = False

    code, output, report = _run(gate_stub, tmp_path, capsys, repetitions=1)

    line = _line(report, "L3")
    assert code == 0
    assert line["verdict"] == "PASA"
    assert line["attempts"][0]["checks"]["model_label"] is True
    assert (
        line["attempts"][0]["checks"]["user_version_before_model_version"]
        is True
    )
    assert line["attempts"][0]["checks"]["contradicted_by_annotation"] is False
    assert line["annotation"] == {"observed": 0, "total": 1, "rate": "0/1"}
    assert "L3: PASA 1/1 (anotacion 0/1)" in output


@pytest.mark.parametrize("failure", ["label", "order"])
def test_l3_still_fails_without_model_label_or_user_first(
    gate_stub, tmp_path, capsys, failure
):
    if failure == "label":
        gate_stub.l3_model_label = False
    else:
        gate_stub.l3_model_first = True

    code, _, report = _run(gate_stub, tmp_path, capsys, repetitions=1)

    assert code == 1
    assert _line(report, "L3")["verdict"] == "NO PASA"


def test_l4a_does_not_block_when_the_composed_context_was_correct(
    gate_stub, tmp_path, capsys
):
    """Reconciliado el 2026-09-22: L4a bloquea por composicion, no por obediencia.

    El doble compone el contexto bien -version del usuario primero y etiquetada-
    y aun asi responde el testigo del modelo. Eso es infidelidad del modelo, que
    la puerta declara fuera de su cobertura: se registra y no suspende.
    """
    gate_stub.l4a_fail_on = {1, 2, 3}

    code, output, report = _run(gate_stub, tmp_path, capsys)

    line = _line(report, "L4a")
    assert code == 0
    assert line["verdict"] == "PASA"
    assert line["composition_failures"] == 0
    assert line["model_unfaithful"]["rate"] == "3/3"
    assert line["attempts"][0]["verdict"] == "INFIDELIDAD DEL MODELO"
    assert line["attempts"][0]["checks"]["composition_correct"] is True
    assert "infidelidad del modelo 3/3" in output
    # La evidencia de la respuesta equivocada se conserva igual que antes.
    assert line["attempts"][0]["incorrect_witness"] in line["attempts"][0]["final_answer"]


def test_l4a_blocks_when_the_composed_context_was_wrong(gate_stub, tmp_path, capsys):
    """Y sigue suspendiendo cuando el fallo SI es de la capa."""
    gate_stub.l4a_fail_on = {1, 2, 3}
    gate_stub.l3_model_first = True

    code, output, report = _run(gate_stub, tmp_path, capsys)

    line = _line(report, "L4a")
    assert code == 1
    assert line["verdict"] == "NO PASA"
    assert line["composition_failures"] == 3
    assert line["model_unfaithful"]["rate"] == "0/3"
    assert line["attempts"][0]["checks"]["composition_correct"] is False
    assert "L4a: NO PASA" in output


def test_version_mismatch_is_null_and_executes_no_line(gate_stub, tmp_path, capsys):
    gate_stub.version = "0.1.0"

    code, output, report = _run(gate_stub, tmp_path, capsys)

    assert code == 2
    assert report["lines"] == []
    assert [request[1] for request in gate_stub.requests] == ["/capability/list"]
    assert "LINEAS: no ejecutadas" in output


def test_l4b_does_not_decide_exit_code(gate_stub, tmp_path, capsys):
    gate_stub.l4b_fail = True

    code, output, report = _run(gate_stub, tmp_path, capsys)

    assert code == 0
    assert _line(report, "L4b")["verdict"] == "NO PASA"
    assert _line(report, "L4b")["blocking"] is False
    assert "brazo sin sintesis de Fase 9; no bloquea" in output


def test_repetition_requires_n_of_n(gate_stub, tmp_path, capsys):
    """Una linea PASA con n de n: una sola repeticion mala la suspende.

    Se rompe la composicion para que el fallo sea atribuible a la capa; eso
    tumba tambien a L3, que mide lo mismo, y aqui solo se afirma sobre L4a.
    """
    gate_stub.l4a_fail_on = {2}
    gate_stub.l3_model_first = True

    code, output, report = _run(gate_stub, tmp_path, capsys)

    line = _line(report, "L4a")
    assert code == 1
    assert (line["passed"], line["total"], line["verdict"]) == (2, 3, "NO PASA")
    assert line["composition_failures"] == 1
    assert "L4a: NO PASA 2/3" in output


def test_requests_have_run_identity_and_runs_use_distinct_users(gate_stub, tmp_path, capsys):
    _, _, first = _run(gate_stub, tmp_path / "one", capsys, repetitions=1)
    first_request_count = len(gate_stub.requests)
    _, _, second = _run(gate_stub, tmp_path / "two", capsys, repetitions=1)

    assert first["user_id_prefix"].startswith(f"puerta-{first['run_id']}-")
    assert second["user_id_prefix"].startswith(f"puerta-{second['run_id']}-")
    assert first["user_id_prefix"] != second["user_id_prefix"]
    first_requests = gate_stub.requests[:first_request_count]
    second_requests = gate_stub.requests[first_request_count:]
    assert all(item[3].startswith(first["user_id_prefix"]) for item in first_requests)
    assert all(item[3].startswith(second["user_id_prefix"]) for item in second_requests)
    for _, _, payload, header_user_id in gate_stub.requests:
        if payload is None:
            continue
        identity = payload.get("identity") or payload.get("request", {}).get("identity")
        assert identity["user_id"] == header_user_id

    probe_users = {
        attempt["user_id"]
        for name in ("L2", "L3", "L4a", "L4b", "L5", "L5r")
        for attempt in _line(first, name)["attempts"]
    }
    assert len(probe_users) == 8
    assert all(user_id.startswith(first["user_id_prefix"]) for user_id in probe_users)


def test_probe_contexts_do_not_contain_other_probe_witnesses(gate_stub, tmp_path, capsys):
    _, _, report = _run(gate_stub, tmp_path, capsys, repetitions=3)

    correction_attempts = [
        attempt
        for name in ("L3", "L4a")
        for attempt in _line(report, name)["attempts"]
    ]
    all_witnesses = {
        attempt[key]
        for attempt in correction_attempts
        for key in ("correct_witness", "incorrect_witness")
    }
    for attempt in correction_attempts:
        own = {attempt["correct_witness"], attempt["incorrect_witness"]}
        context = attempt["recall"]["context"]
        assert own <= {witness for witness in all_witnesses if witness in context}
        assert not any(witness in context for witness in all_witnesses - own)


def test_witnesses_have_no_cut_point_and_full_literal_is_required(
    gate_stub, tmp_path, capsys
):
    _, _, report = _run(gate_stub, tmp_path, capsys, repetitions=1)

    witnesses = [_line(report, "L2")["attempts"][0]["witness"]]
    for name in ("L3", "L4a"):
        attempt = _line(report, name)["attempts"][0]
        witnesses.extend((attempt["correct_witness"], attempt["incorrect_witness"]))
    assert all(witness.isalnum() for witness in witnesses)
    assert all(not puerta._contains(witness[:-1], witness) for witness in witnesses)


def test_l5_fails_when_a_domain_returns_no_fragment(gate_stub, tmp_path, capsys):
    gate_stub.l5_empty_domains = {"agricultura"}
    code, output, report = _run(gate_stub, tmp_path, capsys, repetitions=3)

    line = _line(report, "L5")
    assert code == 1
    assert (line["passed"], line["total"], line["verdict"]) == (0, 3, "NO PASA")
    failed_probe = next(
        probe
        for probe in line["attempts"][0]["probes"]
        if probe["domain"] == "agricultura"
    )
    assert failed_probe["k_returned"] == 0
    assert failed_probe["score"] is None
    assert "L5: NO PASA 0/3" in output


def test_l5_uses_the_five_fixed_probes_literally(gate_stub, tmp_path, capsys):
    _run(gate_stub, tmp_path, capsys, repetitions=1)

    rag_requests = [
        payload
        for _, path, payload, _ in gate_stub.requests
        if path == "/memory/recall"
        and payload.get("use_rag") is True
        and payload["identity"].get("domain_tag") is not None
    ]
    assert [
        (payload["identity"]["domain_tag"], payload["prompt"])
        for payload in rag_requests
    ] == list(puerta.L5_PROBES)


def test_l5r_fails_when_courtesy_retrieves_noise(gate_stub, tmp_path, capsys):
    gate_stub.l5r_noise = True
    code, _, report = _run(gate_stub, tmp_path, capsys, repetitions=1)

    assert code == 1
    assert _line(report, "L5r")["verdict"] == "NO PASA"
    assert all(attempt["k_returned"] == 1 for attempt in _line(report, "L5r")["attempts"])


def test_rest_corpus_identity_limit_is_explicit_in_output_and_json(
    gate_stub, tmp_path, capsys
):
    code, output, report = _run(gate_stub, tmp_path, capsys, repetitions=1)

    assert code == 0
    assert report["rest_observability"]["corpus_identity_verifiable"] is True
    assert "los nombres se publican en context de memory.recall" in output
    assert report["rest_observability"]["rag_score_verifiable"] is False
    assert "la puntuacion no se publica por REST" in output


def test_unpublished_corpus_identity_is_declared_without_hiding_retrieval(
    gate_stub, tmp_path, capsys
):
    gate_stub.l5_hide_corpus_names = True
    code, output, report = _run(gate_stub, tmp_path, capsys, repetitions=1)

    assert code == 0
    assert _line(report, "L5")["verdict"] == "PASA"
    assert report["rest_observability"]["corpus_identity_verifiable"] is False
    assert "la identidad del corpus no se comprueba por REST" in output
    assert all(
        probe["k_returned"] == 1 and probe["recovered_corpora"] == []
        for probe in _line(report, "L5")["attempts"][0]["probes"]
    )


def test_progress_reports_every_probe_before_the_unchanged_summary(
    gate_stub, tmp_path, capsys
):
    _, output, _ = _run(gate_stub, tmp_path, capsys, repetitions=1)

    output_lines = output.splitlines()
    summary_index = output_lines.index("LO QUE LA PUERTA NO CUBRE")
    progress = output_lines[:summary_index]
    assert len(progress) == 13
    assert all(line.startswith("PROGRESO ") for line in progress)
    assert "PROGRESO L1 repeticion 1: PASA" in progress
    assert "PROGRESO L5 repeticion 1 agricultura: PASA" in progress
    assert "PROGRESO L5r repeticion 3: PASA" in progress
    assert "VEREDICTO: PASA (codigo 0)" in output_lines[summary_index:]
    assert "L6: FUERA DEL SCRIPT" in output_lines[summary_index:]


def test_script_imports_only_standard_library():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    assert imported <= set(puerta.sys.stdlib_module_names)
