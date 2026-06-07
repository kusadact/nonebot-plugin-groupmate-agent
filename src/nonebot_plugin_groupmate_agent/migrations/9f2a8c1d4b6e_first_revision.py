"""rename ai-groupmate tables to groupmate-agent

迁移 ID: 9f2a8c1d4b6e
父迁移: a1b2c3d4e5f6
创建时间: 2025-11-27 20:39:11.240822

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f2a8c1d4b6e"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = ("nonebot_plugin_groupmate_agent",)
depends_on: str | Sequence[str] | None = None

OLD_PREFIX = "nonebot_plugin_ai_groupmate"
NEW_PREFIX = "nonebot_plugin_groupmate_agent"

DIRECT_TABLE_SUFFIXES = ("chathistory", "mediastorage", "groupmemory")
OLD_RELATION_TABLE = f"{OLD_PREFIX}_userrelation"
OLD_RELATION_V2_TABLE = f"{OLD_PREFIX}_userrelation_v2"
NEW_RELATION_TABLE = f"{NEW_PREFIX}_userrelation"
MIGRATION_STATE_TABLE = f"{NEW_PREFIX}_migration_state"

POSTGRES_CONSTRAINT_RENAMES: tuple[tuple[str, str, str], ...] = (
    (f"pk_{OLD_PREFIX}_chathistory", f"pk_{NEW_PREFIX}_chathistory", f"{NEW_PREFIX}_chathistory"),
    (f"pk_{OLD_PREFIX}_mediastorage", f"pk_{NEW_PREFIX}_mediastorage", f"{NEW_PREFIX}_mediastorage"),
    (
        f"{OLD_PREFIX}_mediastorage_file_hash_key",
        f"{NEW_PREFIX}_mediastorage_file_hash_key",
        f"{NEW_PREFIX}_mediastorage",
    ),
    (f"pk_{OLD_PREFIX}_userrelation_v2", f"pk_{NEW_PREFIX}_userrelation", NEW_RELATION_TABLE),
    (
        f"uq_{OLD_PREFIX}_userrelation_v2_user_id",
        f"uq_{NEW_PREFIX}_userrelation_user_id",
        NEW_RELATION_TABLE,
    ),
    (f"pk_{OLD_PREFIX}_groupmemory", f"pk_{NEW_PREFIX}_groupmemory", f"{NEW_PREFIX}_groupmemory"),
)

INDEX_RENAMES: tuple[tuple[str, str, str, list[str], bool], ...] = (
    (
        f"ix_{OLD_PREFIX}_chathistory_created_at",
        f"ix_{NEW_PREFIX}_chathistory_created_at",
        f"{NEW_PREFIX}_chathistory",
        ["created_at"],
        False,
    ),
    (
        f"ix_{OLD_PREFIX}_chathistory_session_id",
        f"ix_{NEW_PREFIX}_chathistory_session_id",
        f"{NEW_PREFIX}_chathistory",
        ["session_id"],
        False,
    ),
    (
        f"ix_{OLD_PREFIX}_chathistory_user_id",
        f"ix_{NEW_PREFIX}_chathistory_user_id",
        f"{NEW_PREFIX}_chathistory",
        ["user_id"],
        False,
    ),
    (
        f"ix_{OLD_PREFIX}_chathistory_vectorized",
        f"ix_{NEW_PREFIX}_chathistory_vectorized",
        f"{NEW_PREFIX}_chathistory",
        ["vectorized"],
        False,
    ),
    ("ix_chat_session_time", f"ix_{NEW_PREFIX}_chathistory_session_time", f"{NEW_PREFIX}_chathistory", ["session_id", "created_at"], False),
    (
        f"ix_{OLD_PREFIX}_mediastorage_blocked",
        f"ix_{NEW_PREFIX}_mediastorage_blocked",
        f"{NEW_PREFIX}_mediastorage",
        ["blocked"],
        False,
    ),
    (
        f"ix_{OLD_PREFIX}_mediastorage_created_at",
        f"ix_{NEW_PREFIX}_mediastorage_created_at",
        f"{NEW_PREFIX}_mediastorage",
        ["created_at"],
        False,
    ),
    (
        f"ix_{OLD_PREFIX}_mediastorage_references",
        f"ix_{NEW_PREFIX}_mediastorage_references",
        f"{NEW_PREFIX}_mediastorage",
        ["references"],
        False,
    ),
    (
        f"ix_{OLD_PREFIX}_mediastorage_vectorized",
        f"ix_{NEW_PREFIX}_mediastorage_vectorized",
        f"{NEW_PREFIX}_mediastorage",
        ["vectorized"],
        False,
    ),
    (
        f"ix_{OLD_PREFIX}_userrelation_v2_cap_reset_at",
        f"ix_{NEW_PREFIX}_userrelation_cap_reset_at",
        NEW_RELATION_TABLE,
        ["cap_reset_at"],
        False,
    ),
    (
        f"ix_{OLD_PREFIX}_userrelation_v2_favorability",
        f"ix_{NEW_PREFIX}_userrelation_favorability",
        NEW_RELATION_TABLE,
        ["favorability"],
        False,
    ),
    (
        f"ix_{OLD_PREFIX}_userrelation_v2_favorability_raw",
        f"ix_{NEW_PREFIX}_userrelation_favorability_raw",
        NEW_RELATION_TABLE,
        ["favorability_raw"],
        False,
    ),
    (
        f"ix_{OLD_PREFIX}_userrelation_v2_last_interact_at",
        f"ix_{NEW_PREFIX}_userrelation_last_interact_at",
        NEW_RELATION_TABLE,
        ["last_interact_at"],
        False,
    ),
    (f"ix_{OLD_PREFIX}_userrelation_v2_state", f"ix_{NEW_PREFIX}_userrelation_state", NEW_RELATION_TABLE, ["state"], False),
    (f"ix_{OLD_PREFIX}_userrelation_v2_user_id", f"ix_{NEW_PREFIX}_userrelation_user_id", NEW_RELATION_TABLE, ["user_id"], False),
    (
        f"ix_{OLD_PREFIX}_groupmemory_session_id",
        f"ix_{NEW_PREFIX}_groupmemory_session_id",
        f"{NEW_PREFIX}_groupmemory",
        ["session_id"],
        True,
    ),
    (
        f"ix_{OLD_PREFIX}_groupmemory_updated_at",
        f"ix_{NEW_PREFIX}_groupmemory_updated_at",
        f"{NEW_PREFIX}_groupmemory",
        ["updated_at"],
        False,
    ),
)

POSTGRES_SEQUENCE_RENAMES: tuple[tuple[str, str], ...] = (
    (f"{OLD_PREFIX}_chathistory_msg_id_seq", f"{NEW_PREFIX}_chathistory_msg_id_seq"),
    (f"{OLD_PREFIX}_groupmemory_id_seq", f"{NEW_PREFIX}_groupmemory_id_seq"),
    (f"{OLD_PREFIX}_mediastorage_media_id_seq", f"{NEW_PREFIX}_mediastorage_media_id_seq"),
    (f"{OLD_PREFIX}_userrelation_v2_id_seq", f"{NEW_PREFIX}_userrelation_id_seq"),
)


def _quote(name: str) -> str:
    return op.get_bind().dialect.identifier_preparer.quote(name)


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _columns(table_name: str) -> set[str]:
    return {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table_name)}


def _has_relation(name: str, kind: str) -> bool:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    if kind not in {"i", "S"}:
        raise ValueError(f"unsupported PostgreSQL relation kind: {kind}")
    return (
        bind.execute(
            sa.text(
                f"""
                SELECT 1
                FROM pg_class cls
                JOIN pg_namespace n ON n.oid = cls.relnamespace
                WHERE cls.relkind = '{kind}'
                  AND cls.relname = :name
                  AND n.nspname = current_schema()
                LIMIT 1
                """
            ),
            {"name": name},
        ).first()
        is not None
    )


def _has_constraint(name: str) -> bool:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    return (
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_constraint c
                JOIN pg_namespace n ON n.oid = c.connamespace
                WHERE c.conname = :name
                  AND n.nspname = current_schema()
                LIMIT 1
                """
            ),
            {"name": name},
        ).first()
        is not None
    )


