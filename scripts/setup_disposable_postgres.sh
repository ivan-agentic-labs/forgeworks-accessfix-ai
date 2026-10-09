#!/usr/bin/env bash
# Fresh GitHub-hosted CI database only; never targets a deployment database.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true ]] || { echo 'Disposable GitHub Actions required' >&2; exit 1; }
case ${1:-} in
  runtime) task_db=forgeworks_runtime; task_password=synthetic-disposable-ci-only ;;
  g2) task_db=forgeworks_g2; task_password=g2_only_disposable_password ;;
  *) echo 'Unsupported fixed CI database profile' >&2; exit 1 ;;
esac
sudo apt-get update -qq
sudo apt-get install -y postgresql-common
if ! apt-cache show postgresql-17 >/dev/null 2>&1; then
  sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
  sudo apt-get update -qq
fi
sudo apt-get install -y postgresql-17 postgresql-client-17
if pg_lsclusters --no-header | awk '$1==17 && $2=="forgeworks_ci" {found=1} END {exit !found}'; then
  echo 'Refusing to reuse an existing CI cluster' >&2; exit 1
fi
sudo pg_createcluster 17 forgeworks_ci --port=5438 --start
sudo -u postgres /usr/lib/postgresql/17/bin/psql -p 5438 -v ON_ERROR_STOP=1 -c "ALTER USER postgres WITH PASSWORD '$task_password'" -c "CREATE DATABASE $task_db"
task_version=$(sudo -u postgres /usr/lib/postgresql/17/bin/psql -p 5438 -Atc 'SHOW server_version_num')
[[ $task_version -ge 170000 && $task_version -lt 180000 ]] || { echo 'PostgreSQL 17 required' >&2; exit 1; }
echo "Disposable PostgreSQL 17 ready on loopback port 5438; server version $task_version"
