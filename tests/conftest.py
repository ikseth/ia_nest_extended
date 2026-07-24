import os
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest


@pytest.fixture
def local_service_stub():
    state = SimpleNamespace(requests=[], counter=0)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            state.requests.append((self.path, payload))
            if self.path == "/api/embed":
                self._send({"embeddings": [[3.0, 4.0]]})
                return
            if self.path != "/prompt/run":
                self.send_error(404)
                return

            state.counter += 1
            prompt = payload["prompt"]
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

        def _send(self, payload):
            body = json.dumps(payload).encode()
            self.send_response(200)
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


@pytest.fixture(scope="session")
def postgres_store():
    psycopg = pytest.importorskip(
        "psycopg",
        reason="psycopg no instalado; tests postgres omitidos",
    )
    dsn = os.environ.get("IANEST_EXTENDED_TEST_DSN")
    if not dsn:
        pytest.skip(
            "IANEST_EXTENDED_TEST_DSN no definido; tests postgres omitidos"
        )
    hostname = urlparse(dsn).hostname
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.skip(
            "el DSN no apunta a localhost; no se conectan hosts remotos"
        )

    from ianest_extended import FakeEmbedder
    from ianest_extended.adapters import PostgresMemoryStore

    dimension = int(
        os.environ.get("IANEST_EXTENDED_EMBEDDING_DIMENSION", "1024")
    )
    store = PostgresMemoryStore(dsn, FakeEmbedder(dimension))
    try:
        store.migrate()
    except psycopg.OperationalError as exc:
        pytest.skip(f"postgres local no disponible: {exc}")
    return store
