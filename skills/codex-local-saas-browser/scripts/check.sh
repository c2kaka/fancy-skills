#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

allow_stopped="false"
repo_arg=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] || die "missing_value=--repo"
      repo_arg="$2"
      shift 2
      ;;
    --allow-stopped)
      allow_stopped="true"
      shift
      ;;
    *)
      die "unknown_argument=$1"
      ;;
  esac
done

[ -n "${repo_arg}" ] || die "required_argument=--repo"
repo="$(resolve_repo "${repo_arg}")"

[ "$(uname -s)" = "Darwin" ] || die "platform=macos_required"
for command_name in openssl security lsof curl pnpm awk; do
  require_command "${command_name}"
done
validate_repo "${repo}"
validate_bundled_cogdb_cert

errors=0
emit_error() {
  printf 'ERROR|%s\n' "$*"
  errors=$((errors + 1))
}

printf 'OK|repo=%s\n' "${repo}"
printf 'OK|cogdb_cert_fingerprint=%s\n' "${EXPECTED_COGDB_FINGERPRINT}"

if system_trust_contains "${EXPECTED_COGDB_FINGERPRINT}"; then
  printf 'OK|cogdb_trust=installed\n'
else
  emit_error 'cogdb_trust=missing'
fi

env_file="${repo}/.env"
if [ ! -f "${env_file}" ]; then
  emit_error "env_file=missing path=${env_file}"
else
  oidc_enabled="$(env_value "${env_file}" CONSOLE_DEV_OIDC_ENABLED)"
  oidc_insecure="$(env_value "${env_file}" CONSOLE_DEV_OIDC_ALLOW_INSECURE_REQUESTS)"
  oidc_issuer="$(env_value "${env_file}" CONSOLE_DEV_OIDC_ISSUER)"
  oidc_redirect="$(env_value "${env_file}" CONSOLE_DEV_OIDC_REDIRECT_URI)"
  basic_ssl_disabled="$(env_value "${env_file}" VITE_DISABLE_BASIC_SSL)"

  [ "${oidc_enabled}" = "true" ] && printf 'OK|oidc_enabled=true\n' \
    || emit_error 'oidc_enabled=wrong'
  [ "${oidc_insecure}" = "true" ] && printf 'OK|oidc_local_tls_override=true\n' \
    || emit_error 'oidc_local_tls_override=wrong'
  [ "${oidc_issuer}" = "${EXPECTED_OIDC_ISSUER}" ] && printf 'OK|oidc_issuer=exact\n' \
    || emit_error 'oidc_issuer=wrong'
  [ "${oidc_redirect}" = "${EXPECTED_OIDC_REDIRECT}" ] && printf 'OK|oidc_redirect=exact\n' \
    || emit_error 'oidc_redirect=wrong'
  [ "${basic_ssl_disabled}" != "true" ] && printf 'OK|vite_https=enabled\n' \
    || emit_error 'vite_https=disabled'
fi

vite_combined_cert="${repo}/${VITE_CERT_RELATIVE}"
vite_cert_only="$(mktemp -t codex-local-saas-vite-cert.XXXXXX)"
probe_body="$(mktemp -t codex-local-saas-probe.XXXXXX)"
trap 'rm -f "${vite_cert_only}" "${probe_body}"' EXIT

vite_fingerprint=""
if [ ! -f "${vite_combined_cert}" ]; then
  emit_error "vite_cert=missing path=${vite_combined_cert}"
else
  extract_certificate_block "${vite_combined_cert}" "${vite_cert_only}"
  vite_fingerprint="$(cert_fingerprint "${vite_cert_only}")"
  if openssl x509 -in "${vite_cert_only}" -noout -checkend 0 >/dev/null 2>&1; then
    printf 'OK|vite_cert=valid fingerprint=%s\n' "${vite_fingerprint}"
  else
    emit_error 'vite_cert=expired'
  fi
  if openssl x509 -in "${vite_cert_only}" -noout -ext subjectAltName 2>/dev/null \
    | grep -Fq 'DNS:localhost'; then
    printf 'OK|vite_cert_san=localhost\n'
  else
    emit_error 'vite_cert_san=missing_localhost'
  fi
  if system_trust_contains "${vite_fingerprint}"; then
    printf 'OK|vite_trust=installed\n'
  else
    emit_error 'vite_trust=missing'
  fi
fi

pids="$(port_pids)"
if [ -z "${pids}" ]; then
  printf 'INFO|server=stopped port=%s\n' "${EXPECTED_PORT}"
  if [ "${allow_stopped}" != "true" ]; then
    emit_error 'server=not_running'
  fi
else
  owner_error="false"
  for pid in ${pids}; do
    cwd="$(pid_cwd "${pid}")"
    if [ "${cwd}" = "${repo}" ]; then
      printf 'OK|port_owner=intended_worktree pid=%s cwd=%s\n' "${pid}" "${cwd}"
    else
      emit_error "port_owner=other_worktree pid=${pid} cwd=${cwd:-unknown}"
      owner_error="true"
    fi
  done

  if [ "${owner_error}" = "false" ] && [ -n "${vite_fingerprint}" ]; then
    http_status="$(curl --silent --show-error --output "${probe_body}" --write-out '%{http_code}' \
      --connect-timeout 3 --max-time 10 --cacert "${vite_cert_only}" \
      "https://localhost:${EXPECTED_PORT}/saas" || true)"
    if [ "${http_status}" = "200" ]; then
      printf 'OK|https_probe=200 url=https://localhost:%s/saas\n' "${EXPECTED_PORT}"
    else
      emit_error "https_probe=failed status=${http_status:-none}"
    fi
  fi
fi

if [ "${errors}" -gt 0 ]; then
  printf 'result=not_ready errors=%s\n' "${errors}"
  exit 1
fi

if [ -z "${pids}" ]; then
  printf 'result=prepared server=stopped\n'
else
  printf 'result=ready\n'
fi
