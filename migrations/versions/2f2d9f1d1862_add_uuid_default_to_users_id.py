"""
add uuid default to users id

Revision ID: 2f2d9f1d1862
Revises: 384b8ce70b9d
Create Date: 2026-08-12 10:59:37.173425
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "2f2d9f1d1862"
down_revision: str | Sequence[str] | None = "384b8ce70b9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
