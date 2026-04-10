#!/usr/bin/env bash
set -euo pipefail

# reset.sh -- Drop all skill tables and re-run install.
# Usage:
#   ./scripts/reset.sh           Reset all skills
#   ./scripts/reset.sh --seed    Reset and re-seed all skills

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/../skills"

SEED=false
[[ "${1:-}" == "--seed" ]] && SEED=true

DB_URL="${DATABASE_URL:-${SUPABASE_DB_URL:-}}"
if [[ -z "$DB_URL" ]]; then
  echo "Error: Set DATABASE_URL or SUPABASE_DB_URL environment variable."
  exit 1
fi

# Reverse dependency order for safe dropping
REVERSE_SKILLS=(analytics automations calendar billing content comms support tasks pipeline crm identity)

echo "Dropping all skill tables in reverse dependency order..."

for skill in "${REVERSE_SKILLS[@]}"; do
  manifest="$SKILLS_DIR/$skill/manifest.json"
  if [[ ! -f "$manifest" ]]; then
    continue
  fi

  tables=$(python3 -c "
import json
m = json.load(open('$manifest'))
for t in reversed(m.get('tables', [])):
    print(t)
" 2>/dev/null || true)

  for table in $tables; do
    echo "  DROP TABLE IF EXISTS $table"
    psql "$DB_URL" -c "DROP TABLE IF EXISTS public.$table CASCADE;" --set ON_ERROR_STOP=1 2>/dev/null || true
  done
done

# Drop enums
echo "Dropping enums..."
psql "$DB_URL" --set ON_ERROR_STOP=1 -c "
DO \$\$ DECLARE
  r RECORD;
BEGIN
  FOR r IN SELECT typname FROM pg_type WHERE typnamespace = 'public'::regnamespace AND typtype = 'e' LOOP
    EXECUTE 'DROP TYPE IF EXISTS public.' || r.typname || ' CASCADE';
  END LOOP;
END \$\$;
" 2>/dev/null || true

# Drop helper functions
echo "Dropping functions..."
psql "$DB_URL" --set ON_ERROR_STOP=1 -c "
DROP FUNCTION IF EXISTS public.set_updated_at() CASCADE;
DROP FUNCTION IF EXISTS public.get_user_org_id() CASCADE;
DROP FUNCTION IF EXISTS public.get_user_role() CASCADE;
DROP FUNCTION IF EXISTS public.is_admin() CASCADE;
" 2>/dev/null || true

echo ""
echo "Re-installing..."

INSTALL_ARGS="all"
[[ "$SEED" == true ]] && INSTALL_ARGS="--seed all"

"$SCRIPT_DIR/install.sh" $INSTALL_ARGS
