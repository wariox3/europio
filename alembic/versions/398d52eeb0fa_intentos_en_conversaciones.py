"""intentos en conversaciones

Revision ID: 398d52eeb0fa
Revises: 2aeb4a2987ec
Create Date: 2026-06-18 09:08:51.090660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '398d52eeb0fa'
down_revision: Union[str, None] = '2aeb4a2987ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversaciones",
        sa.Column("intentos", sa.Integer(), nullable=True, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("conversaciones", "intentos")
