"""ai-groupmate daily unit scale placeholder

迁移 ID: e1a6f4d3c2b8
父迁移: d2a4f3bc1b9e

This placeholder keeps the old Alembic revision chain resolvable after the
plugin was renamed. The actual schema creation/rename happens in
9f2a8c1d4b6e_first_revision.py.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = 'e1a6f4d3c2b8'
down_revision: str | Sequence[str] | None = 'd2a4f3bc1b9e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    return


def downgrade(name: str = "") -> None:
    return
