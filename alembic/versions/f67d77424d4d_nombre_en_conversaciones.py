"""nombre en conversaciones

Revision ID: f67d77424d4d
Revises: f7c1d8e92a63
Create Date: 2026-06-24 15:41:27.417512

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f67d77424d4d'
down_revision: Union[str, None] = 'f7c1d8e92a63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversaciones",
        sa.Column("nombre", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversaciones", "nombre")
