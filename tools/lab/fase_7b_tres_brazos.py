#!/usr/bin/env python3
"""Medida reproducible de task.run: control, plan eco y plan enriquecido.

Ejecutar desde una instalacion con core, PostgreSQL, Ollama y corpus disponibles:

    python tools/lab/fase_7b_tres_brazos.py --env-file .env

Usa un user_id de laboratorio propio, no escribe memoria y repite tres veces
cada brazo. No decide un gate: imprime las magnitudes que el revisor compara.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from typing import Any

from ianest_extended import (
    ExtendedConfig,
    ExtendedService,
    MemoryIdentity,
)

DEFAULT_PROMPT = (
    "Explica como configurar un firewall en Linux con nftables y ademas "
    "calcula cuantas reglas se necesitan si hay 4 servicios y 3 redes."
)


def _post(base_url: str, route: str, payload: dict[str, Any], timeout: float):
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{route}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    return result, time.monotonic() - started


def _row(arm: str, repetition: int, result: dict[str, Any], seconds: float):
    trace = result.get("trace") or {}
    spend = (trace.get("tokens_in") or 0) + (trace.get("tokens_out") or 0)
    return {
        "arm": arm,
        "rep": repetition,
        "stop_reason": result.get("stop_reason"),
        "requirements_covered": result.get("requirements_covered"),
        "degradations": len(result.get("degradations") or []),
        "spend": spend,
        "response_chars": len(result.get("response") or ""),
        "seconds": round(seconds, 1),
    }


def _print_table(rows):
    headers = (
        "arm",
        "rep",
        "stop_reason",
        "requirements_covered",
        "degradations",
        "spend",
        "response_chars",
        "seconds",
    )
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        print("| " + " | ".join(str(row[key]) for key in headers) + " |")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--user-id", default="phase_7b_lab")
    args = parser.parse_args(argv)
    if args.repetitions <= 0:
        parser.error("--repetitions debe ser mayor que cero")

    config = ExtendedConfig.from_env(env_file=args.env_file)
    identity = MemoryIdentity(
        user_id=args.user_id,
        session_id="phase_7b_measure",
        service="phase_7b_lab",
    )
    core_identity = identity.to_core_dict()
    timeout = config.task_timeout_seconds
    service = ExtendedService.from_config(config)
    rows = []

    for repetition in range(1, args.repetitions + 1):
        result, seconds = _post(
            config.core_url,
            "/task/run",
            {"prompt": args.prompt, "identity": core_identity},
            timeout,
        )
        rows.append(_row("sin_plan", repetition, result, seconds))

    for repetition in range(1, args.repetitions + 1):
        planned, _ = _post(
            config.core_url,
            "/task/plan",
            {"prompt": args.prompt, "identity": core_identity},
            timeout,
        )
        request = {key: value for key, value in planned.items() if key != "params"}
        request.update({"prompt": args.prompt, "identity": core_identity})
        result, seconds = _post(
            config.core_url,
            "/task/run",
            request,
            timeout,
        )
        rows.append(_row("plan_eco", repetition, result, seconds))

    for repetition in range(1, args.repetitions + 1):
        started = time.monotonic()
        result = service.task_run(
            args.prompt,
            identity,
            write_back=False,
        ).payload
        rows.append(
            _row(
                "plan_enriquecido",
                repetition,
                result,
                time.monotonic() - started,
            )
        )

    _print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
