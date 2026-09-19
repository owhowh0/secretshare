"""Migrations run on container start (app.db.migrate).

Unit tests stub Alembic; the DB-backed test applies the real migrations to
TEST_DATABASE_URL and checks the audit table exists afterwards.
"""

import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

import app.db.migrate as migrate
import pytest
from app.core.config import Settings
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

API_DIR = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("TEST_DATABASE_URL")


class TestRunMigrations:
    def test_skips_without_database_url(self, monkeypatch):
        calls = []
        monkeypatch.setattr(migrate, "get_settings", lambda: Settings(_env_file=None, database_url=""))
        monkeypatch.setattr(migrate.command, "upgrade", lambda *a: calls.append(a))

        assert migrate.run_migrations() is False
        assert calls == []

    def test_upgrades_to_head_when_database_is_configured(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            migrate,
            "get_settings",
            lambda: Settings(_env_file=None, database_url="postgresql+asyncpg://u:p@db/app"),
        )
        monkeypatch.setattr(migrate.command, "upgrade", lambda cfg, rev: calls.append((cfg, rev)))

        assert migrate.run_migrations() is True
        [(config, revision)] = calls
        assert revision == "head"
        assert Path(config.config_file_name) == API_DIR / "alembic.ini"

    def test_migration_failure_propagates(self, monkeypatch):
        # The container must not start serving on a half-migrated schema.
        monkeypatch.setattr(
            migrate,
            "get_settings",
            lambda: Settings(_env_file=None, database_url="postgresql+asyncpg://u:p@db/app"),
        )

        def _boom(*args):
            raise RuntimeError("migration failed")

        monkeypatch.setattr(migrate.command, "upgrade", _boom)

        with pytest.raises(RuntimeError):
            migrate.run_migrations()

    def test_config_points_at_real_migrations(self):
        config = migrate.alembic_config()
        script_location = Path(config.get_main_option("script_location"))

        assert migrate.ALEMBIC_INI.is_file()
        assert (script_location / "env.py").is_file()
        assert any((script_location / "versions").glob("*.py"))

    def test_config_holds_no_credentials(self):
        # The URL carries the password; it must come from the environment only.
        assert migrate.alembic_config().get_main_option("sqlalchemy.url") in ("", None)


class TestDockerImage:
    """The image must ship alembic.ini and migrate before uvicorn starts."""

    dockerfile = (API_DIR / "Dockerfile").read_text(encoding="utf-8")

    def test_alembic_ini_is_copied(self):
        assert re.search(r"^COPY\b.*\balembic\.ini\b", self.dockerfile, re.M)

    def test_alembic_ini_is_not_dockerignored(self):
        ignored = (API_DIR / ".dockerignore").read_text(encoding="utf-8").split()
        assert "alembic.ini" not in ignored and "*.ini" not in ignored

    def test_cmd_migrates_before_serving(self):
        cmd = next(line for line in self.dockerfile.splitlines() if line.startswith("CMD"))

        assert "python -m app.db.migrate &&" in cmd
        assert cmd.index("app.db.migrate") < cmd.index("uvicorn")
        assert "exec uvicorn" in cmd


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not set")
class TestAgainstDatabase:
    def _run_migrate(self) -> subprocess.CompletedProcess:
        # A separate process, exactly as the container runs it; running Alembic
        # in-process would let env.py's fileConfig reconfigure pytest's logging.
        env = {**os.environ, "DATABASE_URL": DATABASE_URL}
        return subprocess.run(
            [sys.executable, "-m", "app.db.migrate"],
            cwd=API_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_upgrade_creates_audit_table_and_is_idempotent(self):
        first = self._run_migrate()
        assert first.returncode == 0, first.stderr
        second = self._run_migrate()  # already at head: a no-op
        assert second.returncode == 0, second.stderr

        async def _tables() -> set[str]:
            engine = create_async_engine(DATABASE_URL)
            try:
                async with engine.connect() as conn:
                    return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
            finally:
                await engine.dispose()

        tables = asyncio.run(_tables())
        assert {"audit_events", "users", "device_keys", "alembic_version"} <= tables

