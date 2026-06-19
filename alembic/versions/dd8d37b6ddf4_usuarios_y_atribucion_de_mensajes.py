"""usuarios y atribucion de mensajes

Revision ID: dd8d37b6ddf4
Revises: 398d52eeb0fa
Create Date: 2026-06-18 13:15:34.176676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd8d37b6ddf4'
down_revision: Union[str, None] = '398d52eeb0fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usuarios_email"), "usuarios", ["email"], unique=True)
    op.add_column("mensajes", sa.Column("usuario_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("mensajes", "usuario_id")
    op.drop_index(op.f("ix_usuarios_email"), table_name="usuarios")
    op.drop_table("usuarios")
