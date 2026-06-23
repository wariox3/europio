"""imagen_url en faqs

Revision ID: c4f7a2b91d36
Revises: b7e1c4a90f22
Create Date: 2026-06-23 08:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f7a2b91d36'
down_revision: Union[str, None] = 'b7e1c4a90f22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('faqs', sa.Column('imagen_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('faqs', 'imagen_url')
