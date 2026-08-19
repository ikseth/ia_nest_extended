import os
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest


@pytest.fixture
def local_service_stub():
    state = SimpleNamespace(
        requests=[],
        counter=0,
        stream_gate=None,
        stream_events=(
            ("token", '{"chunk": "uno"}'),
            ("token", '{"chunk": "dos"}'),
            ("done", '{"stop_reason": "stop"}'),
        ),
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state.requests.append((self.path, None))
            if self.path == "/capability/list":
                self._send(
                    {
                        "core_version": "0.4.0",
                        "capabilities": [
                            {
                                "name": "capability.list",
                                "summary": "catalogo del core",
                                "identity": False,
                                "streaming": False,
                                "params": [],
                                "rest": {
                                    "path": "/capability/list",
                                    "method": "GET",
                                },
                                "cli": {
                                    "group": "capability",
                                    "action": "list",
                                    "description": "catalogo del core",
                                },
                                "mcp": {"tool": "capability.list"},
                            },
                            {
                                "name": "prompt.run",
                                "summary": "prompt del core que se sobreescribe",
                                "identity": True,
                                "streaming": False,
                                "params": [],
                                "rest": {"path": "/prompt/run", "method": "POST"},
                                "cli": {
                                    "group": "prompt",
                                    "action": "run",
                                    "description": "prompt del core",
                                },
                                "mcp": {"tool": "prompt.run"},
                            },
                            {
                                "name": "future.inspect",
                                "summary": "capacidad futura desconocida",
                                "identity": False,
                                "streaming": False,
                                "params": [],
                                "rest": {"path": "/future/inspect", "method": "GET"},
                                "cli": {
                                    "group": "future",
                                    "action": "inspect",
                                    "description": "inspeccion futura",
                                },
                                "mcp": {"tool": "future.inspect"},
                                "future_field": {"preserved": True},
                            },
                        ],
                    }
                )
                return
            if self.path == "/estado/nuevo":
                # Capacidad desconocida servida por GET (sin cuerpo).
                self._send({"estado": "nuevo", "campo_desconocido": True})
                return
            if self.path == "/memory/nuevo":
                self._send({"memory": "nuevo", "forwarded": True})
                return
            if self.path == "/runtime/health":
                self._send(
                    {
                        "status": "ok",
                        "campo_desconocido": {"anidado": [1, 2, 3]},
                    }
                )
                return
            if self.path == "/domain/list":
                self._send(
                    {
                        "domains": [
                            {"id": "general"},
                            {"id": "linux"},
                            {"id": "codigo"},
                        ]
                    }
                )
                return
            self.send_error(404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            state.requests.append((self.path, payload))
            if self.path == "/api/embed":
                self._send({"embeddings": [[3.0, 4.0]]})
                return
            if self.path == "/capability/nueva":
                # Capacidad que esta capa NO conoce: prueba de conformidad.
                self._send(
                    {
                        "eco": payload,
                        "campo_desconocido": ["a", "b"],
                        "anidado": {"otro_campo": 42},
                    }
                )
                return
            if self.path in ("/prompt/stream", "/flujo/nuevo"):
                self._send_stream()
                return
            if self.path == "/capability/rota":
                # Capacidad desconocida que falla en el core.
                self._send(
                    {
                        "error": {
                            "type": "AdapterError",
                            "message": "el adaptador no respondio",
                            "field": "modelo",
                            "origin": "ia_nest_core",
                            "request_id": "core-error-2",
                        }
                    },
                    status=400,
                )
                return
            if self.path == "/eval/run":
                # Error de la capa inferior CON origin declarado.
                self._send(
                    {
                        "error": {
                            "type": "ConfigError",
                            "message": "suite desconocida",
                            "field": "suite",
                            "origin": "ia_nest_core",
                            "request_id": "core-error-1",
                        }
                    },
                    status=400,
                )
                return
            if self.path == "/config/validate":
                # Error SIN origin, como el que emite el core hoy.
                self._send(
                    {
                        "error": {
                            "type": "ConfigValidationError",
                            "message": "modelo declarado inexistente",
                            "field": "models",
                        }
                    },
                    status=400,
                )
                return
            if self.path == "/domain/route":
                if "low-route" in payload["prompt"]:
                    confidence = 0.2
                    domain = "cocina"
                else:
                    confidence = 0.9
                    domain = "linux"
                self._send(
                    {
                        "domain": domain,
                        "confidence": confidence,
                        "reason": "stub route",
                        "alternatives": [],
                        "trace": {"request_id": "route-stub"},
                    }
                )
                return
            if self.path == "/task/run":
                if payload["prompt"] == "tarea lenta":
                    time.sleep(0.15)
                self._send(
                    {
                        "response": "tarea lenta completada",
                        "trace": {
                            "request_id": "slow-task",
                            "stop_reason": "task_done",
                        },
                    }
                )
                return
            if self.path != "/prompt/run":
                self.send_error(404)
                return

            state.counter += 1
            prompt = payload["prompt"]
            if prompt == "slow-prompt":
                time.sleep(0.15)
            if payload.get("model"):
                if "invalid-json" in prompt:
                    response = "not-json"
                elif "remember-blue" in prompt:
                    response = json.dumps(
                        {
                            "items": [
                                {
                                    "namespace": "preferences",
                                    "content": "the user prefers blue",
                                    "confidence": 0.95,
                                    "mentions": [],
                                }
                            ]
                        }
                    )
                elif "repeat-fact" in prompt:
                    response = json.dumps(
                        {
                            "items": [
                                {
                                    "namespace": "facts",
                                    "content": "the project uses PostgreSQL",
                                    "confidence": 0.9,
                                    "mentions": ["PostgreSQL"],
                                }
                            ]
                        }
                    )
                else:
                    response = '{"items":[]}'
            else:
                response = f"echo:{prompt}"
            self._send(
                {
                    "response": response,
                    "model": payload.get("model", "stub-main"),
                    "domain": "stub",
                    "params": {},
                    "trace": {
                        "request_id": f"core-{state.counter}",
                        "finish_reason": "stop",
                    },
                }
            )

        def log_message(self, format, *args):
            return

        def _send(self, payload, status=200):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for index, (name, data) in enumerate(state.stream_events):
                if index == len(state.stream_events) - 1:
                    gate = state.stream_gate
                    if gate is not None and not gate.wait(timeout=10):
                        return
                self.wfile.write(
                    f"event: {name}\ndata: {data}\n\n".encode()
                )
                self.wfile.flush()

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


@pytest.fixture(scope="session")
def postgres_store():
    psycopg = pytest.importorskip(
        "psycopg",
        reason="psycopg no instalado; tests postgres omitidos",
    )
    source_dsn = os.environ.get("IANEST_EXTENDED_TEST_DSN")
    if not source_dsn:
        pytest.skip(
            "IANEST_EXTENDED_TEST_DSN no definido; tests postgres omitidos"
        )
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    source_parameters = conninfo_to_dict(source_dsn)
    hostname = source_parameters.get("host")
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.skip(
            "el DSN no apunta a localhost; no se conectan hosts remotos"
        )
    source_dbname = source_parameters.get("dbname")
    if not source_dbname:
        pytest.fail("IANEST_EXTENDED_TEST_DSN debe declarar dbname")
    test_dbname = f"{source_dbname}_test"
    if len(test_dbname.encode("utf-8")) > 63:
        pytest.fail("el nombre derivado de la DB de pruebas supera 63 bytes")

    admin_parameters = {**source_parameters, "dbname": "postgres"}
    test_parameters = {**source_parameters, "dbname": test_dbname}
    admin_dsn = make_conninfo(**admin_parameters)
    test_dsn = make_conninfo(**test_parameters)
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (test_dbname,),
            ).fetchone()
            if exists is None:
                connection.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(test_dbname)
                    )
                )
        with psycopg.connect(test_dsn) as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except psycopg.OperationalError as exc:
        pytest.skip(f"postgres local no disponible: {exc}")

    from ianest_extended import FakeEmbedder
    from ianest_extended.adapters import PostgresMemoryStore

    dimension = int(
        os.environ.get("IANEST_EXTENDED_EMBEDDING_DIMENSION", "1024")
    )
    store = PostgresMemoryStore(test_dsn, FakeEmbedder(dimension))
    try:
        store.migrate()
    except psycopg.OperationalError as exc:
        pytest.skip(f"postgres local no disponible: {exc}")
    return store


