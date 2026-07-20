"""Introspect a live PostgreSQL database and return a SchemaIndex.

Uses psycopg3 (sync API) to query the PostgreSQL catalog in a small number
of set-returning queries, then assembles the results into the same
:class:`SchemaIndex` that the SQL-file parser produces.

Never raises the raw connection string or password in an exception message
or log line.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from skene.analyzers.schema_parsers.models import (
    ColumnInfo,
    ForeignKey,
    IndexInfo,
    SchemaIndex,
    TableInfo,
)
from skene.output import debug


def _pg_array_to_list(val: Any) -> list[str]:
    """Convert a PostgreSQL array string like '{a,b,c}' to ['a','b','c']."""
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        return [str(v) for v in val]
    # Strip outer braces
    inner = str(val).strip("{}")
    if not inner:
        return []
    # Split on commas, strip quotes and whitespace
    return [item.strip().strip("'") for item in inner.split(",") if item.strip()]


# relkind filter: ordinary tables, partitioned tables, views, materialized views.
# Injected directly into SQL (static string, never user input).
_RELKIND_FILTER = "('r', 'p', 'v', 'm')"


def _discover_user_schemas(cur: Any) -> list[str]:
    """Return user-defined schema names, excluding system and extension schemas."""
    cur.execute("""\
        SELECT nspname
        FROM pg_namespace
        WHERE nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND nspname NOT LIKE 'pg_%%'
        ORDER BY nspname
    """)
    return [row["nspname"] for row in cur.fetchall()]


def introspect_db(db_url: str, *, connect_timeout: int = 10) -> SchemaIndex:
    """Connect to *db_url*, introspect the schema, return a :class:`SchemaIndex`.

    Parameters
    ----------
    db_url:
        A complete PostgreSQL connection string (libpq URL or keyword DSN).
    connect_timeout:
        Seconds to wait for the TCP connection to be established.

    Raises
    ------
    psycopg.Error
        Connection or query errors are re-raised with the connection string
        redacted.  The password never appears in the exception message.
    """
    index = SchemaIndex()

    try:
        conn = psycopg.connect(db_url, connect_timeout=connect_timeout, row_factory=dict_row)
    except psycopg.Error as e:
        raise psycopg.Error("Database connection failed") from e

    with conn:
        tables_by_file: dict[str, dict[str, TableInfo]] = {}

        # --- 0. Discover user schemas (exclude pg_*, information_schema) ---
        with conn.cursor() as cur:
            user_schemas = _discover_user_schemas(cur)

        if not user_schemas:
            return index

        # --- 1. Collect tables (schema-qualified names) ---
        tables_query = f"""\
            SELECT n.nspname AS schema_name,
                   c.relname AS table_name
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_inherits i ON i.inhrelid = c.oid
            WHERE c.relkind IN {_RELKIND_FILTER}
              AND i.inhrelid IS NULL
              AND n.nspname = ANY(%s)
            ORDER BY n.nspname, c.relname
        """
        with conn.cursor() as cur:
            cur.execute(tables_query, (user_schemas,))
            table_ids: list[tuple[str, str]] = [(row["schema_name"], row["table_name"]) for row in cur.fetchall()]

        if not table_ids:
            return index

        # Extract flat lists for legacy ANY() filters
        table_names: list[str] = [t for _, t in table_ids]

        # --- 2. Collect all data in parallel-ish queries (single connection, sequential) ---

        # 2a. Primary keys per table
        pk_query = """\
            SELECT n.nspname AS schema_name,
                   c.relname AS table_name,
                   array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS pk_columns
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_index ix ON ix.indrelid = c.oid AND ix.indisprimary
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(ix.indkey)
            WHERE c.relname = ANY(%s)
              AND n.nspname = ANY(%s)
            GROUP BY n.nspname, c.relname
        """
        with conn.cursor() as cur:
            cur.execute(pk_query, (table_names, user_schemas))
            pk_map: dict[tuple[str, str], list[str]] = {
                (row["schema_name"], row["table_name"]): _pg_array_to_list(row["pk_columns"]) for row in cur.fetchall()
            }

        # 2b. Columns per table
        col_query = """\
            SELECT table_schema AS schema_name,
                   table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = ANY(%s)
              AND table_schema = ANY(%s)
            ORDER BY table_schema, table_name, ordinal_position
        """
        with conn.cursor() as cur:
            cur.execute(col_query, (table_names, user_schemas))
            # Group by (schema, table)
            cols_by_table: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for row in cur.fetchall():
                cols_by_table.setdefault((row["schema_name"], row["table_name"]), []).append(row)

        # 2c. Foreign keys — use pg_constraint directly so we can pair
        # referencing columns (conkey) with referenced columns (confkey)
        # by their position in the array.
        fk_query = """\
            SELECT nsp.nspname AS schema_name,
                   cl.relname AS table_name,
                   array_agg(att.attname ORDER BY sub) AS columns,
                   ref_nsp.nspname AS references_schema,
                   ref_cl.relname AS references_table,
                   array_agg(ref_att.attname ORDER BY sub) AS references_columns
            FROM pg_constraint fk
            JOIN pg_class cl ON cl.oid = fk.conrelid
            JOIN pg_namespace nsp ON nsp.oid = cl.relnamespace
            JOIN LATERAL generate_subscripts(fk.conkey, 1) AS sub ON true
            JOIN pg_attribute att ON att.attrelid = cl.oid
                                 AND att.attnum = fk.conkey[sub]
            JOIN pg_class ref_cl ON ref_cl.oid = fk.confrelid
            JOIN pg_namespace ref_nsp ON ref_nsp.oid = ref_cl.relnamespace
            JOIN pg_attribute ref_att ON ref_att.attrelid = ref_cl.oid
                                    AND ref_att.attnum = fk.confkey[sub]
            WHERE fk.contype = 'f'
              AND cl.relname = ANY(%s)
              AND nsp.nspname = ANY(%s)
            GROUP BY nsp.nspname, cl.relname, ref_nsp.nspname, ref_cl.relname
        """
        with conn.cursor() as cur:
            cur.execute(fk_query, (table_names, user_schemas))
            fk_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for row in cur.fetchall():
                r = dict(row)  # Row → mutable dict
                r["columns"] = _pg_array_to_list(r["columns"])
                r["references_columns"] = _pg_array_to_list(r["references_columns"])
                fk_map.setdefault((r["schema_name"], r["table_name"]), []).append(r)

        # 2d. Indexes
        idx_query = f"""\
            SELECT n.nspname AS schema_name,
                   t.relname AS table_name,
                   i.relname AS index_name,
                   array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS columns,
                   ix.indisunique AS is_unique
            FROM pg_class t
            JOIN pg_index ix ON ix.indrelid = t.oid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            LEFT JOIN pg_inherits pi ON pi.inhrelid = t.oid
            WHERE t.relkind IN {_RELKIND_FILTER}
              AND pi.inhrelid IS NULL
              AND t.relname = ANY(%s)
              AND n.nspname = ANY(%s)
            GROUP BY n.nspname, t.relname, i.relname, ix.indisunique
        """
        with conn.cursor() as cur:
            cur.execute(idx_query, (table_names, user_schemas))
            idx_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for row in cur.fetchall():
                r = dict(row)
                r["columns"] = _pg_array_to_list(r["columns"])
                idx_map.setdefault((r["schema_name"], r["table_name"]), []).append(r)

        # --- 3. Assemble TableInfo objects ---
        for schema_name, tname in table_ids:
            table_id = (schema_name, tname)

            columns = [
                ColumnInfo(
                    name=r["column_name"],
                    type=r["data_type"],
                    nullable=r["is_nullable"] == "YES",
                    default=r["column_default"],
                )
                for r in cols_by_table.get(table_id, [])
            ]

            primary_key = pk_map.get(table_id, [])

            foreign_keys = [
                ForeignKey(
                    columns=r["columns"],
                    references_table=r["references_table"],
                    references_columns=r["references_columns"],
                )
                for r in fk_map.get(table_id, [])
            ]

            indexes = [
                IndexInfo(
                    name=r["index_name"],
                    columns=r["columns"],
                    unique=r["is_unique"],
                )
                for r in idx_map.get(table_id, [])
            ]

            # Schema-qualified file name so tables with the same name in
            # different schemas (e.g. public.users vs. auth.users) don't
            # collide or overwrite each other.
            schema_file = f"{schema_name}.{tname}.sql"
            table_info = TableInfo(
                name=tname,
                schema_file=schema_file,
                columns=columns,
                primary_key=primary_key,
                foreign_keys=foreign_keys,
                indexes=indexes,
            )

            tables_by_file.setdefault(schema_file, {})[tname] = table_info

        # Flatten into SchemaIndex.files dict (key = schema_file)
        for schema_file, tables_dict in tables_by_file.items():
            index.files[schema_file] = sorted(tables_dict.values(), key=lambda t: t.name)

    debug(f"Introspected {len(index.files)} schema files, {sum(len(t) for t in index.files.values())} tables")
    return index
