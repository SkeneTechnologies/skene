"""Parse a directory of Supabase "Copy as SQL" exports into a SchemaIndex.

Each ``.sql`` file in the directory is treated as one Postgres schema
(``public.sql`` → schema ``public``). The filename is the schema name.

We extract only what's useful for journey inference:
- ``CREATE TABLE`` → columns, inline PRIMARY KEY, NOT NULL, DEFAULT
- ``ALTER TABLE ... ADD CONSTRAINT ... PRIMARY KEY (...)``
- ``ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY (...) REFERENCES ...``
- ``CREATE INDEX`` / ``CREATE UNIQUE INDEX``

Everything else (RLS policies, triggers, functions, grants, comments,
extensions) is skipped. Unknown statements are logged and ignored — the
parser must never raise.
"""

from __future__ import annotations

from pathlib import Path

import sqlglot
from sqlglot import expressions as exp

from skene.analyzers.schema_parsers.models import (
    ColumnInfo,
    ForeignKey,
    IndexInfo,
    SchemaIndex,
    TableInfo,
)
from skene.output import debug, warning

# Filenames Supabase uses for system schemas. Parsed (so cross-schema FKs
# resolve) but hidden from the agent's default view.
_INTERNAL_PREFIXES = (
    "auth",
    "storage",
    "realtime",
    "supabase_",
    "pgsodium",
    "vault",
    "graphql",
    "extensions",
    "net",
    "pgbouncer",
    "cron",
)


def is_supabase_internal(filename: str) -> bool:
    stem = Path(filename).stem.lower()
    return any(stem == p or stem.startswith(p) for p in _INTERNAL_PREFIXES)


def parse_schema_dir(schema_dir: Path) -> SchemaIndex:
    """Walk ``schema_dir``, parse every ``*.sql``, return a SchemaIndex.

    Filenames become schema-file keys verbatim (e.g. ``public.sql``). Tables
    within a file inherit that file as their ``schema_file``.
    """
    index = SchemaIndex()
    if not schema_dir.exists():
        raise FileNotFoundError(f"schema directory not found: {schema_dir}")
    for sql_path in sorted(schema_dir.glob("*.sql")):
        tables = _parse_file(sql_path)
        index.files[sql_path.name] = tables
    return index


def _parse_file(path: Path) -> list[TableInfo]:
    text = path.read_text(encoding="utf-8")
    try:
        statements = sqlglot.parse(text, read="postgres")
    except Exception as e:  # noqa: BLE001 — sqlglot raises a wide range
        warning(f"sqlglot failed on {path}, falling back to per-statement parse: {e}")
        statements = _parse_loose(text)

    tables: dict[str, TableInfo] = {}
    for stmt in statements:
        if stmt is None:
            continue
        try:
            _apply_statement(stmt, tables, schema_file=path.name)
        except Exception as e:  # noqa: BLE001
            debug(f"skipping unparseable statement in {path}: {e}")
    return list(tables.values())


def _parse_loose(text: str) -> list[exp.Expression | None]:
    """Fallback when sqlglot chokes on the file: split on ';' and try each."""
    out: list[exp.Expression | None] = []
    for raw in text.split(";"):
        chunk = raw.strip()
        if not chunk:
            continue
        try:
            out.append(sqlglot.parse_one(chunk, read="postgres"))
        except Exception:  # noqa: BLE001
            out.append(None)
    return out


def _apply_statement(stmt: exp.Expression, tables: dict[str, TableInfo], schema_file: str) -> None:
    if isinstance(stmt, exp.Create):
        kind = (stmt.args.get("kind") or "").upper()
        if kind == "TABLE":
            _handle_create_table(stmt, tables, schema_file)
        elif kind == "INDEX":
            _handle_create_index(stmt, tables)
        return

    alter_cls = getattr(exp, "Alter", None) or getattr(exp, "AlterTable", None)
    if alter_cls is not None and isinstance(stmt, alter_cls):
        _handle_alter_table(stmt, tables)
        return


def _handle_create_table(stmt: exp.Create, tables: dict[str, TableInfo], schema_file: str) -> None:
    table_expr = stmt.this
    table_name = _table_name(table_expr)
    if not table_name:
        return

    columns: list[ColumnInfo] = []
    primary_key: list[str] = []
    foreign_keys: list[ForeignKey] = []

    expressions = []
    if isinstance(table_expr, exp.Schema):
        expressions = table_expr.expressions or []

    for item in expressions:
        if isinstance(item, exp.ColumnDef):
            col = _column_def_to_info(item)
            columns.append(col)
            if any(item.find_all(exp.PrimaryKeyColumnConstraint)) and col.name not in primary_key:
                primary_key.append(col.name)
            continue

        for inner in _unwrap_constraint(item):
            if isinstance(inner, exp.PrimaryKey):
                for e in inner.expressions or []:
                    name = _ident_name(e)
                    if name and name not in primary_key:
                        primary_key.append(name)
            elif isinstance(inner, exp.ForeignKey):
                fk = _foreign_key_from_expr(inner)
                if fk is not None:
                    foreign_keys.append(fk)

    info = TableInfo(
        name=table_name,
        schema_file=schema_file,
        columns=columns,
        primary_key=primary_key,
        foreign_keys=foreign_keys,
    )
    tables[table_name] = info


