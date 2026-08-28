#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

repo="$(parse_repo_arg "$@")"
[ "$(uname -s)" = "Darwin" ] || die "platform=macos_required"
for command_name in openssl security sudo awk; do
  require_command "${command_name}"
done
validate_repo "${repo}"
validate_bundled_cogdb_cert

vite_combined_cert="${repo}/${VITE_CERT_RELATIVE}"
[ -f "${vite_combined_cert}" ] || die "vite_cert=missing run=prepare-vite-cert.sh"
vite_cert_only="$(mktemp -t codex-local-saas-vite-cert.XXXXXX)"
trap 'rm -f "${vite_cert_only}"' EXIT
extract_certificate_block "${vite_combined_cert}" "${vite_cert_only}"
vite_fingerprint="$(cert_fingerprint "${vite_cert_only}")"
openssl x509 -in "${vite_cert_only}" -noout -ext subjectAltName 2>/dev/null \
  | grep -Fq 'DNS:localhost' || die "vite_cert_san=missing_localhost"

need_cogdb="false"
need_vite="false"
system_trust_contains "${EXPECTED_COGDB_FINGERPRINT}" || need_cogdb="true"
system_trust_contains "${vite_fingerprint}" || need_vite="true"

if [ "${need_cogdb}" = "false" ] && [ "${need_vite}" = "false" ]; then
  printf 'result=already_trusted\n'
  printf 'codex_restart_required=false\n'
  exit 0
fi

printf 'INFO|system_keychain_change=required\n'
printf 'INFO|cogdb_certificate_fingerprint=%s install=%s\n' \
  "${EXPECTED_COGDB_FINGERPRINT}" "${need_cogdb}"
printf 'INFO|vite_certificate_fingerprint=%s install=%s\n' \
  "${vite_fingerprint}" "${need_vite}"

sudo -v
if [ "${need_cogdb}" = "true" ]; then
  sudo security add-trusted-cert -d -r trustRoot -k "${SYSTEM_KEYCHAIN}" \
    "${BUNDLED_COGDB_CERT}"
fi
if [ "${need_vite}" = "true" ]; then
  sudo security add-trusted-cert -d -r trustRoot -k "${SYSTEM_KEYCHAIN}" \
    "${vite_cert_only}"
fi

system_trust_contains "${EXPECTED_COGDB_FINGERPRINT}" \
  || die "cogdb_trust=verification_failed"
system_trust_contains "${vite_fingerprint}" \
  || die "vite_trust=verification_failed"
printf 'result=trusted\n'
printf 'codex_restart_required=true\n'
