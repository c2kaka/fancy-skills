#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

apply="false"
repo_arg=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] || die "missing_value=--repo"
      repo_arg="$2"
      shift 2
      ;;
    --apply)
      apply="true"
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
env_file="${repo}/.env"
[ -f "${env_file}" ] || die "env_file=missing path=${env_file}"

needs_change="false"
[ "$(env_value "${env_file}" CONSOLE_DEV_OIDC_ENABLED)" = "true" ] || needs_change="true"
[ "$(env_value "${env_file}" CONSOLE_DEV_OIDC_ALLOW_INSECURE_REQUESTS)" = "true" ] \
  || needs_change="true"
[ "$(env_value "${env_file}" CONSOLE_DEV_OIDC_ISSUER)" = "${EXPECTED_OIDC_ISSUER}" ] \
  || needs_change="true"
[ "$(env_value "${env_file}" CONSOLE_DEV_OIDC_REDIRECT_URI)" = "${EXPECTED_OIDC_REDIRECT}" ] \
  || needs_change="true"

if [ "${needs_change}" = "false" ]; then
  printf 'result=no_change\n'
  exit 0
fi

printf 'change=CONSOLE_DEV_OIDC_ENABLED:true\n'
printf 'change=CONSOLE_DEV_OIDC_ALLOW_INSECURE_REQUESTS:true\n'
printf 'change=CONSOLE_DEV_OIDC_ISSUER:%s\n' "${EXPECTED_OIDC_ISSUER}"
printf 'change=CONSOLE_DEV_OIDC_REDIRECT_URI:%s\n' "${EXPECTED_OIDC_REDIRECT}"

if [ "${apply}" != "true" ]; then
  printf 'result=preview_only run_with=--apply\n'
  exit 0
fi

tmp_file="$(mktemp "${env_file}.codex-local-saas.XXXXXX")"
trap 'rm -f "${tmp_file}"' EXIT
awk '
  !/^CONSOLE_DEV_OIDC_ENABLED=/ &&
  !/^CONSOLE_DEV_OIDC_ALLOW_INSECURE_REQUESTS=/ &&
  !/^CONSOLE_DEV_OIDC_ISSUER=/ &&
  !/^CONSOLE_DEV_OIDC_REDIRECT_URI=/ { print }
' "${env_file}" >"${tmp_file}"
printf '\n# Codex local SaaS browser OIDC invariants\n' >>"${tmp_file}"
printf 'CONSOLE_DEV_OIDC_ENABLED=true\n' >>"${tmp_file}"
printf 'CONSOLE_DEV_OIDC_ALLOW_INSECURE_REQUESTS=true\n' >>"${tmp_file}"
printf 'CONSOLE_DEV_OIDC_ISSUER=%s\n' "${EXPECTED_OIDC_ISSUER}" >>"${tmp_file}"
printf 'CONSOLE_DEV_OIDC_REDIRECT_URI=%s\n' "${EXPECTED_OIDC_REDIRECT}" >>"${tmp_file}"
chmod "$(stat -f '%Lp' "${env_file}")" "${tmp_file}"
mv "${tmp_file}" "${env_file}"
trap - EXIT
printf 'result=applied file=%s\n' "${env_file}"
