#!/usr/bin/env bash
set -euo pipefail
# Never execute against a production server or a network host.
[[ "${G1_DISPOSABLE_DB:-}" == 'yes' ]] || { echo 'G1_DISPOSABLE_DB=yes required' >&2; exit 2; }
[[ "${PGHOST:-}" == '127.0.0.1' ]] || { echo 'only 127.0.0.1 is allowed' >&2; exit 2; }
[[ "${PGDATABASE:-}" == 'forgeworks_g1' ]] || { echo 'only disposable database forgeworks_g1 is allowed' >&2; exit 2; }
command -v psql >/dev/null || { echo 'psql unavailable' >&2; exit 2; }
base="$(cd "$(dirname "$0")/.." && pwd)/docs/verification/sql-candidates"
for f in 00_role_candidate.sql 10_schema_candidate.sql 20_grants_candidate.sql; do
  echo "G1 DDL probe: $f"
  psql -X -v ON_ERROR_STOP=1 -f "$base/$f"
done
psql -X -v ON_ERROR_STOP=1 -c 'SELECT COUNT(*) AS user_tables FROM pg_tables WHERE schemaname = current_schema();'
echo 'NOTE: DDL smoke test only. RLS two-tenant isolation, concurrency, FK candidates and permissions require separate evidence.'
