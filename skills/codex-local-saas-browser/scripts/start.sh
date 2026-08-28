#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

agentation="false"
repo_arg=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] || die "missing_value=--repo"
      repo_arg="$2"
      shift 2
      ;;
    --agentation)
      agentation="true"
      shift
      ;;
    *)
      die "unknown_argument=$1"
      ;;
  esac
done

[ -n "${repo_arg}" ] || die "required_argument=--repo"
repo="$(resolve_repo "${repo_arg}")"
validate_repo "${repo}"
"${SCRIPT_DIR}/check.sh" --repo "${repo}" --allow-stopped

pids="$(port_pids)"
if [ -n "${pids}" ]; then
  all_intended="true"
  for pid in ${pids}; do
    cwd="$(pid_cwd "${pid}")"
    [ "${cwd}" = "${repo}" ] || all_intended="false"
  done
  if [ "${all_intended}" = "true" ]; then
    printf 'result=already_running pids=%s\n' "$(printf '%s' "${pids}" | tr '\n' ',')"
    exit 0
  fi
  die "port_owner=other_worktree pids=$(printf '%s' "${pids}" | tr '\n' ',')"
fi

cd "${repo}"
printf 'INFO|starting=https://localhost:3000 agentation=%s repo=%s\n' "${agentation}" "${repo}"
if [ "${agentation}" = "true" ]; then
  exec env VITE_AGENTATION_DEVTOOLS=true pnpm dev
else
  exec env VITE_AGENTATION_DEVTOOLS=false pnpm dev
fi
