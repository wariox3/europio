"""rol en usuarios

Revision ID: f7c1d8e92a63
Revises: e6b9c4d71f58
Create Date: 2026-06-23 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7c1d8e92a63'
down_revision: Union[str, None] = 'e6b9c4d71f58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'usuarios',
        sa.Column('rol', sa.String(length=30), nullable=False, server_default=sa.text("'asesor'")),
    )


def downgrade() -> None:
    op.drop_column('usuarios', 'rol')
