"""imagen_url en mensajes

Revision ID: b7e1c4a90f22
Revises: fca65680f3b4
Create Date: 2026-06-19 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e1c4a90f22'
down_revision: Union[str, None] = 'fca65680f3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('mensajes', sa.Column('imagen_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('mensajes', 'imagen_url')
