#!/usr/bin/env bash
# smoke-test.sh -- End-to-end smoke test for Skene Skills against a Supabase DB.
#
# Verifies the full install path AND that multi-tenant RLS actually isolates
# tenants under the real `authenticated` role with auth.uid() resolved from the
# JWT `sub` claim -- i.e. the security-critical behaviour, not just that the SQL
# parses.
#
# Requirements:
#   - A Supabase-style Postgres reachable via $DATABASE_URL (local Supabase /
#     OrbStack works out of the box: it already has the `auth` schema,
#     auth.uid(), and the anon/authenticated/service_role roles).
#   - psql on PATH.
#
# NOTE: this inserts a demo "Beta Inc" tenant to prove isolation. Run it against
# a development / throwaway database, not production. Inserts are idempotent
# (ON CONFLICT DO NOTHING).
#
# Usage:
#   ./skills/scripts/smoke-test.sh
#   DATABASE_URL=postgresql://... ./skills/scripts/smoke-test.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Local Supabase DB (OrbStack). If different, grab it from: supabase status
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"
echo "Target: $DATABASE_URL"

# 1. Apply + seed all skills via the real install path
chmod +x skills/scripts/install.sh
skills/scripts/install.sh --seed all

# 2. Add a second tenant to prove isolation
psql "$DATABASE_URL" -q <<'SQL'
INSERT INTO public.organizations (id,name,slug,domain) VALUES
  ('a0000000-0000-0000-0000-000000000002','Beta Inc','beta','beta.io')
  ON CONFLICT (id) DO NOTHING;
INSERT INTO public.users (id,org_id,auth_id,email,full_name) VALUES
  ('b0000000-0000-0000-0000-000000000099','a0000000-0000-0000-0000-000000000002',
   'c0000000-0000-0000-0000-000000000099','dana@beta.io','Dana Beta')
  ON CONFLICT (id) DO NOTHING;
SQL

# 3. RLS isolation check as the real 'authenticated' role + JWT sub claim
run_as () {
  echo "==== $1 ===="
  psql "$DATABASE_URL" -t <<SQL
BEGIN;
SET LOCAL ROLE authenticated;
$( [ -n "$2" ] && echo "SET LOCAL request.jwt.claim.sub = '$2';" )
SELECT 'my org_id          = '||coalesce(public.get_user_org_id()::text,'NULL');
SELECT 'contacts visible   = '||count(*) FROM contacts;
SELECT 'Acme users visible = '||count(*) FROM users WHERE org_id='a0000000-0000-0000-0000-000000000001';
SELECT 'Beta users visible = '||count(*) FROM users WHERE org_id='a0000000-0000-0000-0000-000000000002';
COMMIT;
SQL
}
run_as "Acme user (Sarah)" "c0000000-0000-0000-0000-000000000001"
run_as "Beta user (Dana)"  "c0000000-0000-0000-0000-000000000099"
