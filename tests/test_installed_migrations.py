from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ianest_extended.migrations import MIGRATION_NAMES, migration_resource


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_PARTS = ("src", "ianest_extended", "db", "migrations")


def test_migrations_are_reachable_in_editable_installation():
    for name in MIGRATION_NAMES:
        sql = migration_resource(name).read_text(encoding="ascii")
        assert "CREATE" in sql


def test_wheel_install_contains_reachable_migrations(tmp_path):
    source = tmp_path / "source"
    wheelhouse = tmp_path / "wheelhouse"
    installed = tmp_path / "installed"
    source.mkdir()
    shutil.copy2(ROOT / "pyproject.toml", source)
    shutil.copy2(ROOT / "README.md", source)
    shutil.copytree(
        ROOT / "src",
        source / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    wheelhouse.mkdir()
    installed.mkdir()

    build_python = Path(sys.base_prefix) / "bin" / "python3.13"
    if not build_python.is_file():
        build_python = Path(sys.executable)
    built = subprocess.run(
        [
            str(build_python),
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
            str(source),
        ],
        capture_output=True,
        text=True,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    wheels = list(wheelhouse.glob("ianest_extended-*.whl"))
    assert len(wheels) == 1

    installed_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--target",
            str(installed),
            str(wheels[0]),
        ],
        capture_output=True,
        text=True,
    )
    assert installed_result.returncode == 0, (
        installed_result.stdout + installed_result.stderr
    )

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, ianest_extended; "
                "from ianest_extended.adapters.postgres import "
                "_default_migration_path as memory; "
                "from ianest_extended.adapters.rag_postgres import "
                "_default_migration_path as rag, "
                "_default_domain_migration_path as domains; "
                "print(json.dumps({'package': ianest_extended.__file__, "
                "'sql': [resource().read_text(encoding='ascii') "
                "for resource in (memory, rag, domains)]}))"
            ),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(installed)},
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    payload = json.loads(probe.stdout)
    assert Path(payload["package"]).is_relative_to(installed)
    assert len(payload["sql"]) == len(MIGRATION_NAMES)
    assert "CREATE TABLE IF NOT EXISTS memory_types" in payload["sql"][0]
    assert "CREATE TABLE IF NOT EXISTS rag_chunks" in payload["sql"][1]
    assert "CREATE TABLE IF NOT EXISTS rag_corpus_domains" in payload["sql"][2]


def test_repository_has_one_copy_of_each_migration():
    found = sorted(
        path.relative_to(ROOT).parts
        for path in ROOT.rglob("*.sql")
        if path.name in MIGRATION_NAMES
    )

    assert found == sorted((*RESOURCE_PARTS, name) for name in MIGRATION_NAMES)
