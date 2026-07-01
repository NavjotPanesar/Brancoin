"""empty message

Revision ID: b725cef0d49d
Revises: 05aac18d388b
Create Date: 2024-05-18 06:05:43.758715

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b725cef0d49d'
down_revision: Union[str, None] = '05aac18d388b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both 'shoppable' (e1e419059f3f) and 'featured' (187d59df5391) already exist.
    # Autogenerate wrongly emitted add_column; the real intent was to reconcile
    # cards.shoppable's default with the model (False -> True). featured stays False.
    op.alter_column('cards', 'shoppable', server_default=sa.text('true'))


def downgrade() -> None:
    op.alter_column('cards', 'shoppable', server_default=sa.text('false'))
