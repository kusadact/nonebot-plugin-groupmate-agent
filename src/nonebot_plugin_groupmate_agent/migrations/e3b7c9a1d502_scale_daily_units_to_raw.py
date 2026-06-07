"""scale daily favorability units to raw

迁移 ID: e3b7c9a1d502
父迁移: d8e1a4f6c920
创建时间: 2026-03-03 11:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3b7c9a1d502"
down_revision: str | Sequence[str] | None = "d8e1a4f6c920"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nonebot_plugin_groupmate_agent_userrelation"
MIGRATION_STATE_TABLE = "nonebot_plugin_groupmate_agent_migration_state"


def _daily_units_already_scaled() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if MIGRATION_STATE_TABLE not in set(inspector.get_table_names()):
        return False

    exists = bind.execute(
        sa.text(f"SELECT 1 FROM {MIGRATION_STATE_TABLE} WHERE key = 'daily_units_scaled' LIMIT 1")
    ).first()
    op.drop_table(MIGRATION_STATE_TABLE)
    return exists is not None


def upgrade(name: str = "") -> None:
    if name:
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE not in tables:
        return
    if _daily_units_already_scaled():
        return

    columns = {col["name"] for col in inspector.get_columns(TABLE)}
    required = {"daily_gain_used", "daily_loss_used", "daily_bypass_used", "daily_gain_bank", "daily_cap"}
    if not required.issubset(columns):
        return

    # 旧版本按映射分存储（日上限=7）。这里统一放大到 raw 单位。
    op.execute(
        sa.text(
            f"""
            UPDATE {TABLE}
            SET
                daily_gain_used = daily_gain_used * 10,
                daily_loss_used = daily_loss_used * 10,
                daily_bypass_used = daily_bypass_used * 10,
                daily_gain_bank = daily_gain_bank * 10,
                daily_cap = daily_cap * 10
            """
        )
    )

    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.alter_column("daily_cap", server_default="70")


def downgrade(name: str = "") -> None:
    if name:
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns(TABLE)}
    required = {"daily_gain_used", "daily_loss_used", "daily_bypass_used", "daily_gain_bank", "daily_cap"}
    if not required.issubset(columns):
        return

    op.execute(
        sa.text(
            f"""
            UPDATE {TABLE}
            SET
                daily_gain_used = daily_gain_used / 10,
                daily_loss_used = daily_loss_used / 10,
                daily_bypass_used = daily_bypass_used / 10,
                daily_gain_bank = daily_gain_bank / 10,
                daily_cap = daily_cap / 10
            """
        )
    )

    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.alter_column("daily_cap", server_default="7")
