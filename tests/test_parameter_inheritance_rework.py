"""Retrabajo de herencia de parametros: flujo REAL, no funciones aisladas.

Contexto (docs/handoff/herencia_parametros_retrabajo.md): la suite anterior
pasaba 104 pruebas en verde y aun asi el CLI abortaba en cuanto el core era
alcanzable, con

    argparse.ArgumentError: argument --domain: conflicting option string: --domain

porque la unica prueba de construccion del parser llamaba a `_build_parser()`
sin argumentos -el camino puramente local- y nunca al `cli.main` real contra
un catalogo remoto que declarase un parametro con el mismo nombre que una
bandera propia. Este modulo cierra ese hueco: invoca `cli.main` de punta a
punta contra un stub HTTP ALCANZABLE, como pide el retrabajo.

Se usa un parametro llamado 'namespace' -no 'domain'- para demostrar que la
regla de colision es UNA sola derivada del dato, no una lista de casos.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from ianest_extended import cli
from ianest_extended.catalog_cache import write_catalog_cache

UNREACHABLE = "http://127.0.0.1:1"
CLOSED_DSN = "postgresql://ianest:local@127.0.0.1:1/ianest_extended"

# Declaracion ajena (como la publicaria el core): 'namespace' colisiona con la
# bandera de identidad que esta capa ya posee; 'mode' no colisiona con nada.
WIDGET_CAPABILITY = {
    "name": "widget.inspect",
    "summary": "inspecciona un widget (stub de pruebas)",
    "identity": True,
    "streaming": False,
    "params": [
        {
            "name": "namespace",
            "type": "string",
            "required": False,
            "choices": None,
            "default": None,
            "summary": "espacio del widget segun el core",
            "metavar": "ESPACIO",
        },
        {
            "name": "mode",
            "type": "string",
            "required": True,
            "choices": ["fast", "safe"],
            "default": None,
            "summary": "modo de inspeccion",
            "metavar": "MODO",
        },
    ],
    "rest": {"path": "/widget/inspect", "method": "POST"},
    "cli": {
        "group": "widget",
        "action": "inspect",
        "description": "Inspecciona un widget del core (stub de pruebas).",
    },
    "mcp": None,
}


@pytest.fixture
def widget_stub():
    """Core stub ALCANZABLE: catalogo con colision, mas /widget/inspect y /prompt/run."""
    state = SimpleNamespace(capability_list_requests=0, requests=[])

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/capability/list":
                state.capability_list_requests += 1
                self._send(
                    {"core_version": "9.9.9", "capabilities": [WIDGET_CAPABILITY]}
                )
                return
            self.send_error(404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length)) if length else {}
            state.requests.append((self.path, payload))
            if self.path == "/widget/inspect":
                self._send({"ok": True, "echoed": payload})
                return
            if self.path == "/prompt/run":
                self._send(
                    {
                        "response": f"echo:{payload.get('prompt')}",
                        "trace": {
                            "request_id": "widget-prompt-1",
                            "finish_reason": "stop",
                        },
                    }
                )
                return
            self.send_error(404)

        def log_message(self, format, *args):
            return

        def _send(self, payload, status=200):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _cli_env(monkeypatch, tmp_path, core_url, *, cache_path=None):
    monkeypatch.setenv("IANEST_EXTENDED_CORE_URL", core_url)
    monkeypatch.setenv("IANEST_EXTENDED_OLLAMA_URL", UNREACHABLE)
    monkeypatch.setenv("IANEST_EXTENDED_DATABASE_DSN", CLOSED_DSN)
    monkeypatch.setenv("IANEST_EXTENDED_TELEMETRY_DIR", str(tmp_path))
    monkeypatch.setenv(
        "IANEST_EXTENDED_SESSION_STATE_PATH", str(tmp_path / "session_id")
    )
    monkeypatch.setenv(
        "IANEST_EXTENDED_CATALOG_CACHE_PATH",
        str(cache_path or tmp_path / "catalog_cache.json"),
    )
    monkeypatch.setenv("IANEST_EXTENDED_EMBEDDING_DIMENSION", "2")
    return ["--env-file", str(tmp_path / "ausente.env")]


# --- criterios 1-3: la colision no aborta, y es una regla generica ---------


def test_collision_does_not_abort_the_cli_and_the_layer_flag_wins(
    monkeypatch, tmp_path, capsys, widget_stub
):
    """Criterios 1-3 del retrabajo, reproduciendo el modo de fallo real.

    Antes del arreglo esto abortaba la construccion ENTERA del parser -
    incluidos los comandos propios- con argparse.ArgumentError en cuanto el
    core era alcanzable. Se elige 'namespace' -no 'domain'- para demostrar
    que la regla no es una lista de excepciones escrita a mano.
    """
    argv = _cli_env(monkeypatch, tmp_path, widget_stub.base_url)

    # Unica via de refresco: capability list consulta el core y actualiza
    # la cache.
    assert cli.main([*argv, "capability", "list", "--json"]) == 0
    assert widget_stub.capability_list_requests == 1

    # Un comando PROPIO sigue funcionando con el core alcanzable y la
    # colision presente en el catalogo fusionado.
    assert (
        cli.main([*argv, "prompt", "run", "--prompt", "hola", "--no-enrich"]) == 0
    )

    # La capacidad reenviada conserva 'mode' (sin colision) y NO redeclara
    # 'namespace': la gobierna la bandera propia de identidad.
    code = cli.main(
        [*argv, "widget", "inspect", "--mode", "fast", "--namespace", "equipo-x", "--json"]
    )
    capsys.readouterr()
    assert code == 0

    path, payload = widget_stub.requests[-1]
    assert path == "/widget/inspect"
    assert payload["mode"] == "fast"
    # Un unico origen de verdad: el valor de la bandera propia llega una
    # vez, tanto al campo declarado por el catalogo como a la identidad.
    assert payload["namespace"] == "equipo-x"
    assert payload["identity"]["namespace"] == "equipo-x"


def test_forwarded_help_explains_the_governed_parameter(
    monkeypatch, tmp_path, capsys, widget_stub
):
    """La ayuda dice que 'namespace' lo gobierna la bandera de la capa."""
    argv = _cli_env(monkeypatch, tmp_path, widget_stub.base_url)
    assert cli.main([*argv, "capability", "list", "--json"]) == 0
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc_info:
        cli.main([*argv, "widget", "inspect", "--help"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "--namespace" in captured.out
    assert "gobierna la bandera propia de la capa" in captured.out


# --- criterio 4: construir el parser jamas toca la red ----------------------


def test_parser_construction_never_touches_the_network(
    monkeypatch, tmp_path, capsys, widget_stub
):
    """Criterio 4: analizar argumentos no pide el catalogo, ni alcanzable.

    Se refresca la cache UNA vez -via legitima, capability list- y despues
    se ejercen varios comandos. Ninguno debe volver a golpear
    /capability/list: el parser se construye siempre desde la cache local.
    """
    argv = _cli_env(monkeypatch, tmp_path, widget_stub.base_url)
    assert cli.main([*argv, "capability", "list", "--json"]) == 0
    assert widget_stub.capability_list_requests == 1

    cli.main([*argv, "widget", "inspect", "--mode", "fast", "--json"])
    cli.main([*argv, "prompt", "run", "--prompt", "hola", "--no-enrich"])
    with pytest.raises(SystemExit):
        cli.main([*argv, "--help"])
    with pytest.raises(SystemExit):
        cli.main([*argv, "widget", "inspect", "--help"])
    capsys.readouterr()

    assert widget_stub.capability_list_requests == 1


# --- criterios 6-7: la cache se usa, y solo si es del core configurado -----


def test_cache_is_used_when_core_is_unreachable(monkeypatch, tmp_path):
    """Criterio 6: cache presente, core caido -> se conservan las banderas.

    La invocacion falla, pero HONESTAMENTE porque el core esta caido -exit
    1, error tipado-, nunca porque argparse no reconociera '--mode' -exit 2-.
    """
    cache_path = tmp_path / "catalog_cache.json"
    write_catalog_cache(
        cache_path,
        core_url=UNREACHABLE,
        core_version="9.9.9",
        capabilities=[WIDGET_CAPABILITY],
    )
    argv = _cli_env(monkeypatch, tmp_path, UNREACHABLE, cache_path=cache_path)

    code = cli.main([*argv, "widget", "inspect", "--mode", "fast", "--json"])

    assert code == 1


def test_cache_of_a_different_core_is_ignored(monkeypatch, tmp_path, capsys, widget_stub):
    """Criterio 7: cache de otro origen se ignora; degrada a --param."""
    cache_path = tmp_path / "catalog_cache.json"
    write_catalog_cache(
        cache_path,
        core_url="http://127.0.0.1:9",  # origen distinto del configurado
        core_version="9.9.9",
        capabilities=[WIDGET_CAPABILITY],
    )
    argv = _cli_env(monkeypatch, tmp_path, widget_stub.base_url, cache_path=cache_path)

    # La bandera tipada NO existe: la cache se ignoro por origen distinto.
    with pytest.raises(SystemExit) as exc_info:
        cli.main([*argv, "widget", "inspect", "--mode", "fast"])
    assert exc_info.value.code == 2

    # Pero la capacidad sigue invocable por el escape generico.
    code = cli.main([*argv, "widget", "inspect", "--param", "mode=fast", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    path, payload = widget_stub.requests[-1]
    assert path == "/widget/inspect"
    assert payload["mode"] == "fast"


# --- criterio 8: sin cache y sin core, nada aborta --------------------------


def test_no_cache_and_no_core_degrades_without_aborting(monkeypatch, tmp_path):
    """Criterio 8: propias conservan banderas; lo ajeno via --param; nada aborta."""
    argv = _cli_env(
        monkeypatch,
        tmp_path,
        UNREACHABLE,
        cache_path=tmp_path / "no_existe" / "catalog_cache.json",
    )

    # Propia: tipada y con sus banderas; falla honesto porque el core cae.
    assert cli.main([*argv, "prompt", "run", "--prompt", "hola", "--no-enrich"]) == 1

    # Ajena y desconocida: se resuelve via --param; tambien honesto.
    assert cli.main([*argv, "future", "inspect", "--param", "x=1"]) == 1


# --- criterio 9 / brief 5-7: entrada de fichero, colision, --param ---------


def test_cli_plan_file_fills_multiple_parameters_from_one_json_file(
    monkeypatch, tmp_path, local_service_stub
):
    """Brief criterio 5, via flujo real: un fichero rellena varios parametros."""
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub.base_url)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "plan": [
                    {
                        "index": 0,
                        "prompt": "paso operador",
                        "domain": "general",
                        "depends_on": [],
                    }
                ],
                "requirements": [
                    {"id": "r1", "statement": "cumplir", "covered_by": [0]}
                ],
                "effort": "low",
            }
        ),
        encoding="utf-8",
    )

    code = cli.main(
        [
            *argv,
            "task",
            "run",
            "--prompt",
            "tarea",
            "--plan-file",
            str(plan_path),
            "--no-enrich",
            "--json",
        ]
    )

    assert code == 0
    path, payload = local_service_stub.requests[-1]
    assert path == "/task/run"
    assert payload["plan"][0]["prompt"] == "paso operador"
    assert payload["requirements"] == [
        {"id": "r1", "statement": "cumplir", "covered_by": [0]}
    ]
    assert payload["effort"] == "low"


def test_cli_plan_file_and_explicit_effort_collide(
    monkeypatch, tmp_path, capsys, local_service_stub
):
    """Brief criterio 6: fichero y bandera sobre el mismo parametro, error tipado."""
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub.base_url)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({"plan": [], "requirements": [], "effort": "low"}),
        encoding="utf-8",
    )

    code = cli.main(
        [
            *argv,
            "task",
            "run",
            "--prompt",
            "tarea",
            "--plan-file",
            str(plan_path),
            "--effort",
            "high",
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "effort" in captured.err


def test_param_escape_works_for_undeclared_fields(monkeypatch, tmp_path, widget_stub):
    """Brief criterio 7 (parte 1): --param sigue funcionando para lo no declarado."""
    argv = _cli_env(monkeypatch, tmp_path, widget_stub.base_url)
    assert cli.main([*argv, "capability", "list", "--json"]) == 0

    code = cli.main(
        [*argv, "widget", "inspect", "--mode", "fast", "--param", "extra=uno", "--json"]
    )

    assert code == 0
    path, payload = widget_stub.requests[-1]
    assert payload["mode"] == "fast"
    assert payload["extra"] == "uno"


def test_param_colliding_with_a_declared_flag_is_a_typed_error(
    monkeypatch, tmp_path, capsys, widget_stub
):
    """Brief criterio 7 (parte 2): --param sobre una bandera declarada, error tipado."""
    argv = _cli_env(monkeypatch, tmp_path, widget_stub.base_url)
    assert cli.main([*argv, "capability", "list", "--json"]) == 0

    code = cli.main(
        [*argv, "widget", "inspect", "--mode", "fast", "--param", "mode=other"]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "mode" in captured.err
