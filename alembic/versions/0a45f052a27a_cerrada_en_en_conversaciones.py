"""cerrada_en en conversaciones

Revision ID: 0a45f052a27a
Revises: e922c7c5e7ff
Create Date: 2026-06-18 07:21:43.424924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a45f052a27a'
down_revision: Union[str, None] = 'e922c7c5e7ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversaciones",
        sa.Column("cerrada_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversaciones", "cerrada_en")