@pytest.fixture(scope="session")
def postgres_rag_store(postgres_store):
    from ianest_extended.adapters import PostgresRagStore

    store = PostgresRagStore(postgres_store._dsn, postgres_store._embedder)
    store.migrate()
    return store


_POSTGRES_DATA_TABLES = (
    "engrams",
    "entities",
    "memory_links",
    "rag_chunks",
    "rag_corpus_domains",
    "rag_corpora",
)


def _truncate_postgres_data(store) -> None:
    """Vacia las tablas de DATOS; `memory_types` (esquema) no se toca."""
    with store._connect() as connection:
        existing = [
            table
            for table in _POSTGRES_DATA_TABLES
            if connection.execute(
                "SELECT to_regclass(%s) AS relation", (table,)
            ).fetchone()["relation"]
            is not None
        ]
        if existing:
            connection.execute(
                "TRUNCATE TABLE "
                + ", ".join(existing)
                + " RESTART IDENTITY CASCADE"
            )


@pytest.fixture(autouse=True)
def _reset_postgres_state(request):
    """D4: banco de pruebas de PostgreSQL idempotente.

    `postgres_store` es de sesion (una migracion, muchas pruebas) y no se
    limpiaba entre pruebas ni entre ejecuciones: acumulaba filas y el
    resultado dependia de la historia (llego a superar cien engramas de
    pasadas anteriores). Se vacian las tablas de datos antes de cada prueba
    que use `postgres_store`, directa o indirectamente (`postgres_rag_store`
    depende de el). Asi, dos ejecuciones seguidas de la suite dan el mismo
    resultado, y una prueba aislada da lo mismo que dentro de la suite.
    """
    if "postgres_store" not in request.fixturenames:
        yield
        return
    store = request.getfixturevalue("postgres_store")
    _truncate_postgres_data(store)
    yield
