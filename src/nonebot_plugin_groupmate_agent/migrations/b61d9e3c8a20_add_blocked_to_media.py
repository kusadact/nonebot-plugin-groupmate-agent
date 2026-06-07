"""add blocked flag to media storage

迁移 ID: b61d9e3c8a20
父迁移: 9f2a8c1d4b6e
创建时间: 2026-02-28 19:15:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b61d9e3c8a20"
down_revision: str | Sequence[str] | None = "9f2a8c1d4b6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "nonebot_plugin_groupmate_agent_mediastorage" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("nonebot_plugin_groupmate_agent_mediastorage")}
    if "blocked" in columns:
        return

    with op.batch_alter_table("nonebot_plugin_groupmate_agent_mediastorage", schema=None) as batch_op:
        batch_op.add_column(sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_index(batch_op.f("ix_nonebot_plugin_groupmate_agent_mediastorage_blocked"), ["blocked"], unique=False)


def downgrade(name: str = "") -> None:
    if name:
        return
    with op.batch_alter_table("nonebot_plugin_groupmate_agent_mediastorage", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_nonebot_plugin_groupmate_agent_mediastorage_blocked"))
        batch_op.drop_column("blocked")
