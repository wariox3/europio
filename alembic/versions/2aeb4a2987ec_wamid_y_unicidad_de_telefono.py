"""wamid y unicidad de telefono

Revision ID: 2aeb4a2987ec
Revises: 0a45f052a27a
Create Date: 2026-06-18 07:37:53.766747

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2aeb4a2987ec'
down_revision: Union[str, None] = '0a45f052a27a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # mensajes.wamid (id de WhatsApp) + índice único para deduplicar reintentos
    op.add_column("mensajes", sa.Column("wamid", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_mensajes_wamid"), "mensajes", ["wamid"], unique=True)

    # conversaciones.telefono pasa a ser único (una conversación por número)
    op.drop_index(op.f("ix_conversaciones_telefono"), table_name="conversaciones")
    op.create_index(op.f("ix_conversaciones_telefono"), "conversaciones", ["telefono"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_conversaciones_telefono"), table_name="conversaciones")
    op.create_index(op.f("ix_conversaciones_telefono"), "conversaciones", ["telefono"], unique=False)

    op.drop_index(op.f("ix_mensajes_wamid"), table_name="mensajes")
    op.drop_column("mensajes", "wamid")
