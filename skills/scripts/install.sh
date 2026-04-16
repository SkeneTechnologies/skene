#!/usr/bin/env bash
set -euo pipefail

# install.sh -- Install Skene Skills by running migration.sql files in dependency order.
# Usage:
#   ./scripts/install.sh <skill>       Install a single skill (resolves dependencies)
#   ./scripts/install.sh all           Install all skills
#   ./scripts/install.sh --seed <skill> Install and seed a skill
#   ./scripts/install.sh --seed all     Install and seed everything

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/.."

# Dependency order (topologically sorted)
ALL_SKILLS=(identity crm pipeline tasks support comms content billing calendar automations analytics forms notifications campaigns commerce knowledge approvals integrations compliance)

SEED=false
TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seed) SEED=true; shift ;;
    *) TARGET="$1"; shift ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "Usage: $0 [--seed] <skill|all>"
  echo ""
  echo "Available skills: ${ALL_SKILLS[*]}"
  exit 1
fi

# Check for DATABASE_URL or SUPABASE_DB_URL
DB_URL="${DATABASE_URL:-${SUPABASE_DB_URL:-}}"
if [[ -z "$DB_URL" ]]; then
  echo "Error: Set DATABASE_URL or SUPABASE_DB_URL environment variable."
  exit 1
fi

resolve_deps() {
  local skill="$1"
  local manifest="$SKILLS_DIR/$skill/manifest.json"

  if [[ ! -f "$manifest" ]]; then
    echo "Error: Skill '$skill' not found at $SKILLS_DIR/$skill" >&2
    exit 1
  fi

  # Parse depends_on from manifest.json
  local deps
  deps=$(python3 -c "
import json, sys
m = json.load(open(sys.argv[1]))
for d in m.get('depends_on', []):
    print(d)
" "$manifest")

  for dep in $deps; do
    resolve_deps "$dep"
  done
  echo "$skill"
}

get_install_order() {
  if [[ "$TARGET" == "all" ]]; then
    printf '%s\n' "${ALL_SKILLS[@]}"
  else
    resolve_deps "$TARGET" | awk '!seen[$0]++'
  fi
}

INSTALL_ORDER=$(get_install_order)

echo "Install order:"
echo "$INSTALL_ORDER" | sed 's/^/  /'
echo ""

if [[ "$SEED" != true ]]; then
  for skill in $INSTALL_ORDER; do
    migration="$SKILLS_DIR/$skill/migration.sql"
    if [[ ! -f "$migration" ]]; then
      echo "Warning: $migration not found, skipping."
      continue
    fi
    echo "Running $skill/migration.sql ..."
    psql "$DB_URL" -f "$migration" --set ON_ERROR_STOP=1
  done
fi

if [[ "$SEED" == true ]]; then
  echo ""
  echo "Seeding..."
  for skill in $INSTALL_ORDER; do
    seed="$SKILLS_DIR/$skill/seed.sql"
    if [[ ! -f "$seed" ]]; then
      continue
    fi
    echo "Running $skill/seed.sql ..."
    psql "$DB_URL" -f "$seed" --set ON_ERROR_STOP=1
  done
fi

echo ""
echo "Done."
