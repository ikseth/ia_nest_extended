#!/usr/bin/env python3
"""Ejecuta la puerta de laboratorio de ia_nest_extended por REST.

Codigos de salida: 0 PASA, 1 NO PASA, 2 NULA.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_NULL = 2

PASS = "PASA"
FAIL = "NO PASA"
NULL = "NULA"
NOT_EXECUTABLE = "NO EJECUTABLE"
OUTSIDE = "FUERA DEL SCRIPT"

L5_PROBES = (
    ("linux", "como abro un puerto en el cortafuegos de mi servidor"),
    ("finanzas", "cuanto tarda en duplicarse mi dinero al 6 por ciento anual"),
    ("agricultura", "cuando conviene sembrar tomates"),
    ("medicina", "que hago ante una quemadura leve"),
    ("cocina", "como se hace un sofrito"),
)
L5R_PROBES = (
    "hola, buenos dias",
    "gracias por tu ayuda",
    "que recuerdas de mi",
)

OWN_CAPABILITIES = frozenset(
    {
        "memory_type.list",
        "memory_type.validate",
        "memory.recall",
        "memory.write",
        "memory.consolidate",
        "memory.maintain",
        "knowledge.ingest",
        "knowledge.status",
        "knowledge.suggest",
        "knowledge.confirm",
        "knowledge.reject",
    }
)

NOT_COVERED = (
    "La veracidad general de las respuestas: solo los testigos fijados.",
    "El filtro que impide destilar a `episodic` una tarea no convergida: no se "
    "puede forzar la no convergencia de forma reproducible.",
    "Streaming y la piel MCP: solo REST, y MCP solo en lo que comprueba L1.",
    "Rendimiento y capacidad de GPU.",
    "Si los umbrales son los OPTIMOS. La puerta dice si la capa funciona con "
    "los valores declarados; calibrarlos es otra medida (D4, D5).",
    "Un PASA de forma no es un PASA de contenido. El oraculo lexico puede dar "
    "un falso NO PASA ante una parafrasis (\"dos dias despues del martes\"); "
    "por eso cada respuesta queda en la evidencia y la cruzan dos agentes.",
)


class GateHttpError(RuntimeError):
    """Una llamada REST no produjo una respuesta JSON satisfactoria."""


@dataclass(frozen=True)
class GateArgs:
    base_url: str
    tag: str
    installed_at: str
    service_unit: str
    core_smoke_passed: bool
    parameter_fingerprint: str | None
    setup_exit_code: int | None
    repetitions: int
    timeout: float
    json_path: Path | None


class RestRecorder:
    def __init__(self, base_url: str, timeout: float, default_user_id: str):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_user_id = default_user_id
        self.exchanges: list[dict[str, Any]] = []

    def get(self, route: str) -> dict[str, Any]:
        return self._request("GET", route, None)

    def post(self, route: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", route, payload)

    def _request(
        self,
        method: str,
        route: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{route}"
        data = None
        user_id = _payload_user_id(payload) or self.default_user_id
        headers = {
            "Accept": "application/json",
            # Las capacidades sin identidad no admiten body. La cabecera deja
            # trazada la identidad de la pasada tambien en esas llamadas.
            "X-IA-NEST-Lab-User-Id": user_id,
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        started_wall = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()
        record: dict[str, Any] = {
            "request": {
                "method": method,
                "url": url,
                "headers": {"X-IA-NEST-Lab-User-Id": user_id},
                "body": payload,
            },
            "started_at": started_wall,
        }
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            status = exc.code
            record["response"] = {"status": status, "body": _json_or_text(raw)}
            record["elapsed_seconds"] = round(time.monotonic() - started, 6)
            self.exchanges.append(record)
            raise GateHttpError(f"{method} {route} devolvio HTTP {status}") from exc
        except (OSError, TimeoutError) as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["elapsed_seconds"] = round(time.monotonic() - started, 6)
            self.exchanges.append(record)
            raise GateHttpError(f"{method} {route} no respondio: {exc}") from exc

        body = _json_or_text(raw)
        record["response"] = {"status": status, "body": body}
        record["elapsed_seconds"] = round(time.monotonic() - started, 6)
        self.exchanges.append(record)
        if not isinstance(body, dict):
            raise GateHttpError(f"{method} {route} no devolvio un objeto JSON")
        return body


def _json_or_text(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _payload_user_id(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    identity = payload.get("identity")
    if not isinstance(identity, dict):
        request = payload.get("request")
        identity = request.get("identity") if isinstance(request, dict) else None
    user_id = identity.get("user_id") if isinstance(identity, dict) else None
    return user_id if isinstance(user_id, str) else None


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def _contains(text: str, witness: str) -> bool:
    return _normalized(witness) in _normalized(text)


def _response_text(payload: dict[str, Any]) -> str:
    response = payload.get("response")
    return response if isinstance(response, str) else ""


def _identity(
    user_id: str,
    session_id: str,
    *,
    domain: str | None = None,
) -> dict[str, str]:
    identity = {
        "user_id": user_id,
        "session_id": session_id,
        "service": "puerta_laboratorio",
    }
    if domain is not None:
        identity["domain_tag"] = domain
    return identity


def _probe_user_id(run_id: str, line: str, repetition: int) -> str:
    return f"puerta-{run_id}-{line.lower()}-{repetition}"


def _random_word(prefix: str) -> str:
    """Crea un testigo alfanumerico de una sola palabra y sin punto de corte."""
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def _prompt(
    rest: RestRecorder,
    user_id: str,
    session_id: str,
    prompt: str,
) -> dict[str, Any]:
    return rest.post(
        "/prompt/run",
        {"prompt": prompt, "identity": _identity(user_id, session_id)},
    )


def _recall(
    rest: RestRecorder,
    user_id: str,
    session_id: str,
    prompt: str,
) -> dict[str, Any]:
    return rest.post(
        "/memory/recall",
        {
            "prompt": prompt,
            "identity": _identity(user_id, session_id),
            "use_memory": True,
            "use_rag": False,
        },
    )


def _attempt_l2(rest: RestRecorder, user_id: str, repetition: int) -> dict[str, Any]:
    witness = _random_word("Xanthe")
    session_a = f"l2-{repetition}-a-{uuid.uuid4().hex[:8]}"
    session_b = f"l2-{repetition}-b-{uuid.uuid4().hex[:8]}"
    assertion = f"Mi perro se llama {witness}. Recuerda exactamente ese nombre."
    question = "Como se llama mi perro? Escribe el nombre exacto."
    evidence: dict[str, Any] = {
        "repetition": repetition,
        "user_id": user_id,
        "witness": witness,
        "sessions": [session_a, session_b],
    }
    try:
        evidence["assertion_response"] = _prompt(rest, user_id, session_a, assertion)
        answer_payload = _prompt(rest, user_id, session_b, question)
        recall_payload = _recall(rest, user_id, session_b, question)
        answer = _response_text(answer_payload)
        context = recall_payload.get("context")
        context = context if isinstance(context, str) else ""
        matching_lines = [line for line in context.splitlines() if _contains(line, witness)]
        stated_by_user = any(_contains(line, "fuente: usuario") for line in matching_lines)
        passed = stated_by_user
        evidence.update(
            {
                "answer": answer_payload,
                "recall": recall_payload,
                "matching_context_lines": matching_lines,
                "checks": {
                    "answer_contains_witness": _contains(answer, witness),
                    "recall_contains_witness_stated_by_user": stated_by_user,
                },
                "verdict": PASS if passed else FAIL,
            }
        )
    except GateHttpError as exc:
        evidence.update({"error": str(exc), "verdict": FAIL})
    return evidence


def _attempt_l3_l4a(
    rest: RestRecorder,
    user_id: str,
    repetition: int,
    *,
    run_l4a: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    suffix = uuid.uuid4().hex[:10]
    correct = f"Ambar{suffix}"
    incorrect = f"Cobalto{suffix}"
    session_id = f"l3-l4a-{repetition}-{uuid.uuid4().hex[:8]}"
    evidence_l3: dict[str, Any] = {
        "repetition": repetition,
        "user_id": user_id,
        "correct_witness": correct,
        "incorrect_witness": incorrect,
        "session_id": session_id,
        "contradicted_by_observation": "context annotation derived from contradicted_by",
    }
    evidence_l4a: dict[str, Any] = {
        "repetition": repetition,
        "user_id": user_id,
        "correct_witness": correct,
        "incorrect_witness": incorrect,
        "session_id": session_id,
    }
    try:
        seeded = rest.post(
            "/memory/write",
            {
                "principal": "extended",
                "request": {
                    "type_name": "episodic",
                    "namespace": "facts",
                    "content": f"La clave del refugio es {incorrect}.",
                    "stated_by": "model",
                    "identity": _identity(user_id, session_id),
                },
            },
        )
        turn_1 = _prompt(
            rest,
            user_id,
            session_id,
            f"La clave del refugio es {correct}.",
        )
        recall_payload = _recall(rest, user_id, session_id, "Cual es la clave del refugio?")
        context = recall_payload.get("context")
        context = context if isinstance(context, str) else ""
        normalized_context = _normalized(context)
        correct_index = normalized_context.find(_normalized(correct))
        incorrect_index = normalized_context.find(_normalized(incorrect))
        incorrect_lines = [line for line in context.splitlines() if _contains(line, incorrect)]
        model_label = any(
            _contains(line, "fuente: modelo, sin verificar") for line in incorrect_lines
        )
        contradiction_label = any(
            _contains(line, "hay una version del usuario sobre esto")
            for line in incorrect_lines
        )
        ordered = correct_index >= 0 and incorrect_index > correct_index
        l3_passed = model_label and ordered
        evidence_l3.update(
            {
                "seed_response": seeded,
                "turn_1_response": turn_1,
                "recall": recall_payload,
                "incorrect_context_lines": incorrect_lines,
                "checks": {
                    "model_label": model_label,
                    "contradicted_by_annotation": contradiction_label,
                    "user_version_before_model_version": ordered,
                },
                "verdict": PASS if l3_passed else FAIL,
            }
        )

        if not run_l4a:
            return evidence_l3, evidence_l4a

        turn_2 = _prompt(rest, user_id, session_id, "Responde solo OK.")
        turn_3 = _prompt(rest, user_id, session_id, "Responde solo LISTO.")
        turn_4 = _prompt(
            rest,
            user_id,
            session_id,
            "Cual es la clave del refugio? Escribe solo la clave correcta.",
        )
        answer = _response_text(turn_4)
        has_correct = _contains(answer, correct)
        has_incorrect = _contains(answer, incorrect)
        l4a_passed = has_correct and not has_incorrect
        evidence_l4a.update(
            {
                "recall": recall_payload,
                "turns": [turn_1, turn_2, turn_3, turn_4],
                "final_answer": answer,
                "checks": {
                    "contains_correct": has_correct,
                    "contains_incorrect": has_incorrect,
                },
                "verdict": PASS if l4a_passed else FAIL,
            }
        )
    except GateHttpError as exc:
        evidence_l3.setdefault("error", str(exc))
        evidence_l3.setdefault("verdict", FAIL)
        evidence_l4a.update({"error": str(exc), "verdict": FAIL})
    return evidence_l3, evidence_l4a


def _attempt_l4b(rest: RestRecorder, user_id: str, repetition: int) -> dict[str, Any]:
    correct = "jueves"
    incorrect = "martes"
    session_id = f"l4b-{repetition}-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, Any] = {
        "repetition": repetition,
        "user_id": user_id,
        "correct_witness": correct,
        "incorrect_witness": incorrect,
        "session_id": session_id,
        "phase_9_control_arm": True,
        "blocking": False,
    }
    try:
        turn_1 = _prompt(rest, user_id, session_id, "La reunion es el martes.")
        turn_2 = _prompt(rest, user_id, session_id, "Responde solo OK.")
        turn_3 = _prompt(
            rest,
            user_id,
            session_id,
            "Perdona, la reunion es el jueves.",
        )
        turn_4 = _prompt(
            rest,
            user_id,
            session_id,
            "Que dia es la reunion? Escribe solo el dia correcto.",
        )
        answer = _response_text(turn_4)
        has_correct = _contains(answer, correct)
        has_incorrect = _contains(answer, incorrect)
        passed = has_correct and not has_incorrect
        evidence.update(
            {
                "turns": [turn_1, turn_2, turn_3, turn_4],
                "final_answer": answer,
                "checks": {
                    "contains_correct": has_correct,
                    "contains_incorrect": has_incorrect,
                },
                "verdict": PASS if passed else FAIL,
            }
        )
    except GateHttpError as exc:
        evidence.update({"error": str(exc), "verdict": FAIL})
    return evidence


def _rag_observation(payload: dict[str, Any]) -> tuple[int, list[str], str]:
    counters = payload.get("counters")
    raw_count = counters.get("rag") if isinstance(counters, dict) else None
    rag_count = raw_count if isinstance(raw_count, int) and raw_count >= 0 else 0
    context = payload.get("context")
    context = context if isinstance(context, str) else ""
    corpora: set[str] = set()
    for line in context.splitlines():
        if not line.startswith("[") or "]" not in line:
            continue
        descriptor = line[1 : line.index("]")]
        corpus = descriptor.split("/", 1)[0]
        if corpus:
            corpora.add(corpus)
    return rag_count, sorted(corpora), context


def _attempt_l5(
    rest: RestRecorder,
    user_id: str,
    repetition: int,
    *,
    on_probe: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    probes: list[dict[str, Any]] = []
    for domain, question in L5_PROBES:
        session_id = f"l5-{repetition}-{domain}-{uuid.uuid4().hex[:8]}"
        evidence: dict[str, Any] = {
            "domain": domain,
            "question": question,
            "user_id": user_id,
            "session_id": session_id,
            "score": None,
            "score_observation": "la puntuacion no se publica por REST",
        }
        try:
            payload = rest.post(
                "/memory/recall",
                {
                    "prompt": question,
                    "identity": _identity(user_id, session_id, domain=domain),
                    "use_memory": False,
                    "use_rag": True,
                },
            )
            rag_count, corpora, context = _rag_observation(payload)
            corpus_identity_verifiable = bool(corpora)
            passed = rag_count > 0
            evidence.update(
                {
                    "recall": payload,
                    "context": context,
                    "k_returned": rag_count,
                    "recovered_corpora": corpora,
                    "corpus_identity_verifiable_by_rest": corpus_identity_verifiable,
                    "corpus_identity_observation": (
                        "nombres publicados en context de memory.recall"
                        if corpora
                        else (
                            "no se recupero ningun corpus"
                            if rag_count == 0
                            else "la identidad del corpus no se comprueba por REST"
                        )
                    ),
                    "verdict": PASS if passed else FAIL,
                }
            )
        except GateHttpError as exc:
            evidence.update({"error": str(exc), "verdict": FAIL})
        probes.append(evidence)
        if on_probe is not None:
            on_probe(evidence)
    passed = all(probe.get("verdict") == PASS for probe in probes)
    return {
        "repetition": repetition,
        "user_id": user_id,
        "probes": probes,
        "verdict": PASS if passed else FAIL,
    }


def _attempt_l5r(
    rest: RestRecorder,
    user_id: str,
    repetition: int,
    question: str,
) -> dict[str, Any]:
    session_id = f"l5r-{repetition}-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, Any] = {
        "repetition": repetition,
        "question": question,
        "user_id": user_id,
        "session_id": session_id,
        "score": None,
        "score_observation": "la puntuacion no se publica por REST",
    }
    try:
        payload = rest.post(
            "/memory/recall",
            {
                "prompt": question,
                "identity": _identity(user_id, session_id),
                "use_memory": False,
                "use_rag": True,
            },
        )
        rag_count, corpora, context = _rag_observation(payload)
        evidence.update(
            {
                "recall": payload,
                "context": context,
                "k_returned": rag_count,
                "recovered_corpora": corpora,
                "verdict": PASS if rag_count == 0 else FAIL,
            }
        )
    except GateHttpError as exc:
        evidence.update({"error": str(exc), "verdict": FAIL})
    return evidence


def _aggregate(
    line: str,
    attempts: list[dict[str, Any]],
    blocking: bool = True,
) -> dict[str, Any]:
    passed = sum(item.get("verdict") == PASS for item in attempts)
    total = len(attempts)
    return {
        "line": line,
        "verdict": PASS if passed == total else FAIL,
        "passed": passed,
        "total": total,
        "blocking": blocking,
        "attempts": attempts,
    }


def _print_probe_progress(
    line: str,
    repetition: int,
    verdict: str,
    detail: str | None = None,
) -> None:
    suffix = f" {detail}" if detail else ""
    print(f"PROGRESO {line} repeticion {repetition}{suffix}: {verdict}", flush=True)


def _check_l1(
    rest: RestRecorder,
    catalog: dict[str, Any],
    setup_exit_code: int | None,
) -> dict[str, Any]:
    capabilities = catalog.get("capabilities")
    names = {
        item.get("name")
        for item in capabilities
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    } if isinstance(capabilities, list) else set()
    missing = sorted(OWN_CAPABILITIES - names)
    degraded = bool(catalog.get("error") or catalog.get("degradations"))
    try:
        status = rest.get("/knowledge/status")
        status_responded = True
        status_error = None
    except GateHttpError as exc:
        status = None
        status_responded = False
        status_error = str(exc)
    setup_ok = setup_exit_code == 0
    passed = setup_ok and not degraded and not missing and status_responded
    return {
        "line": "L1",
        "verdict": PASS if passed else FAIL,
        "blocking": True,
        "setup_exit_code_declared": setup_exit_code,
        "catalog": catalog,
        "knowledge_status": status,
        "checks": {
            "setup_exit_code_zero": setup_ok,
            "catalog_without_degradation": not degraded,
            "own_capabilities_present": not missing,
            "knowledge_status_responded": status_responded,
        },
        "missing_capabilities": missing,
        "error": status_error,
    }


def _is_local_url(base_url: str) -> bool:
    host = urllib.parse.urlparse(base_url).hostname
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    return bool(host and host.startswith("127."))


def _parse_timestamp(value: str) -> datetime:
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        pass
    # systemctl suele devolver: Sat 2026-09-12 12:34:56 CEST
    pieces = candidate.split()
    if len(pieces) >= 3:
        joined = " ".join(pieces[1:3]) if pieces[0].isalpha() else " ".join(pieces[:2])
        try:
            return datetime.strptime(joined, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    raise ValueError(f"marca de tiempo no reconocida: {value!r}")


def _comparable_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone().replace(tzinfo=None)


def _preconditions(
    args: GateArgs,
    rest: RestRecorder,
    systemctl_run: Callable[..., subprocess.CompletedProcess[str]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    checks: dict[str, Any] = {}
    if not args.core_smoke_passed:
        checks["P3"] = {"verdict": NULL, "reason": "core smoke no declarado PASA"}
        return checks, None
    checks["P3"] = {"verdict": PASS, "declared_by_operator": True}
    if not args.parameter_fingerprint:
        checks["P4"] = {"verdict": NULL, "reason": "huella de parametros no declarada"}
        return checks, None
    checks["P4"] = {
        "verdict": PASS,
        "declared_by_operator": True,
        "fingerprint": args.parameter_fingerprint,
    }

    try:
        catalog = rest.get("/capability/list")
    except GateHttpError as exc:
        checks["P1"] = {"verdict": NULL, "reason": str(exc)}
        return checks, None
    published = catalog.get("extended_version")
    expected = args.tag[1:] if args.tag.startswith("v") else args.tag
    version_ok = isinstance(published, str) and published == expected
    checks["P1"] = {
        "verdict": PASS if version_ok else NULL,
        "tag": args.tag,
        "expected_version": expected,
        "published_version": published,
        "catalog": catalog,
    }
    if not version_ok:
        return checks, None

    if not _is_local_url(args.base_url):
        checks["P2"] = {
            "verdict": NULL,
            "reason": "servicio remoto: ExecMainStartTimestamp no comprobado",
        }
        return checks, None
    try:
        installed = _parse_timestamp(args.installed_at)
        completed = systemctl_run(
            [
                "systemctl",
                "show",
                "-p",
                "ExecMainStartTimestamp",
                "--value",
                args.service_unit,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        raw_started = completed.stdout.strip()
        started = _parse_timestamp(raw_started)
        start_ok = _comparable_local(started) > _comparable_local(installed)
        checks["P2"] = {
            "verdict": PASS if start_ok else NULL,
            "installed_at": args.installed_at,
            "service_started_at": raw_started,
            "service_unit": args.service_unit,
            "command": [
                "systemctl",
                "show",
                "-p",
                "ExecMainStartTimestamp",
                "--value",
                args.service_unit,
            ],
        }
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        checks["P2"] = {
            "verdict": NULL,
            "reason": f"ExecMainStartTimestamp no comprobado: {exc}",
            "service_unit": args.service_unit,
        }
        return checks, None
    if checks["P2"]["verdict"] != PASS:
        return checks, None
    return checks, catalog


def execute_gate(
    args: GateArgs,
    *,
    systemctl_run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[int, dict[str, Any]]:
    run_id = str(uuid.uuid4())
    user_id_prefix = f"puerta-{run_id}-"
    rest = RestRecorder(
        args.base_url,
        args.timeout,
        _probe_user_id(run_id, "l1", 1),
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "user_id_prefix": user_id_prefix,
        "base_url": args.base_url,
        "tag": args.tag,
        "repetitions": args.repetitions,
        "not_covered": list(NOT_COVERED),
        "preconditions": {},
        "lines": [],
        "http_exchanges": rest.exchanges,
    }
    preconditions, catalog = _preconditions(args, rest, systemctl_run)
    report["preconditions"] = preconditions
    if catalog is None:
        report.update(
            {
                "verdict": NULL,
                "exit_code": EXIT_NULL,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return EXIT_NULL, report

    lines: list[dict[str, Any]] = []
    l1 = _check_l1(rest, catalog, args.setup_exit_code)
    lines.append(l1)
    _print_probe_progress("L1", 1, l1["verdict"])

    l2_attempts: list[dict[str, Any]] = []
    l3_attempts: list[dict[str, Any]] = []
    l4a_attempts: list[dict[str, Any]] = []
    l4b_attempts: list[dict[str, Any]] = []
    l5_attempts: list[dict[str, Any]] = []
    for repetition in range(1, args.repetitions + 1):
        l2 = _attempt_l2(
            rest,
            _probe_user_id(run_id, "l2", repetition),
            repetition,
        )
        l2_attempts.append(l2)
        _print_probe_progress("L2", repetition, l2["verdict"])
        l3, _ = _attempt_l3_l4a(
            rest,
            _probe_user_id(run_id, "l3", repetition),
            repetition,
            run_l4a=False,
        )
        l3_attempts.append(l3)
        annotation = l3.get("checks", {}).get("contradicted_by_annotation", False)
        _print_probe_progress(
            "L3",
            repetition,
            l3["verdict"],
            f"anotacion {'SI' if annotation else 'NO'}",
        )
        _, l4a = _attempt_l3_l4a(
            rest,
            _probe_user_id(run_id, "l4a", repetition),
            repetition,
            run_l4a=True,
        )
        l4a_attempts.append(l4a)
        _print_probe_progress("L4a", repetition, l4a["verdict"])
        l4b = _attempt_l4b(
            rest,
            _probe_user_id(run_id, "l4b", repetition),
            repetition,
        )
        l4b_attempts.append(l4b)
        _print_probe_progress("L4b", repetition, l4b["verdict"])
        l5 = _attempt_l5(
            rest,
            _probe_user_id(run_id, "l5", repetition),
            repetition,
            on_probe=lambda probe, current=repetition: _print_probe_progress(
                "L5",
                current,
                probe["verdict"],
                str(probe["domain"]),
            ),
        )
        l5_attempts.append(l5)
    l5r_attempts = []
    for repetition, question in enumerate(L5R_PROBES, start=1):
        l5r = _attempt_l5r(
            rest,
            _probe_user_id(run_id, "l5r", repetition),
            repetition,
            question,
        )
        l5r_attempts.append(l5r)
        _print_probe_progress("L5r", repetition, l5r["verdict"])
    corpus_observations = [
        probe.get("corpus_identity_verifiable_by_rest", False)
        for attempt in l5_attempts
        for probe in attempt["probes"]
        if probe.get("k_returned", 0) > 0
    ]
    l5_corpus_observable = bool(corpus_observations) and all(corpus_observations)
    report["rest_observability"] = {
        "corpus_identity_verifiable": l5_corpus_observable,
        "corpus_identity": (
            "los nombres se publican en context de memory.recall"
            if l5_corpus_observable
            else "la identidad del corpus no se comprueba por REST"
        ),
        "rag_score_verifiable": False,
        "rag_score": "la puntuacion no se publica por REST",
    }
    l3_line = _aggregate("L3", l3_attempts)
    annotations = sum(
        attempt.get("checks", {}).get("contradicted_by_annotation") is True
        for attempt in l3_attempts
    )
    l3_line["annotation"] = {
        "observed": annotations,
        "total": len(l3_attempts),
        "rate": f"{annotations}/{len(l3_attempts)}",
    }
    lines.extend(
        [
            _aggregate("L2", l2_attempts),
            l3_line,
            _aggregate("L4a", l4a_attempts),
            _aggregate("L4b", l4b_attempts, blocking=False),
            _aggregate("L5", l5_attempts),
            _aggregate("L5r", l5r_attempts),
            {
                "line": "L6",
                "verdict": OUTSIDE,
                "blocking": False,
                "reason": "la ejecuta el operador repitiendo setup.sh y la puerta",
            },
        ]
    )
    report["lines"] = lines
    blocking_failures = [
        line for line in lines if line.get("blocking") and line.get("verdict") != PASS
    ]
    code = EXIT_FAIL if blocking_failures else EXIT_PASS
    report.update(
        {
            "verdict": FAIL if code == EXIT_FAIL else PASS,
            "exit_code": code,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return code, report


def _failure_summary(line: dict[str, Any]) -> str:
    if line.get("verdict") != FAIL:
        return ""
    if "passed" in line:
        failed = next(
            (item for item in line["attempts"] if item.get("verdict") != PASS),
            {},
        )
        if failed.get("probes"):
            failed = next(
                (
                    probe
                    for probe in failed["probes"]
                    if probe.get("verdict") != PASS
                ),
                failed,
            )
        expected = failed.get("correct_witness") or failed.get("witness")
        if expected is None and failed.get("domain"):
            expected = f"al menos un fragmento RAG para {failed['domain']}"
        if expected is None and "k_returned" in failed:
            expected = "k_returned = 0"
        fragment = failed.get("final_answer") or failed.get("error")
        if not fragment and isinstance(failed.get("answer"), dict):
            fragment = _response_text(failed["answer"])
        if not fragment:
            fragment = " | ".join(failed.get("incorrect_context_lines") or [])
        if not fragment and isinstance(failed.get("recall"), dict):
            fragment = failed["recall"].get("context")
        return f"; esperado={expected!r}; respuesta={str(fragment)[:240]!r}"
    checks = line.get("checks") or {}
    return f"; comprobaciones={json.dumps(checks, ensure_ascii=True, sort_keys=True)}"


def print_report(report: dict[str, Any]) -> None:
    print("LO QUE LA PUERTA NO CUBRE")
    for item in report["not_covered"]:
        print(f"- {item}")
    print(f"VEREDICTO: {report['verdict']} (codigo {report['exit_code']})")
    if report["verdict"] == NULL:
        for name, check in report["preconditions"].items():
            print(f"{name}: {check['verdict']} - {check.get('reason', 'comprobada')}")
        print("LINEAS: no ejecutadas")
        return
    observability = report.get("rest_observability", {})
    print(f"IDENTIDAD DE CORPUS POR REST: {observability.get('corpus_identity')}")
    print(f"PUNTUACION RAG POR REST: {observability.get('rag_score')}")
    for line in report["lines"]:
        share = ""
        if "passed" in line:
            share = f" {line['passed']}/{line['total']}"
        annotation = ""
        if line["line"] == "L3":
            annotation = f" (anotacion {line['annotation']['rate']})"
        label = (
            " [brazo sin sintesis de Fase 9; no bloquea]"
            if line["line"] == "L4b"
            else ""
        )
        print(
            f"{line['line']}: {line['verdict']}{share}{annotation}{label}"
            f"{_failure_summary(line)}"
        )


def _write_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001", dest="base_url")
    parser.add_argument("--tag", required=True, help="tag desplegado, por ejemplo v0.2.0")
    parser.add_argument(
        "--instalado",
        required=True,
        dest="installed_at",
        help="marca ISO-8601 de la ultima instalacion",
    )
    parser.add_argument(
        "--service-unit",
        default="ianest-extended-extended-rest.service",
        help="unit REST comprobada por systemctl",
    )
    parser.add_argument(
        "--core-smoke-pasa",
        action="store_true",
        dest="core_smoke_passed",
        help="declara P3: el smoke del core paso hoy en esta maquina",
    )
    parser.add_argument(
        "--parametros-huella",
        dest="parameter_fingerprint",
        help="declara P4: huella de los ficheros de parametros usados",
    )
    parser.add_argument(
        "--setup-exit-code",
        type=int,
        help="codigo declarado de setup.sh con VERIFY=strict para L1",
    )
    parser.add_argument("--n", type=int, default=3, dest="repetitions")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--json", type=Path, dest="json_path")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    systemctl_run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int:
    namespace = _parser().parse_args(argv)
    if namespace.repetitions <= 0:
        _parser().error("--n debe ser mayor que cero")
    if namespace.timeout <= 0:
        _parser().error("--timeout debe ser mayor que cero")
    args = GateArgs(**vars(namespace))
    code, report = execute_gate(args, systemctl_run=systemctl_run)
    print_report(report)
    if args.json_path is not None:
        _write_json(args.json_path, report)
    return code


if __name__ == "__main__":
    sys.exit(main())
