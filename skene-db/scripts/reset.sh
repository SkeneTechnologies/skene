#!/usr/bin/env bash
set -euo pipefail

# Reset the Skene DB schema: drop all tables, re-run migrations, load seed data.
# Requires: supabase CLI linked to a project (local or remote).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Resetting Skene DB..."
echo ""

# Use supabase db reset which drops and re-applies all migrations
echo "==> Running supabase db reset..."
cd "$ROOT_DIR"
supabase db reset

echo ""
echo "==> Loading seed data..."
# Determine the database URL for the local Supabase instance
DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"
psql "$DB_URL" -f "$ROOT_DIR/seed/demo.sql"

echo ""
echo "==> Done. Skene DB reset complete."
