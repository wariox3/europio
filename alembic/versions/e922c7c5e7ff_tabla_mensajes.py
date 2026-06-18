"""tabla mensajes

Revision ID: e922c7c5e7ff
Revises: 4d3689a85789
Create Date: 2026-06-18 07:15:25.937455

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e922c7c5e7ff'
down_revision: Union[str, None] = '4d3689a85789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mensajes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telefono", sa.String(length=20), nullable=False),
        sa.Column("direccion", sa.String(length=10), nullable=False),
        sa.Column("texto", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mensajes_telefono"), "mensajes", ["telefono"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mensajes_telefono"), table_name="mensajes")
    op.drop_table("mensajes")
