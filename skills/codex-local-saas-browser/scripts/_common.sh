#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
BUNDLED_COGDB_CERT="${SKILL_DIR}/assets/cogdb-idic.pem"
VITE_CERT_RELATIVE="node_modules/.vite/basic-ssl/_cert.pem"
EXPECTED_COGDB_FINGERPRINT="23E11646AF27FE63E955AA86E4F270AB5325473BEDB332ABA22FECB2B91A091A"
EXPECTED_OIDC_ISSUER="https://account.cogdb.idic/.well-known/openid-configuration"
EXPECTED_OIDC_REDIRECT="https://localhost:3000/console/oidc/callback"
EXPECTED_PORT="3000"
SYSTEM_KEYCHAIN="/Library/Keychains/System.keychain"

die() {
  printf 'ERROR|%s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing_command=$1"
}

resolve_repo() {
  local candidate="$1"
  [ -d "${candidate}" ] || die "repo_not_found=${candidate}"
  (
    cd "${candidate}"
    pwd -P
  )
}

validate_repo() {
  local repo="$1"
  [ -f "${repo}/package.json" ] || die "missing=${repo}/package.json"
  [ -f "${repo}/vite.config.ts" ] || die "missing=${repo}/vite.config.ts"
  [ -f "${repo}/pnpm-lock.yaml" ] || die "missing=${repo}/pnpm-lock.yaml"
  grep -Fq '@vitejs/plugin-basic-ssl' "${repo}/package.json" || die "basic_ssl_dependency=missing"
}

cert_fingerprint() {
  openssl x509 -in "$1" -noout -fingerprint -sha256 \
    | awk -F= '{gsub(":", "", $2); print toupper($2)}'
}

validate_bundled_cogdb_cert() {
  [ -f "${BUNDLED_COGDB_CERT}" ] || die "bundled_cogdb_cert=missing"
  if grep -Fq 'PRIVATE KEY' "${BUNDLED_COGDB_CERT}"; then
    die "bundled_cogdb_cert=contains_private_key"
  fi
  local fingerprint
  fingerprint="$(cert_fingerprint "${BUNDLED_COGDB_CERT}")"
  [ "${fingerprint}" = "${EXPECTED_COGDB_FINGERPRINT}" ] \
    || die "bundled_cogdb_cert=fingerprint_mismatch"
  openssl x509 -in "${BUNDLED_COGDB_CERT}" -noout -checkend 0 >/dev/null 2>&1 \
    || die "bundled_cogdb_cert=expired"
}

extract_certificate_block() {
  local source_file="$1"
  local output_file="$2"
  awk '/-----BEGIN CERTIFICATE-----/{copy=1} copy{print} /-----END CERTIFICATE-----/{exit}' \
    "${source_file}" >"${output_file}"
  openssl x509 -in "${output_file}" -noout >/dev/null 2>&1 \
    || die "certificate_extract=invalid source=${source_file}"
}

system_trust_contains() {
  local fingerprint="$1"
  security find-certificate -a -Z "${SYSTEM_KEYCHAIN}" 2>/dev/null \
    | grep -Fq "SHA-256 hash: ${fingerprint}"
}

env_value() {
  local env_file="$1"
  local key="$2"
  awk -F= -v wanted="${key}" '
    $1 == wanted {
      value = substr($0, index($0, "=") + 1)
      sub(/\r$/, "", value)
    }
    END { if (value != "") print value }
  ' "${env_file}"
}

port_pids() {
  lsof -nP -iTCP:"${EXPECTED_PORT}" -sTCP:LISTEN -t 2>/dev/null | sort -u || true
}

pid_cwd() {
  local pid="$1"
  lsof -a -p "${pid}" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1
}

parse_repo_arg() {
  local repo_arg=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo)
        [ "$#" -ge 2 ] || die "missing_value=--repo"
        repo_arg="$2"
        shift 2
        ;;
      *)
        die "unknown_argument=$1"
        ;;
    esac
  done
  [ -n "${repo_arg}" ] || die "required_argument=--repo"
  resolve_repo "${repo_arg}"
}
