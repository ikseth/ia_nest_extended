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
        version="0.2.0",
        l4a_fail_on=set(),
        l4a_count=0,
        l4b_fail=False,
        l2_witnesses={},
        l3_by_session={},
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
                session = identity["session_id"]
                incorrect = payload["request"]["content"].split()[-1].rstrip(".")
                state.l3_by_session[session] = {"incorrect": incorrect}
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
            session = payload["identity"]["session_id"]
            if prompt.startswith("Mi perro se llama "):
                witness = prompt.split()[4].rstrip(".")
                state.l2_witnesses[payload["identity"]["user_id"]] = witness
                self._send({"response": "OK"})
                return
            if prompt.startswith("Como se llama mi perro"):
                witness = state.l2_witnesses[payload["identity"]["user_id"]]
                self._send({"response": witness})
                return
            if prompt.startswith("La clave del refugio es Ambar-"):
                correct = prompt.split()[-1].rstrip(".")
                state.l3_by_session[session]["correct"] = correct
                self._send({"response": "OK"})
                return
            if prompt.startswith("Cual es la clave del refugio"):
                state.l4a_count += 1
                witnesses = state.l3_by_session[session]
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
            session = payload["identity"]["session_id"]
            if "perro" in prompt:
                witness = state.l2_witnesses[payload["identity"]["user_id"]]
                self._send(
                    {
                        "context": f"[episodic/facts] (fuente: usuario) Mi perro se llama {witness}.",
                        "counters": {"episodic": 1},
                    }
                )
                return
            witnesses = state.l3_by_session[session]
            self._send(
                {
                    "context": (
                        "[episodic/facts] (fuente: usuario) La clave del refugio es "
                        f"{witnesses['correct']}.\n"
                        "[episodic/facts] (fuente: modelo, sin verificar; "
                        "hay una version del usuario sobre esto) La clave del refugio es "
                        f"{witnesses['incorrect']}."
                    ),
                    "counters": {"episodic": 2},
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
        "v0.2.0",
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
    assert all(_line(report, name)["verdict"] == "PASA" for name in ("L1", "L2", "L3", "L4a", "L4b"))
    assert "VEREDICTO: PASA (codigo 0)" in output


def test_red_verdict_keeps_wrong_l4a_evidence(gate_stub, tmp_path, capsys):
    gate_stub.l4a_fail_on = {1, 2, 3}

    code, output, report = _run(gate_stub, tmp_path, capsys)

    line = _line(report, "L4a")
    assert code == 1
    assert line["verdict"] == "NO PASA"
    assert line["attempts"][0]["incorrect_witness"] in line["attempts"][0]["final_answer"]
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
    gate_stub.l4a_fail_on = {2}

    code, output, report = _run(gate_stub, tmp_path, capsys)

    line = _line(report, "L4a")
    assert code == 1
    assert (line["passed"], line["total"], line["verdict"]) == (2, 3, "NO PASA")
    assert "L4a: NO PASA 2/3" in output


def test_requests_have_run_identity_and_runs_use_distinct_users(gate_stub, tmp_path, capsys):
    _, _, first = _run(gate_stub, tmp_path / "one", capsys, repetitions=1)
    first_request_count = len(gate_stub.requests)
    _, _, second = _run(gate_stub, tmp_path / "two", capsys, repetitions=1)

    assert first["user_id"].startswith("puerta-")
    assert second["user_id"].startswith("puerta-")
    assert first["user_id"] != second["user_id"]
    first_requests = gate_stub.requests[:first_request_count]
    second_requests = gate_stub.requests[first_request_count:]
    assert {item[3] for item in first_requests} == {first["user_id"]}
    assert {item[3] for item in second_requests} == {second["user_id"]}
    for _, _, payload, _ in gate_stub.requests:
        if payload is None:
            continue
        identity = payload.get("identity") or payload.get("request", {}).get("identity")
        assert identity["user_id"].startswith("puerta-")


def test_l5_and_l5r_are_declared_not_executable(gate_stub, tmp_path, capsys):
    code, _, report = _run(gate_stub, tmp_path, capsys, repetitions=1)

    assert code == 0
    assert _line(report, "L5")["verdict"] == "NO EJECUTABLE"
    assert _line(report, "L5r")["verdict"] == "NO EJECUTABLE"
    assert not any("rag" in request[1] for request in gate_stub.requests)


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
