"""soporte y gestion humana en empresas

Revision ID: d5a8b3c62e47
Revises: c4f7a2b91d36
Create Date: 2026-06-23 08:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5a8b3c62e47'
down_revision: Union[str, None] = 'c4f7a2b91d36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'empresas',
        sa.Column('soporte', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )
    op.add_column('empresas', sa.Column('gestion_humana_nombre', sa.String(length=150), nullable=True))
    op.add_column('empresas', sa.Column('gestion_humana_celular', sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column('empresas', 'gestion_humana_celular')
    op.drop_column('empresas', 'gestion_humana_nombre')
    op.drop_column('empresas', 'soporte')
