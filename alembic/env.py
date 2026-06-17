from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Configuración del proyecto: URL de BD y metadata de los modelos.
import app.modelos  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.core.config import settings
from app.core.db import Base

# Objeto de configuración de Alembic (lee alembic.ini).
config = context.config

# Logging según alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata objetivo para autogenerate.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Migraciones en modo 'offline' (genera SQL sin conectarse)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migraciones en modo 'online' (con conexión real)."""
    connectable = create_engine(settings.database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
