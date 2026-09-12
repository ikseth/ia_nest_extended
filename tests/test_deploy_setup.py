from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "deploy" / "setup.sh"
EXAMPLE = ROOT / "deploy" / "ejemplo.setup.conf"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="ascii")
    path.chmod(0o755)


def _deployment(
    tmp_path: Path,
    *,
    migrate_fails: bool = False,
    network_fails: bool = False,
):
    install_root = tmp_path / "opt" / "ia_nest"
    bin_dir = tmp_path / "bin"
    systemd_dir = tmp_path / "systemd"
    venv_bin = install_root / "state" / "extended" / "test" / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    bin_dir.mkdir()
    systemd_dir.mkdir()
    log_path = tmp_path / "calls.log"
    _write_executable(
        venv_bin / "python",
        "#!/usr/bin/env bash\n"
        "if [[ ${1:-} == -m && ${2:-} == pip ]]; then exit 0; fi\n"
        "exit 0\n",
    )
    failure = (
        "echo 'connection refused: host db.invalid' >&2; exit 23"
        if migrate_fails
        else "exit 0"
    )
    _write_executable(
        venv_bin / "ianest-extended",
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$FAKE_CALL_LOG\"\n"
        "if [[ $* == *'knowledge '* ]]; then\n"
        "  grep -Fqx -- \"$*\" \"$FAKE_STATE_LOG\" 2>/dev/null || "
        "printf '%s\\n' \"$*\" >> \"$FAKE_STATE_LOG\"\n"
        "fi\n"
        "if [[ -n ${FAKE_FAIL_CORPUS:-} && "
        "\"$*\" == *\"knowledge ingest --corpus ${FAKE_FAIL_CORPUS} \"* ]]; then\n"
        "  echo \"simulated ingest failure for ${FAKE_FAIL_CORPUS}\" >&2\n"
        "  exit 31\n"
        "fi\n"
        "if [[ \"$*\" == *'runtime migrate'* ]]; then " + failure + "; fi\n"
        "exit 0\n",
    )
    for name in ("ianest-extended-rest", "ianest-extended-mcp"):
        _write_executable(venv_bin / name, "#!/usr/bin/env bash\nexit 0\n")
    fake_path = tmp_path / "fake-path"
    fake_path.mkdir()
    curl_result = (
        "echo 'WARNING: Retrying package index' >&2; exit 19"
        if network_fails
        else "exit 0"
    )
    _write_executable(
        fake_path / "curl",
        "#!/usr/bin/env bash\n" + curl_result + "\n",
    )
    for name in ("docker", "podman", "podman-compose"):
        _write_executable(
            fake_path / name,
            "#!/usr/bin/env bash\n"
            "printf 'runtime:%s\\n' \"$0\" >> \"$FAKE_CALL_LOG\"\n"
            "exit 99\n",
        )
    config = tmp_path / "setup.conf"
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "manual.md").write_text("texto reproducible", encoding="ascii")
    config.write_text(
        "\n".join(
            (
                "INSTANCE_NAME=test",
                "STORE_DSN=postgresql://user:secret@db.invalid:5432/extended",
                "PROVISION_STORE=false",
                "SERVICE_INSTALL=false",
                "SERVICE_ENABLE=false",
                "VERIFY=skip",
                f"CORPUS_PATH={corpus}",
                "CORPUS_NAME=manual",
                "CORPUS_DOMAINS=linux,codigo",
                f"OPERATOR_USER={os.environ.get('USER', os.getlogin())}",
                "REPLACE_CONFIG=false",
            )
        )
        + "\n",
        encoding="ascii",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_path}:{os.environ['PATH']}",
        "IANEST_INSTALL_ROOT": str(install_root),
        "IANEST_BIN_DIR": str(bin_dir),
        "IANEST_SYSTEMD_DIR": str(systemd_dir),
        "FAKE_CALL_LOG": str(log_path),
        "FAKE_STATE_LOG": str(tmp_path / "fake-state.log"),
    }
    return config, env, install_root, bin_dir, log_path


def _use_manifest(config: Path, manifest: Path) -> None:
    lines = [
        line
        for line in config.read_text(encoding="ascii").splitlines()
        if not line.startswith(("CORPUS_PATH=", "CORPUS_NAME=", "CORPUS_DOMAINS="))
    ]
    lines.append(f"CORPUS_MANIFEST={manifest}")
    config.write_text("\n".join(lines) + "\n", encoding="ascii")