def _unwrap_constraint(node: exp.Expression) -> list[exp.Expression]:
    if isinstance(node, (exp.PrimaryKey, exp.ForeignKey)):
        return [node]
    out: list[exp.Expression] = []
    for inner in getattr(node, "expressions", None) or []:
        if isinstance(inner, (exp.PrimaryKey, exp.ForeignKey)):
            out.append(inner)
    if out:
        return out
    return [
        *node.find_all(exp.PrimaryKey),
        *node.find_all(exp.ForeignKey),
    ]


def _column_def_to_info(col: exp.ColumnDef) -> ColumnInfo:
    name = _ident_name(col.this) or ""
    type_expr = col.args.get("kind")
    type_sql = type_expr.sql(dialect="postgres") if type_expr is not None else ""

    nullable = True
    default: str | None = None
    for c in col.find_all(exp.ColumnConstraint):
        kind = c.args.get("kind")
        if isinstance(kind, exp.NotNullColumnConstraint):
            nullable = False
        elif isinstance(kind, exp.DefaultColumnConstraint):
            inner = kind.this
            default = inner.sql(dialect="postgres") if inner is not None else None
    return ColumnInfo(name=name, type=type_sql, nullable=nullable, default=default)


def _handle_alter_table(stmt: exp.Expression, tables: dict[str, TableInfo]) -> None:
    target = stmt.this
    table_name = _table_name(target)
    if not table_name or table_name not in tables:
        return
    info = tables[table_name]

    actions = stmt.args.get("actions") or []
    for action in actions:
        inner_list = _action_constraints(action)
        for inner in inner_list:
            if isinstance(inner, exp.PrimaryKey):
                for e in inner.expressions or []:
                    name = _ident_name(e)
                    if name and name not in info.primary_key:
                        info.primary_key.append(name)
            elif isinstance(inner, exp.ForeignKey):
                fk = _foreign_key_from_expr(inner)
                if fk is not None:
                    info.foreign_keys.append(fk)


def _action_constraints(action: exp.Expression) -> list[exp.Expression]:
    out: list[exp.Expression] = []
    if action is None:
        return out
    candidates: list[exp.Expression] = []
    if hasattr(action, "expressions") and action.expressions:
        candidates.extend(action.expressions)
    if hasattr(action, "this") and action.this is not None:
        candidates.append(action.this)
    candidates.append(action)

    for c in candidates:
        if isinstance(c, (exp.PrimaryKey, exp.ForeignKey)):
            out.append(c)
        else:
            for nested in c.find_all(exp.PrimaryKey):
                out.append(nested)
            for nested in c.find_all(exp.ForeignKey):
                out.append(nested)
    seen: set[int] = set()
    uniq: list[exp.Expression] = []
    for x in out:
        if id(x) not in seen:
            seen.add(id(x))
            uniq.append(x)
    return uniq


def _foreign_key_from_expr(fk: exp.ForeignKey) -> ForeignKey | None:
    cols = [_ident_name(e) for e in (fk.expressions or [])]
    cols = [c for c in cols if c]

    ref = fk.args.get("reference")
    if ref is None:
        return None
    ref_target = ref.this
    ref_table = _table_name(ref_target)
    ref_cols: list[str] = []
    if isinstance(ref_target, exp.Schema):
        ref_cols = [_ident_name(e) for e in (ref_target.expressions or []) if _ident_name(e)]
    if not ref_table:
        return None
    return ForeignKey(
        columns=cols,
        references_table=ref_table,
        references_columns=ref_cols,
    )


def _handle_create_index(stmt: exp.Create, tables: dict[str, TableInfo]) -> None:
    index_expr = stmt.this
    if index_expr is None:
        return

    table_node = None
    if hasattr(index_expr, "args"):
        table_node = index_expr.args.get("table") or index_expr.args.get("this")
    table_name = _table_name(table_node) if table_node is not None else None
    if not table_name or table_name not in tables:
        return
    info = tables[table_name]

    name = ""
    if hasattr(index_expr, "this") and index_expr.this is not None:
        name = _ident_name(index_expr.this) or ""

    params = index_expr.args.get("params") if hasattr(index_expr, "args") else None
    cols: list[str] = []
    if params is not None and hasattr(params, "args"):
        for c in params.args.get("columns") or []:
            n = _ident_name(c.this if hasattr(c, "this") else c)
            if n:
                cols.append(n)
    if not cols:
        for c in getattr(index_expr, "expressions", None) or []:
            n = _ident_name(c.this if hasattr(c, "this") else c)
            if n:
                cols.append(n)

    unique = bool(stmt.args.get("unique"))
    info.indexes.append(IndexInfo(name=name, columns=cols, unique=unique))


def _ident_name(node: exp.Expression | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, exp.Identifier):
        return node.this
    if isinstance(node, exp.Column):
        return _ident_name(node.this)
    if isinstance(node, exp.Ordered):
        return _ident_name(node.this)
    if hasattr(node, "name") and node.name:
        return node.name
    if hasattr(node, "this"):
        return _ident_name(node.this)
    return None


def _table_name(node: exp.Expression | None) -> str | None:
    """Return a bare table name (no schema qualifier) or qualified ``schema.table``."""
    if node is None:
        return None
    if isinstance(node, exp.Schema):
        return _table_name(node.this)
    if isinstance(node, exp.Table):
        name = node.name
        schema = node.args.get("db")
        schema_name = _ident_name(schema) if schema is not None else None
        if schema_name:
            return f"{schema_name}.{name}"
        return name
    return _ident_name(node)
