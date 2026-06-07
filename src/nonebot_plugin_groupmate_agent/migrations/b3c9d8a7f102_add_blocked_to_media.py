"""ai-groupmate blocked media placeholder

迁移 ID: b3c9d8a7f102
父迁移: 6a6a44d58ced

This placeholder keeps the old Alembic revision chain resolvable after the
plugin was renamed. The actual schema creation/rename happens in
9f2a8c1d4b6e_first_revision.py.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = 'b3c9d8a7f102'
down_revision: str | Sequence[str] | None = '6a6a44d58ced'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    return


def downgrade(name: str = "") -> None:
    return