def _knowledge_calls(log_path: Path) -> list[str]:
    if not log_path.exists():
        return []
    return [
        line[line.index("knowledge ") :]
        for line in log_path.read_text(encoding="ascii").splitlines()
        if "knowledge " in line
    ]


def test_setup_is_valid_bash_and_example_resolves_without_effects():
    syntax = subprocess.run(["bash", "-n", str(SETUP)], capture_output=True, text=True)
    assert syntax.returncode == 0, syntax.stderr

    printed = subprocess.run(
        [str(SETUP), "--config", str(EXAMPLE), "--print-config"],
        capture_output=True,
        text=True,
    )

    assert printed.returncode == 0, printed.stderr
    assert "STORE_DSN=(oculto) (file)" in printed.stdout
    assert "PROVISION_STORE=false (file)" in printed.stdout
    assert "VERIFY=strict (file)" in printed.stdout


def test_extended_config_passes_through_in_order_snapshot_and_is_idempotent(tmp_path):
    config, env, install_root, _, _ = _deployment(tmp_path)
    with config.open("a", encoding="ascii") as stream:
        stream.write(
            "IANEST_EXTENDED_RAG_MIN_SCORE_DOMAIN=0.41\n"
            "IANEST_EXTENDED_TASK_TIMEOUT_SECONDS=not-validated-here\n"
            "IANEST_EXTENDED_RAG_MIN_SCORE_NO_DOMAIN=0.46\n"
        )

    first = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )
    config_dir = install_root / "config" / "extended" / "test"
    env_file = config_dir / "extended.env"
    first_environment = env_file.read_text(encoding="ascii")
    env_file.unlink()
    second = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )
    second_environment = env_file.read_text(encoding="ascii")

    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    inherited = [
        "IANEST_EXTENDED_RAG_MIN_SCORE_DOMAIN=0.41",
        "IANEST_EXTENDED_TASK_TIMEOUT_SECONDS=not-validated-here",
        "IANEST_EXTENDED_RAG_MIN_SCORE_NO_DOMAIN=0.46",
    ]
    env_lines = first_environment.splitlines()
    assert env_lines[-3:] == inherited
    assert env_lines.index(inherited[0]) > env_lines.index(
        "IANEST_EXTENDED_CATALOG_CACHE_PATH="
        f"{install_root}/state/extended/test/catalog_cache.json"
    )
    assert second_environment == first_environment
    snapshot_lines = (config_dir / "setup.conf").read_text(
        encoding="ascii"
    ).splitlines()
    assert snapshot_lines[-3:] == inherited


def test_unknown_unprefixed_config_key_fails_before_writing(tmp_path):
    config = tmp_path / "invalid.setup.conf"
    config.write_text("TYPO_RAG_MIN_SCORE=0.41\n", encoding="ascii")
    install_root = tmp_path / "untouched"
    env = {**os.environ, "IANEST_INSTALL_ROOT": str(install_root)}

    result = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert "clave desconocida 'TYPO_RAG_MIN_SCORE'" in result.stderr
    assert not install_root.exists()


