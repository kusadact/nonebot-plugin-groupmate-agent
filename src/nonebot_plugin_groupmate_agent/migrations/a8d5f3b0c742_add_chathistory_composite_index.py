"""add chathistory composite index

迁移 ID: a8d5f3b0c742
父迁移: f6a2c8d4e901
创建时间: 2026-04-10 10:35:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a8d5f3b0c742"
down_revision: str | Sequence[str] | None = "f6a2c8d4e901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nonebot_plugin_groupmate_agent_chathistory"
OLD_INDEX = "ix_chat_session_time"
INDEX = "ix_nonebot_plugin_groupmate_agent_chathistory_session_time"


def upgrade(name: str = "") -> None:
    if name:
        return

    inspector = sa.inspect(op.get_bind())
    if TABLE not in set(inspector.get_table_names()):
        return

    indexes = {idx["name"] for idx in inspector.get_indexes(TABLE)}
    if INDEX in indexes:
        return
    if OLD_INDEX in indexes:
        op.drop_index(OLD_INDEX, table_name=TABLE)

    op.create_index(
        INDEX,
        TABLE,
        ["session_id", "created_at"],
        unique=False,
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_index(
        INDEX,
        table_name=TABLE,
    )
