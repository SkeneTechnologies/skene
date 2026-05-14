"""In-memory representation of a parsed SQL schema.

Built once by the parser, then queried by the schema agent through the
tools defined in :mod:`skene.analyzers.journey.tools.schema_tools`. The
agent never sees raw SQL.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: str | None = None


class ForeignKey(BaseModel):
    columns: list[str]
    references_table: str
    references_columns: list[str]


class IndexInfo(BaseModel):
    name: str
    columns: list[str]
    unique: bool = False


class TableInfo(BaseModel):
    name: str
    schema_file: str
    columns: list[ColumnInfo]
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKey] = Field(default_factory=list)
    indexes: list[IndexInfo] = Field(default_factory=list)


class SchemaFileInfo(BaseModel):
    name: str
    table_count: int
    is_internal: bool


class SchemaIndex(BaseModel):
    files: dict[str, list[TableInfo]] = Field(default_factory=dict)

    def application_files(self) -> list[str]:
        from skene.analyzers.schema_parsers.supabase_sql import is_supabase_internal

        return sorted(f for f in self.files if not is_supabase_internal(f))

    def all_files(self) -> list[str]:
        return sorted(self.files)

    def file_info(self, name: str) -> SchemaFileInfo | None:
        from skene.analyzers.schema_parsers.supabase_sql import is_supabase_internal

        tables = self.files.get(name)
        if tables is None:
            return None
        return SchemaFileInfo(
            name=name,
            table_count=len(tables),
            is_internal=is_supabase_internal(name),
        )

    def get_table(self, schema_file: str, table: str) -> TableInfo | None:
        for t in self.files.get(schema_file, []):
            if t.name == table:
                return t
        return None
