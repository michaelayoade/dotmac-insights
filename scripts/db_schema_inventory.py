"""Dump the current DB schema (tables + columns) to db_schema_inventory.txt."""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text

# Ensure repo root is on sys.path for app imports.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


def main() -> None:
    engine = create_engine(settings.database_url)
    query = text(
        """
        SELECT
            table_schema,
            table_name,
            column_name,
            data_type,
            is_nullable,
            column_default,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name, ordinal_position
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()

    out_lines: list[str] = []
    current_table = None
    for schema, table, column, data_type, is_nullable, default, _ordinal in rows:
        table_id = f"{schema}.{table}"
        if table_id != current_table:
            if current_table is not None:
                out_lines.append("")
            out_lines.append(f"{table_id}:")
            current_table = table_id
        nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
        default_str = "" if default is None else f" DEFAULT {default}"
        out_lines.append(f"  - {column} {data_type} {nullable}{default_str}")

    with open("db_schema_inventory.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))

    print(
        f"Wrote {len(rows)} columns across "
        f"{len(set((r[0], r[1]) for r in rows))} tables."
    )


if __name__ == "__main__":
    main()
