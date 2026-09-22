from dataclasses import replace
from types import SimpleNamespace

import pytest

from ianest_extended import (
    EngramWrite,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    MemoryIdentity,
    Principal,
    SessionAlreadyExistsError,
    SessionStatus,
)
from ianest_extended import cli
from ianest_extended.identity import remember_session_id

from .fakes import InMemoryStore


def _config(tmp_path, **changes):
    return ExtendedConfig(
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        catalog_cache_path=tmp_path / "catalog.json",
        embedding_dimension=2,
        rag_enabled=False,
        write_back_enabled=False,
        **changes,
    )


def _service(tmp_path):
    config = _config(tmp_path)
    store = InMemoryStore()
    return config, store, ExtendedService(
        ExtendedComposition(config, memory_store=store)
    )


def test_session_surface_is_user_scoped_and_filters_explicit_states(tmp_path):
    _, store, service = _service(tmp_path)
    first = MemoryIdentity(user_id="first")
    second = MemoryIdentity(user_id="second")
    service.session_new(first, session_id="shared")
    service.session_new(second, session_id="shared")
    store.sessions[("first", "shared")] = replace(
        store.sessions[("first", "shared")],
        status=SessionStatus.ARCHIVED,
        archived_at=store.sessions[("first", "shared")].last_activity_at,
    )

    assert service.session_list(first) == {"sessions": []}
    archived = service.session_list(first, status="archivada")["sessions"]
    assert [item["session_id"] for item in archived] == ["shared"]
    assert service.session_list(second)["sessions"][0]["session_id"] == "shared"
    shown = service.session_show(first, "shared")["session"]
    assert shown["status"] == "archivada"
    assert shown["archived_at"] is not None


def test_session_new_accepts_client_id_or_generates_and_rejects_duplicate(tmp_path):
    _, _, service = _service(tmp_path)
    identity = MemoryIdentity(user_id="u")

    selected = service.session_new(identity, session_id="cine_20260926")
    generated = service.session_new(identity)

    assert selected["session"]["session_id"] == "cine_20260926"
    assert generated["session"]["session_id"]
    assert generated["session"]["session_id"] != "cine_20260926"
    with pytest.raises(SessionAlreadyExistsError) as exc_info:
        service.session_new(identity, session_id="cine_20260926")
    assert "ya existe" in exc_info.value.message


def test_session_title_comes_only_from_latest_summary_and_is_word_cut(tmp_path):
    _, store, service = _service(tmp_path)
    identity = MemoryIdentity(user_id="u", session_id="thread")
    created = service.session_new(identity, session_id="thread")["session"]
    assert created["title"] is None
    first = store.write(
        Principal.EXTENDED,
        EngramWrite(type_name="dialog", content="turno", identity=identity),
    )
    summary = (
        "Este es el resumen mas reciente del hilo y contiene suficientes "
        "palabras para superar con claridad el limite publico del titulo"
    )
    store.write_thread_summary(
        Principal.EXTENDED,
        identity=identity,
        content=summary,
        source_ids=(first.id,),
        source_trace_id="summary",
    )

    title = service.session_show(identity, "thread")["session"]["title"]
    assert title == "Este es el resumen mas reciente del hilo y contiene suficientes palabras para"
    assert len(title) <= 80
    assert not title.endswith("...")


def test_cli_session_precedence_and_new_becomes_remembered(tmp_path):
    path = tmp_path / "session_id"
    remember_session_id(path, "file-session")
    store = InMemoryStore()
    env_config = _config(tmp_path, cli_session_id="env-session")
    service = ExtendedService(
        ExtendedComposition(env_config, memory_store=store)
    )
    common = dict(user_id=None, service=None, namespace=None, domain=None)

    explicit = cli._identity(
        service,
        env_config,
        SimpleNamespace(session_id="flag-session", **common),
    )
    from_env = cli._identity(
        service,
        env_config,
        SimpleNamespace(session_id=None, **common),
    )
    file_config = _config(tmp_path)
    file_service = ExtendedService(
        ExtendedComposition(file_config, memory_store=store)
    )
    from_file = cli._identity(
        file_service,
        file_config,
        SimpleNamespace(session_id=None, **common),
    )

    assert explicit.session_id == "flag-session"
    assert from_env.session_id == "env-session"
    assert from_file.session_id == "file-session"

    args = SimpleNamespace(user_id="u", session_id="new-thread", json=True)
    assert cli._session_new(file_service, file_config, args) == 0
    assert path.read_text(encoding="ascii").strip() == "new-thread"


def test_cli_thread_notice_uses_stderr_and_leaves_stdout_clean(tmp_path, capsys):
    config, _, service = _service(tmp_path)
    remember_session_id(config.session_state_path, "thread-on-stderr")
    args = SimpleNamespace(
        prompt="hola",
        use_memory=False,
        use_rag=False,
        user_id=None,
        session_id=None,
        service=None,
        namespace=None,
        domain=None,
        json=False,
    )

    assert cli._memory_recall(service, config, args) == 0

    captured = capsys.readouterr()
    assert captured.out == "(sin contexto recuperado)\n"
    assert captured.err == "Sesion: thread-on-stderr\n"
