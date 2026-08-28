#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

repo="$(parse_repo_arg "$@")"
require_command pnpm
require_command openssl
require_command lsof
validate_repo "${repo}"

vite_combined_cert="${repo}/${VITE_CERT_RELATIVE}"
cert_only="$(mktemp -t codex-local-saas-vite-cert.XXXXXX)"
vite_log="$(mktemp -t codex-local-saas-vite-log.XXXXXX)"
child_pid=""

cleanup() {
  if [ -n "${child_pid}" ] && kill -0 "${child_pid}" 2>/dev/null; then
    kill -TERM "${child_pid}" 2>/dev/null || true
    wait "${child_pid}" 2>/dev/null || true
  fi
  rm -f "${cert_only}" "${vite_log}"
}
trap cleanup EXIT INT TERM

if [ -f "${vite_combined_cert}" ]; then
  extract_certificate_block "${vite_combined_cert}" "${cert_only}"
  if openssl x509 -in "${cert_only}" -noout -checkend 0 >/dev/null 2>&1 \
    && openssl x509 -in "${cert_only}" -noout -ext subjectAltName 2>/dev/null \
      | grep -Fq 'DNS:localhost'; then
    printf 'result=already_present fingerprint=%s\n' "$(cert_fingerprint "${cert_only}")"
    exit 0
  fi
  die "vite_cert=present_but_invalid remove_requires_user_decision path=${vite_combined_cert}"
fi

pids="$(port_pids)"
[ -z "${pids}" ] || die "port_3000=occupied pids=$(printf '%s' "${pids}" | tr '\n' ',')"

(
  cd "${repo}"
  exec env VITE_AGENTATION_DEVTOOLS=false pnpm exec vite --host 127.0.0.1 --port 3000 --strictPort
) >"${vite_log}" 2>&1 &
child_pid=$!

ready="false"
for _attempt in $(seq 1 80); do
  if [ -f "${vite_combined_cert}" ]; then
    ready="true"
    break
  fi
  if ! kill -0 "${child_pid}" 2>/dev/null; then
    break
  fi
  sleep 0.5
done

[ "${ready}" = "true" ] || die "vite_cert=generation_failed"
extract_certificate_block "${vite_combined_cert}" "${cert_only}"
openssl x509 -in "${cert_only}" -noout -ext subjectAltName 2>/dev/null \
  | grep -Fq 'DNS:localhost' || die "vite_cert_san=missing_localhost"
printf 'result=generated fingerprint=%s\n' "$(cert_fingerprint "${cert_only}")"
