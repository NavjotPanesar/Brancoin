"""add ext fuzzy search

Revision ID: c9a254fa1b7f
Revises: ccff6feeb9b3
Create Date: 2024-05-24 23:55:22.752785

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9a254fa1b7f'
down_revision: Union[str, None] = 'ccff6feeb9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION pg_trgm;")
    pass


def downgrade() -> None:
    op.execute("DROP EXTENSION pg_trgm;")
    pass
