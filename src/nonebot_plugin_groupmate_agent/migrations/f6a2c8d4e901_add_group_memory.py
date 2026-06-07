"""add group memory

迁移 ID: f6a2c8d4e901
父迁移: e3b7c9a1d502
创建时间: 2026-04-10 10:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f6a2c8d4e901"
down_revision: str | Sequence[str] | None = "e3b7c9a1d502"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "nonebot_plugin_groupmate_agent_groupmemory" in set(inspector.get_table_names()):
        return

    op.create_table(
        "nonebot_plugin_groupmate_agent_groupmemory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("msg_count_at_last_update", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nonebot_plugin_groupmate_agent_groupmemory")),
        info={"bind_key": "nonebot_plugin_groupmate_agent"},
    )
    with op.batch_alter_table("nonebot_plugin_groupmate_agent_groupmemory", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_nonebot_plugin_groupmate_agent_groupmemory_session_id"), ["session_id"], unique=True)
        batch_op.create_index(batch_op.f("ix_nonebot_plugin_groupmate_agent_groupmemory_updated_at"), ["updated_at"], unique=False)


def downgrade(name: str = "") -> None:
    if name:
        return

    with op.batch_alter_table("nonebot_plugin_groupmate_agent_groupmemory", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_nonebot_plugin_groupmate_agent_groupmemory_updated_at"))
        batch_op.drop_index(batch_op.f("ix_nonebot_plugin_groupmate_agent_groupmemory_session_id"))

    op.drop_table("nonebot_plugin_groupmate_agent_groupmemory")
