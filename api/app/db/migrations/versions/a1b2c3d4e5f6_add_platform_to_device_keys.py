"""expand platform constraint and add platform to device_keys

Revision ID: a1b2c3d4e5f6
Revises: 02234c7da915
Create Date: 2026-09-21 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "02234c7da915"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update check constraint on users table
    op.drop_constraint("ck_users_platform", "users", type_="check")
    op.create_check_constraint(
        "ck_users_platform",
        "users",
        "platform IN ('slack', 'teams', 'keycloak', 'web')",
    )

    # 2. Add platform column and check constraint to device_keys table
    op.add_column(
        "device_keys",
        sa.Column("platform", sa.Text(), nullable=False, server_default="web"),
    )
    op.create_check_constraint(
        "ck_device_keys_platform",
        "device_keys",
        "platform IN ('slack', 'teams', 'keycloak', 'web')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_device_keys_platform", "device_keys", type_="check")
    op.drop_column("device_keys", "platform")
    op.drop_constraint("ck_users_platform", "users", type_="check")
    op.create_check_constraint(
        "ck_users_platform",
        "users",
        "platform IN ('slack', 'teams')",
    )
