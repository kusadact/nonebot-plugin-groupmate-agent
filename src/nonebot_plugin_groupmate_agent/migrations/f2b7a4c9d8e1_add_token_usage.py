"""add token usage

迁移 ID: f2b7a4c9d8e1
父迁移: a8d5f3b0c742
创建时间: 2026-07-09

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b7a4c9d8e1"
down_revision: str | Sequence[str] | None = "a8d5f3b0c742"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nonebot_plugin_groupmate_agent_tokenusage"


def upgrade(name: str = "") -> None:
    if name:
        return

    inspector = sa.inspect(op.get_bind())
    if TABLE in set(inspector.get_table_names()):
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("session_type", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("user_name", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nonebot_plugin_groupmate_agent_tokenusage")),
        info={"bind_key": "nonebot_plugin_groupmate_agent"},
    )
    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_nonebot_plugin_groupmate_agent_tokenusage_created_at"),
            ["created_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_nonebot_plugin_groupmate_agent_tokenusage_model"),
            ["model"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_nonebot_plugin_groupmate_agent_tokenusage_request_id"),
            ["request_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_nonebot_plugin_groupmate_agent_tokenusage_session_id"),
            ["session_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_nonebot_plugin_groupmate_agent_tokenusage_session_type"),
            ["session_type"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_nonebot_plugin_groupmate_agent_tokenusage_user_id"),
            ["user_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_nonebot_plugin_groupmate_agent_tokenusage_session_time",
            ["session_id", "created_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_nonebot_plugin_groupmate_agent_tokenusage_user_time",
            ["user_id", "created_at"],
            unique=False,
        )


def downgrade(name: str = "") -> None:
    if name:
        return

    inspector = sa.inspect(op.get_bind())
    if TABLE not in set(inspector.get_table_names()):
        return

    op.drop_table(TABLE)
