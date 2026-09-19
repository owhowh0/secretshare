"""
Applies pending Alembic migrations. Run before the API starts:

    python -m app.db.migrate

The container runs this on every start, so a fresh preview or staging database
gets its schema before the first request. Without it the audit_events table
never exists and every audit write fails (swallowed by AuditService, so the API
looks healthy while recording nothing).

Upgrading to head is idempotent: an up-to-date database is a no-op.
"""

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings

logger = logging.getLogger("secretshare.migrate")

# api/alembic.ini, which sits next to the app package both in the repo and in
# the image (/app/alembic.ini).
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    # script_location in the ini is relative; anchor it so the command works
    # from any working directory.
    config.set_main_option(
        "script_location", str(ALEMBIC_INI.parent / "app" / "db" / "migrations")
    )
    return config


def run_migrations() -> bool:
    """Upgrades the database to head. Returns False when there is no database."""
    if not get_settings().database_url:
        logger.warning("DATABASE_URL is not set — skipping migrations.")
        return False

    # env.py reads DATABASE_URL from Settings, so the password never has to be
    # written into the ini.
    command.upgrade(alembic_config(), "head")
    return True


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run_migrations()
    return 0


if __name__ == "__main__":
    sys.exit(main())
