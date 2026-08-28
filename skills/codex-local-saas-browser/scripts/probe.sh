#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

repo_arg=""
browser_path="/saas"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] || die "missing_value=--repo"
      repo_arg="$2"
      shift 2
      ;;
    --path)
      [ "$#" -ge 2 ] || die "missing_value=--path"
      browser_path="$2"
      shift 2
      ;;
    *)
      die "unknown_argument=$1"
      ;;
  esac
done

[ -n "${repo_arg}" ] || die "required_argument=--repo"
case "${browser_path}" in
  /saas|/saas/*) ;;
  *) die "path=must_start_with_/saas" ;;
esac

repo="$(resolve_repo "${repo_arg}")"
"${SCRIPT_DIR}/check.sh" --repo "${repo}"
printf 'browser_url=https://localhost:%s%s\n' "${EXPECTED_PORT}" "${browser_path}"
printf 'result=ready\n'