def test_generated_extended_config_collision_is_typed_and_names_option(tmp_path):
    config = tmp_path / "collision.setup.conf"
    config.write_text("IANEST_EXTENDED_REST_PORT=9001\n", encoding="ascii")
    install_root = tmp_path / "untouched"
    env = {**os.environ, "IANEST_INSTALL_ROOT": str(install_root)}

    result = subprocess.run(
        [str(SETUP), "--config", str(config), "--print-config"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "configuration_collision" in result.stderr
    assert "IANEST_EXTENDED_REST_PORT" in result.stderr
    assert "REST_PORT / --rest-port" in result.stderr
    assert not install_root.exists()


def test_remote_store_path_is_idempotent_ingests_text_and_never_calls_runtime(tmp_path):
    config, env, install_root, bin_dir, log_path = _deployment(tmp_path)

    first = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )
    second = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    calls = log_path.read_text(encoding="ascii")
    assert "runtime:" not in calls
    assert calls.count("runtime migrate") == 2
    assert calls.count("knowledge ingest --corpus manual") == 2
    assert calls.count("knowledge confirm --corpus manual --domain linux") == 2
    assert calls.count("knowledge confirm --corpus manual --domain codigo") == 2
    config_dir = install_root / "config" / "extended" / "test"
    env_file = config_dir / "extended.env"
    assert env_file.is_file()
    assert ROOT not in env_file.parents
    assert env_file.stat().st_mode & 0o777 == 0o600
    assert "db.invalid" in env_file.read_text(encoding="ascii")
    wrapper = bin_dir / "ianest-extended"
    invoked = subprocess.run(
        [str(wrapper), "memory_type", "list"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert invoked.returncode == 0
    assert f"--env-file {env_file} memory_type list" in log_path.read_text(
        encoding="ascii"
    )


def test_manifest_ingests_n_corpora_in_file_order_with_relative_paths(tmp_path):
    config, env, _, _, log_path = _deployment(tmp_path)
    corpus_dir = tmp_path / "portable" / "texts"
    corpus_dir.mkdir(parents=True)
    for name in ("linux.txt", "scripting.txt", "domotica.txt"):
        (corpus_dir / name).write_text(name, encoding="ascii")
    manifest = tmp_path / "portable" / "corpora.txt"
    manifest.write_text(
        "# name | domains | path\n"
        "linux_docs | linux | texts/linux.txt\n"
        "scripting_docs | codigo, linux | texts/scripting.txt\n"
        "domotica_docs | domotica | texts/domotica.txt\n",
        encoding="ascii",
    )
    _use_manifest(config, manifest)

    result = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert _knowledge_calls(log_path) == [
        f"knowledge ingest --corpus linux_docs --domain linux {corpus_dir / 'linux.txt'}",
        "knowledge confirm --corpus linux_docs --domain linux",
        f"knowledge ingest --corpus scripting_docs --domain codigo --domain linux {corpus_dir / 'scripting.txt'}",
        "knowledge confirm --corpus scripting_docs --domain codigo",
        "knowledge confirm --corpus scripting_docs --domain linux",
        f"knowledge ingest --corpus domotica_docs --domain domotica {corpus_dir / 'domotica.txt'}",
        "knowledge confirm --corpus domotica_docs --domain domotica",
    ]


@pytest.mark.parametrize("legacy_key", ["CORPUS_PATH", "CORPUS_NAME", "CORPUS_DOMAINS"])
def test_manifest_is_exclusive_with_each_legacy_corpus_key(tmp_path, legacy_key):
    config, env, _, _, log_path = _deployment(tmp_path)
    corpus = tmp_path / "only.txt"
    corpus.write_text("text", encoding="ascii")
    manifest = tmp_path / "corpora.txt"
    manifest.write_text(f"one | linux | {corpus}\n", encoding="ascii")
    lines = config.read_text(encoding="ascii").splitlines()
    for index, line in enumerate(lines):
        if line.startswith(("CORPUS_PATH=", "CORPUS_NAME=", "CORPUS_DOMAINS=")):
            key = line.split("=", 1)[0]
            lines[index] = f"{key}=" if key != legacy_key else line
    lines.append(f"CORPUS_MANIFEST={manifest}")
    config.write_text("\n".join(lines) + "\n", encoding="ascii")

    result = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert "CORPUS_MANIFEST es excluyente" in result.stderr
    assert _knowledge_calls(log_path) == []


def test_no_corpus_configuration_preserves_no_ingestion_behavior(tmp_path):
    config, env, _, _, log_path = _deployment(tmp_path)
    lines = [
        line
        for line in config.read_text(encoding="ascii").splitlines()
        if not line.startswith(("CORPUS_PATH=", "CORPUS_NAME=", "CORPUS_DOMAINS="))
    ]
    config.write_text("\n".join(lines) + "\n", encoding="ascii")

    result = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert _knowledge_calls(log_path) == []


def test_manifest_is_fully_validated_before_first_ingestion(tmp_path):
    config, env, _, _, log_path = _deployment(tmp_path)
    corpus = tmp_path / "valid.txt"
    corpus.write_text("text", encoding="ascii")
    manifest = tmp_path / "corpora.txt"
    manifest.write_text(
        f"valid | linux | {corpus}\ninvalid | only-two-fields\n",
        encoding="ascii",
    )
    _use_manifest(config, manifest)

    result = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert f"{manifest}:2: se esperaban tres campos" in result.stderr
    assert _knowledge_calls(log_path) == []


def test_manifest_rejects_duplicate_corpus_name_before_ingestion(tmp_path):
    config, env, _, _, log_path = _deployment(tmp_path)
    corpus = tmp_path / "valid.txt"
    corpus.write_text("text", encoding="ascii")
    manifest = tmp_path / "corpora.txt"
    manifest.write_text(
        f"same | linux | {corpus}\nsame | codigo | {corpus}\n",
        encoding="ascii",
    )
    _use_manifest(config, manifest)

    result = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert "nombre de corpus repetido 'same'" in result.stderr
    assert _knowledge_calls(log_path) == []


def test_manifest_ingestion_failure_names_corpus_and_stops(tmp_path):
    config, env, _, _, log_path = _deployment(tmp_path)
    corpus = tmp_path / "valid.txt"
    corpus.write_text("text", encoding="ascii")
    manifest = tmp_path / "corpora.txt"
    manifest.write_text(
        f"first | linux | {corpus}\nsecond | codigo | {corpus}\nthird | domotica | {corpus}\n",
        encoding="ascii",
    )
    _use_manifest(config, manifest)
    env["FAKE_FAIL_CORPUS"] = "second"

    result = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert "simulated ingest failure for second" in result.stderr
    assert "fallo knowledge ingest para el corpus 'second'" in result.stderr
    calls = _knowledge_calls(log_path)
    assert any("--corpus first" in call for call in calls)
    assert any("--corpus second" in call for call in calls)
    assert not any("--corpus third" in call for call in calls)


def test_manifest_repetition_uses_identical_idempotency_keys(tmp_path):
    config, env, _, _, log_path = _deployment(tmp_path)
    corpus = tmp_path / "valid.txt"
    corpus.write_text("text", encoding="ascii")
    manifest = tmp_path / "corpora.txt"
    manifest.write_text(
        f"first | linux | {corpus}\nsecond | codigo,linux | {corpus}\n",
        encoding="ascii",
    )
    _use_manifest(config, manifest)

    first = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )
    second = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    calls = _knowledge_calls(log_path)
    assert calls[:5] == calls[5:]
    state = Path(env["FAKE_STATE_LOG"]).read_text(encoding="ascii").splitlines()
    assert len(state) == len(set(state)) == 5


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (" | linux | readable.txt", "nombre de corpus no puede estar vacio"),
        ("name | , | readable.txt", "contiene un dominio vacio"),
        ("name | linux | missing.txt", "ruta de corpus no legible"),
    ],
)
def test_manifest_rejects_empty_fields_and_unreadable_paths(tmp_path, line, message):
    config, env, _, _, log_path = _deployment(tmp_path)
    (tmp_path / "readable.txt").write_text("text", encoding="ascii")
    manifest = tmp_path / "corpora.txt"
    manifest.write_text(line + "\n", encoding="ascii")
    _use_manifest(config, manifest)

    result = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert message in result.stderr
    assert _knowledge_calls(log_path) == []


