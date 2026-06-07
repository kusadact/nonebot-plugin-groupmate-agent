"""ai-groupmate daily loss placeholder

迁移 ID: d2a4f3bc1b9e
父迁移: c7f99f9f4e21

This placeholder keeps the old Alembic revision chain resolvable after the
plugin was renamed. The actual schema creation/rename happens in
9f2a8c1d4b6e_first_revision.py.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = 'd2a4f3bc1b9e'
down_revision: str | Sequence[str] | None = 'c7f99f9f4e21'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    return


def downgrade(name: str = "") -> None:
    return