def _rename_table(old_name: str, new_name: str) -> None:
    if not _has_table(old_name) or _has_table(new_name):
        return
    op.rename_table(old_name, new_name)


def _rename_postgres_constraint(old_name: str, new_name: str, table_name: str) -> None:
    if _has_constraint(old_name) and not _has_constraint(new_name) and _has_table(table_name):
        op.execute(sa.text(f"ALTER TABLE {_quote(table_name)} RENAME CONSTRAINT {_quote(old_name)} TO {_quote(new_name)}"))


def _rename_postgres_index(old_name: str, new_name: str) -> None:
    if _has_relation(old_name, "i") and not _has_relation(new_name, "i"):
        op.execute(sa.text(f"ALTER INDEX {_quote(old_name)} RENAME TO {_quote(new_name)}"))


def _rename_postgres_sequence(old_name: str, new_name: str) -> None:
    if _has_relation(old_name, "S") and not _has_relation(new_name, "S"):
        op.execute(sa.text(f"ALTER SEQUENCE {_quote(old_name)} RENAME TO {_quote(new_name)}"))


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    indexes = {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if index_name in indexes:
        op.drop_index(index_name, table_name=table_name)


def _drop_table_if_exists(table_name: str) -> None:
    if _has_table(table_name):
        op.drop_table(table_name)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], unique: bool = False) -> None:
    indexes = {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def _rename_or_recreate_index(
    old_name: str,
    new_name: str,
    table_name: str,
    columns: list[str],
    unique: bool = False,
) -> None:
    if op.get_bind().dialect.name == "postgresql":
        _rename_postgres_index(old_name, new_name)
        return

    if not _has_table(table_name):
        return
    indexes = {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if old_name in indexes:
        op.drop_index(old_name, table_name=table_name)
    _create_index_if_missing(table_name, new_name, columns, unique)


def _create_core_tables_if_missing() -> None:
    if not _has_table(f"{NEW_PREFIX}_chathistory"):
        op.create_table(
            f"{NEW_PREFIX}_chathistory",
            sa.Column("msg_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("content_type", sa.String(), nullable=False),
            sa.Column("content", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("user_name", sa.String(), nullable=False),
            sa.Column("media_id", sa.Integer(), nullable=True),
            sa.Column("vectorized", sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint("msg_id", name=op.f(f"pk_{NEW_PREFIX}_chathistory")),
            info={"bind_key": NEW_PREFIX},
        )
        _create_index_if_missing(f"{NEW_PREFIX}_chathistory", f"ix_{NEW_PREFIX}_chathistory_created_at", ["created_at"])
        _create_index_if_missing(f"{NEW_PREFIX}_chathistory", f"ix_{NEW_PREFIX}_chathistory_session_id", ["session_id"])
        _create_index_if_missing(f"{NEW_PREFIX}_chathistory", f"ix_{NEW_PREFIX}_chathistory_user_id", ["user_id"])
        _create_index_if_missing(f"{NEW_PREFIX}_chathistory", f"ix_{NEW_PREFIX}_chathistory_vectorized", ["vectorized"])

    if not _has_table(f"{NEW_PREFIX}_mediastorage"):
        op.create_table(
            f"{NEW_PREFIX}_mediastorage",
            sa.Column("media_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("file_hash", sa.String(length=64), nullable=False),
            sa.Column("file_path", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("references", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(), nullable=False),
            sa.Column("vectorized", sa.Boolean(), nullable=False),
            sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.PrimaryKeyConstraint("media_id", name=op.f(f"pk_{NEW_PREFIX}_mediastorage")),
            sa.UniqueConstraint("file_hash"),
            info={"bind_key": NEW_PREFIX},
        )
        _create_index_if_missing(f"{NEW_PREFIX}_mediastorage", f"ix_{NEW_PREFIX}_mediastorage_blocked", ["blocked"])
        _create_index_if_missing(f"{NEW_PREFIX}_mediastorage", f"ix_{NEW_PREFIX}_mediastorage_created_at", ["created_at"])
        _create_index_if_missing(f"{NEW_PREFIX}_mediastorage", f"ix_{NEW_PREFIX}_mediastorage_references", ["references"])
        _create_index_if_missing(f"{NEW_PREFIX}_mediastorage", f"ix_{NEW_PREFIX}_mediastorage_vectorized", ["vectorized"])

    if not _has_table(NEW_RELATION_TABLE):
        op.create_table(
            NEW_RELATION_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("user_name", sa.String(), nullable=False),
            sa.Column("favorability", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("favorability_raw", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("state", sa.String(length=32), nullable=False, server_default="normal"),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("daily_gain_used", sa.Float(), nullable=False, server_default="0"),
            sa.Column("daily_loss_used", sa.Float(), nullable=False, server_default="0"),
            sa.Column("daily_bypass_used", sa.Float(), nullable=False, server_default="0"),
            sa.Column("daily_gain_bank", sa.Float(), nullable=False, server_default="0"),
            sa.Column("daily_cap", sa.Float(), nullable=False, server_default="70"),
            sa.Column("cap_reset_at", sa.DateTime(), nullable=False),
            sa.Column("last_interact_at", sa.DateTime(), nullable=False),
            sa.Column("last_penalty_at", sa.DateTime(), nullable=True),
            sa.Column("apology_counts", sa.JSON(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{NEW_PREFIX}_userrelation")),
            sa.UniqueConstraint("user_id", name=op.f(f"uq_{NEW_PREFIX}_userrelation_user_id")),
            info={"bind_key": NEW_PREFIX},
        )

    if not _has_table(f"{NEW_PREFIX}_groupmemory"):
        op.create_table(
            f"{NEW_PREFIX}_groupmemory",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("summary", sa.String(), nullable=False),
            sa.Column("msg_count_at_last_update", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{NEW_PREFIX}_groupmemory")),
            info={"bind_key": NEW_PREFIX},
        )
        _create_index_if_missing(f"{NEW_PREFIX}_groupmemory", f"ix_{NEW_PREFIX}_groupmemory_session_id", ["session_id"], unique=True)
        _create_index_if_missing(f"{NEW_PREFIX}_groupmemory", f"ix_{NEW_PREFIX}_groupmemory_updated_at", ["updated_at"])


def _mark_daily_units_scaled() -> None:
    if _has_table(MIGRATION_STATE_TABLE):
        return
    op.create_table(
        MIGRATION_STATE_TABLE,
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("key", name=f"pk_{MIGRATION_STATE_TABLE}"),
    )
    op.execute(sa.text(f"INSERT INTO {MIGRATION_STATE_TABLE} (key) VALUES ('daily_units_scaled')"))


def _rename_relation_tables() -> None:
    if _has_table(OLD_RELATION_V2_TABLE):
        _drop_table_if_exists(OLD_RELATION_TABLE)
        op.rename_table(OLD_RELATION_V2_TABLE, NEW_RELATION_TABLE)
        return

    _drop_table_if_exists(OLD_RELATION_TABLE)


def upgrade(name: str = "") -> None:
    if name:
        return

    for suffix in DIRECT_TABLE_SUFFIXES:
        _rename_table(f"{OLD_PREFIX}_{suffix}", f"{NEW_PREFIX}_{suffix}")
    _rename_relation_tables()

    for old_constraint_name, new_constraint_name, table_name in POSTGRES_CONSTRAINT_RENAMES:
        _rename_postgres_constraint(old_constraint_name, new_constraint_name, table_name)
    for old_index_name, new_index_name, table_name, columns, unique in INDEX_RENAMES:
        _rename_or_recreate_index(old_index_name, new_index_name, table_name, columns, unique)
    for old_sequence_name, new_sequence_name in POSTGRES_SEQUENCE_RENAMES:
        _rename_postgres_sequence(old_sequence_name, new_sequence_name)

    _create_core_tables_if_missing()

    if _has_table(NEW_RELATION_TABLE) and "daily_loss_used" in _columns(NEW_RELATION_TABLE):
        _mark_daily_units_scaled()

    if _has_table(f"{NEW_PREFIX}_chathistory"):
        _drop_index_if_exists(f"{NEW_PREFIX}_chathistory", "ix_chat_session_time")
        _create_index_if_missing(
            f"{NEW_PREFIX}_chathistory",
            f"ix_{NEW_PREFIX}_chathistory_session_time",
            ["session_id", "created_at"],
        )

    if _has_table(NEW_RELATION_TABLE):
        columns = _columns(NEW_RELATION_TABLE)
        if "favorability_raw" in columns:
            _create_index_if_missing(NEW_RELATION_TABLE, f"ix_{NEW_PREFIX}_userrelation_cap_reset_at", ["cap_reset_at"])
            _create_index_if_missing(NEW_RELATION_TABLE, f"ix_{NEW_PREFIX}_userrelation_favorability", ["favorability"])
            _create_index_if_missing(NEW_RELATION_TABLE, f"ix_{NEW_PREFIX}_userrelation_favorability_raw", ["favorability_raw"])
            _create_index_if_missing(NEW_RELATION_TABLE, f"ix_{NEW_PREFIX}_userrelation_last_interact_at", ["last_interact_at"])
            _create_index_if_missing(NEW_RELATION_TABLE, f"ix_{NEW_PREFIX}_userrelation_state", ["state"])
            _create_index_if_missing(NEW_RELATION_TABLE, f"ix_{NEW_PREFIX}_userrelation_user_id", ["user_id"])


def downgrade(name: str = "") -> None:
    if name:
        return

    if _has_table(NEW_RELATION_TABLE):
        op.rename_table(NEW_RELATION_TABLE, OLD_RELATION_V2_TABLE)
    for suffix in reversed(DIRECT_TABLE_SUFFIXES):
        _rename_table(f"{NEW_PREFIX}_{suffix}", f"{OLD_PREFIX}_{suffix}")
