"""add daily_loss_used to userrelation

迁移 ID: d8e1a4f6c920
父迁移: c4a7d2f9b305
创建时间: 2026-03-03 10:40:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8e1a4f6c920"
down_revision: str | Sequence[str] | None = "c4a7d2f9b305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nonebot_plugin_groupmate_agent_userrelation"
COLUMN = "daily_loss_used"


def upgrade(name: str = "") -> None:
    if name:
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns(TABLE)}
    if COLUMN in columns:
        return

    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.add_column(sa.Column(COLUMN, sa.Float(), nullable=False, server_default="0"))


def downgrade(name: str = "") -> None:
    if name:
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns(TABLE)}
    if COLUMN not in columns:
        return

    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.drop_column(COLUMN)