def test_existing_configuration_is_preserved_without_replace(tmp_path):
    config, env, install_root, _, _ = _deployment(tmp_path)
    first = subprocess.run([str(SETUP), "--config", str(config)], env=env)
    assert first.returncode == 0
    config.write_text(
        config.read_text(encoding="ascii").replace("db.invalid", "changed.invalid"),
        encoding="ascii",
    )

    second = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert second.returncode == 0, second.stderr
    assert "se preserva" in second.stdout
    env_file = install_root / "config" / "extended" / "test" / "extended.env"
    assert "db.invalid" in env_file.read_text(encoding="ascii")
    assert "changed.invalid" not in env_file.read_text(encoding="ascii")


def test_invalid_store_dsn_fails_with_exit_code_and_names_cause(tmp_path):
    config, env, _, _, _ = _deployment(tmp_path, migrate_fails=True)

    result = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert "almacen no accesible o migracion fallida" in result.stderr
    assert "connection refused: host db.invalid" in result.stderr


def test_package_index_network_failure_has_own_message_without_pip_retries(tmp_path):
    config, env, _, _, _ = _deployment(tmp_path, network_fails=True)

    result = subprocess.run(
        [str(SETUP), "--config", str(config)], env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert "red no disponible" in result.stderr
    assert "indice de paquetes de pip" in result.stderr
    assert "Retrying" not in result.stderr


def test_setup_waits_for_ports_and_units_have_restart_and_network_ordering():
    source = SETUP.read_text(encoding="ascii")

    assert "socket.create_connection" in source
    assert "wait_for_service \"$rest_unit\"" in source
    assert "wait_for_service \"$mcp_unit\"" in source
    assert "After=network-online.target" in source
    assert source.count("Restart=on-failure") == 2
    assert "systemctl enable \"$rest_unit\" \"$mcp_unit\"" in source


def test_provisioned_store_restarts_unless_explicitly_stopped():
    compose = (ROOT / "deploy" / "postgres.compose.yaml").read_text(
        encoding="ascii"
    )

    assert "restart: unless-stopped" in compose
