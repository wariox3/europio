"""no_leidos en conversaciones

Revision ID: fca65680f3b4
Revises: dd8d37b6ddf4
Create Date: 2026-06-18 20:39:21.982224

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fca65680f3b4'
down_revision: Union[str, None] = 'dd8d37b6ddf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversaciones",
        sa.Column("no_leidos", sa.Integer(), nullable=True, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("conversaciones", "no_leidos")
