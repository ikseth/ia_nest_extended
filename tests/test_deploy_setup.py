from __future__ import annotations

import os
import subprocess
from pathlib import Path


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
    }
    return config, env, install_root, bin_dir, log_path


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
