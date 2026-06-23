"""eliminar celular de empresas

Revision ID: e6b9c4d71f58
Revises: d5a8b3c62e47
Create Date: 2026-06-23 09:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6b9c4d71f58'
down_revision: Union[str, None] = 'd5a8b3c62e47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('empresas', 'celular')


def downgrade() -> None:
    op.add_column('empresas', sa.Column('celular', sa.String(length=30), nullable=True))
