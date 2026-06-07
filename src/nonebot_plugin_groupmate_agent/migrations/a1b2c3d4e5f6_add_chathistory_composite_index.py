"""ai-groupmate chathistory index placeholder

迁移 ID: a1b2c3d4e5f6
父迁移: 811f4ae4bcd1

This placeholder keeps the old Alembic revision chain resolvable after the
plugin was renamed. The actual schema creation/rename happens in
9f2a8c1d4b6e_first_revision.py.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = '811f4ae4bcd1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    return


def downgrade(name: str = "") -> None:
    return
