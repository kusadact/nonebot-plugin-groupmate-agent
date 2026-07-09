"""add token usage cache creation

迁移 ID: b7c4e2a9d103
父迁移: f2b7a4c9d8e1
创建时间: 2026-07-09

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c4e2a9d103"
down_revision: str | Sequence[str] | None = "f2b7a4c9d8e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nonebot_plugin_groupmate_agent_tokenusage"
COLUMN = "cache_creation_tokens"


def upgrade(name: str = "") -> None:
    if name:
        return

    inspector = sa.inspect(op.get_bind())
    if TABLE not in set(inspector.get_table_names()):
        return
    if COLUMN in {column["name"] for column in inspector.get_columns(TABLE)}:
        return

    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.add_column(sa.Column(COLUMN, sa.Integer(), nullable=False, server_default="0"))


def downgrade(name: str = "") -> None:
    if name:
        return

    inspector = sa.inspect(op.get_bind())
    if TABLE not in set(inspector.get_table_names()):
        return
    if COLUMN not in {column["name"] for column in inspector.get_columns(TABLE)}:
        return

    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.drop_column(COLUMN)
