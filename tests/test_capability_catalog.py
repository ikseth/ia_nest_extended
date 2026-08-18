"""Criterios falsables del catalogo propio y fusionado (extended ADR 0012)."""

import argparse
from pathlib import Path

from ianest_extended import (
    CoreConnectionError,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    ForwardedJson,
    LOCAL_CAPABILITIES,
)
from ianest_extended import cli
from ianest_extended.cli import _build_parser


class CatalogCore:
    def list_capabilities(self):
        return {
            "core_version": "0.4.0",
            "capabilities": [
                {
                    "name": "prompt.run",
                    "summary": "declaracion inferior sustituida",
                    "identity": True,
                    "streaming": False,
                    "params": [{"name": "prompt", "future": "kept"}],
                    "rest": {"path": "/prompt/run", "method": "POST"},
                    "cli": None,
                    "mcp": None,
                },
                {
                    "name": "future.inspect",
                    "summary": "capacidad que extended desconoce",
                    "identity": False,
                    "streaming": False,
                    "params": [],
                    "rest": {"path": "/future/inspect", "method": "GET"},
                    "cli": None,
                    "mcp": {"tool": "future.inspect"},
                    "field_from_future_core": {"kept": [1, 2, 3]},
                },
            ],
        }


class OfflineCore:
    def list_capabilities(self):
        raise CoreConnectionError("core inalcanzable", "core_url")


def _service(tmp_path, core):
    config = ExtendedConfig(
        core_url="http://127.0.0.1:1",
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        embedding_dimension=2,
    )
    return ExtendedService(ExtendedComposition(config, core=core))


def test_own_catalog_declares_all_implemented_capabilities_and_explicit_gaps():
    """Criterios 1 y forma local: propias visibles; previstas ausentes."""
    by_name = {item.name: item for item in LOCAL_CAPABILITIES}

    assert "memory.recall" in by_name
    assert "knowledge.ingest" in by_name
    assert "knowledge.retrieve" not in by_name
    assert "knowledge.corpus.list" not in by_name
    assert all(item.rest is None and item.mcp is None for item in by_name.values())


def test_fusion_passes_unknown_core_capability_and_preserves_it(tmp_path):
    """Criterios 2, 4 y 5: desconocida, intacta y con procedencia."""
    result = _service(tmp_path, CatalogCore()).capability_list()
    names = {item["name"] for item in result["capabilities"]}
    future = next(
        item for item in result["capabilities"] if item["name"] == "future.inspect"
    )

    assert {"memory.recall", "knowledge.ingest"} <= names
    assert future == {
        "name": "future.inspect",
        "summary": "capacidad que extended desconoce",
        "identity": False,
        "streaming": False,
        "params": [],
        "rest": {"path": "/future/inspect", "method": "GET"},
        "cli": None,
        "mcp": {"tool": "future.inspect"},
        "field_from_future_core": {"kept": [1, 2, 3]},
        "provenance": "forwarded",
    }
    assert result["extended_version"] == "0.0.0"
    assert result["core_version"] == "0.4.0"
    assert {item["provenance"] for item in result["capabilities"]} == {
        "own",
        "overridden",
        "forwarded",
    }


def test_overridden_capability_appears_once_with_extended_declaration(tmp_path):
    """Criterio 3: una sobreescritura sustituye la declaracion inferior."""
    result = _service(tmp_path, CatalogCore()).capability_list()
    prompts = [
        item for item in result["capabilities"] if item["name"] == "prompt.run"
    ]

    assert len(prompts) == 1
    assert prompts[0]["provenance"] == "overridden"
    assert prompts[0]["summary"] == "ejecuta un prompt enriquecido"


def test_offline_core_returns_local_catalog_and_typed_error(tmp_path):
    """Criterio 9: degradacion honesta, no catalogo parcial fingido."""
    result = _service(tmp_path, OfflineCore()).capability_list()

    names = {item["name"] for item in result["capabilities"]}
    assert {"memory.recall", "knowledge.ingest"} <= names
    assert result["core_version"] is None
    assert result["error"] == {
        "type": "CoreConnectionError",
        "message": "core inalcanzable",
        "field": "core_url",
        "origin": "ia_nest_extended",
        "request_id": None,
    }


def test_cli_help_for_own_capability_is_derived_from_catalog():
    """Criterio 7: resumen y descripcion proceden de la declaracion."""
    declared = next(item for item in LOCAL_CAPABILITIES if item.name == "memory.recall")
    parser = _build_parser()
    root = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    memory = root.choices["memory"]
    actions = next(
        action
        for action in memory._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    recall = actions.choices["recall"]
    help_by_action = {item.dest: item.help for item in actions._choices_actions}
    prompt_param = next(item for item in declared.params if item.name == "prompt")
    prompt_action = next(
        item for item in recall._actions if item.dest == "prompt"
    )

    assert help_by_action["recall"] == declared.summary
    assert recall.description == declared.cli.description
    assert prompt_action.help == prompt_param.summary


def test_building_cli_parser_does_not_construct_or_call_core(monkeypatch):
    """Criterio 10: construir el parser es una operacion puramente local."""
    def forbidden(*args, **kwargs):
        raise AssertionError("el parser intento construir el cliente del core")

    monkeypatch.setattr(ExtendedComposition, "core", forbidden)

    parser = _build_parser()

    assert parser.prog == "ianest-extended"


def test_unknown_action_in_local_group_remains_invocable_without_catalog(
    monkeypatch,
    capsys,
):
    """Criterio 8: conocer la accion nunca es condicion para invocarla."""
    calls = []

    class Service:
        def forward(self, name, payload=None, *, method=None):
            calls.append((name, payload, method))
            return ForwardedJson({"forwarded": name})

    monkeypatch.setattr(ExtendedConfig, "from_env", lambda **kwargs: object())
    monkeypatch.setattr(
        ExtendedService,
        "from_config",
        lambda config: Service(),
    )

    code = cli.main(["memory", "future", "--json"])

    assert code == 0
    assert calls == [("memory.future", None, None)]
    assert '"forwarded": "memory.future"' in capsys.readouterr().out


def test_forwarded_static_catalog_is_gone():
    """Criterio 6: ninguna piel ni prueba depende de la lista interina."""
    root = Path(__file__).resolve().parents[1]
    sources = [
        *(root / "src").rglob("*.py"),
        *(root / "tests").rglob("*.py"),
    ]

    assert not [
        path
        for path in sources
        if "FORWARDED" + "_CAPABILITIES" in path.read_text(encoding="utf-8")
    ]
