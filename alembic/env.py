from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base
import importlib
import pkgutil
import app.models as models_pkg

# Import every module in app.models so Base.metadata is complete for autogenerate.
for _, module_name, _ in pkgutil.iter_modules(models_pkg.__path__, models_pkg.__name__ + "."):
    importlib.import_module(module_name)
from app.config import settings

config = context.config

# Prefer an explicit Alembic-configured URL when provided (e.g., tests),
# otherwise fall back to settings.database_url.
configured_url = config.get_main_option("sqlalchemy.url")
if not configured_url or "${" in configured_url:
    config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_include_tables() -> set[str] | None:
    x_args = context.get_x_argument(as_dictionary=True)
    tables_arg = x_args.get("tables")
    if not tables_arg:
        return None
    return {t.strip() for t in tables_arg.split(",") if t.strip()}


def _include_object(include_tables: set[str] | None):
    def include_object(obj, name, type_, reflected, compare_to):
        if include_tables is None:
            return True
        if type_ == "table":
            return name in include_tables
        table = getattr(obj, "table", None) or getattr(obj, "parent", None)
        if table is None and compare_to is not None:
            table = getattr(compare_to, "table", None)
        if table is not None:
            return table.name in include_tables
        return True

    return include_object


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    include_tables = _get_include_tables()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=_include_object(include_tables),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        include_tables = _get_include_tables()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=_include_object(include_tables),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
