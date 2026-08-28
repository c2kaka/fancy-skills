---
name: codex-local-saas-browser
description: Prepare and verify the saas-frontend HTTPS development server at localhost:3000 for access from the Codex in-app browser on macOS, including CogDB certificate trust, Vite certificate trust, OIDC redirect checks, deterministic startup, and browser handoff. Use when localhost SaaS pages fail with SSL, OAuth callback, wrong-worktree, or browser-interaction problems. Do not use for arbitrary local web apps or non-CogDB authentication.
---

# Codex Local SaaS Browser

Make `https://localhost:3000/saas...` reachable in the Codex in-app browser without weakening browser security or guessing which worktree owns the port.

## Invariants

- Use port `3000`. CogDB OAuth must register the exact callback `https://localhost:3000/console/oidc/callback`; changing only the frontend port or `.env` cannot make an unregistered callback valid.
- Use the bundled public certificate at `assets/cogdb-idic.pem`. Its pinned SHA-256 certificate fingerprint is `23:E1:16:46:AF:27:FE:63:E9:55:AA:86:E4:F2:70:AB:53:25:47:3B:ED:B3:32:AB:A2:2F:EC:B2:B9:1A:09:1A`.
- Never record, print, or reuse an administrator password, OAuth client secret, browser cookie, or saved credential.
- Vite's `node_modules/.vite/basic-ssl/_cert.pem` contains a private key followed by a certificate. Scripts may extract and trust only the certificate block; never copy or install the private-key block.
- Never bypass an HTTPS safety interstitial. Install the verified certificates, then restart Codex so its browser process reloads system trust.
- Never kill a process occupying port 3000. If another worktree owns the port, report its PID and working directory and let the user decide.
- Keep JIRA, OAuth-client, and other external systems read-only unless the user separately authorizes a write.

## Deterministic workflow

Resolve the repository path from the user's workspace; do not assume a checkout. Run every script with `--repo <absolute-saas-frontend-path>`.

1. Run the read-only preflight:

   ```bash
   scripts/check.sh --repo /absolute/path/to/saas-frontend --allow-stopped
   ```

   Do not proceed past any `ERROR` line. `server=stopped` is allowed only before startup.

2. If the `.env` OIDC values are wrong, preview the deterministic correction and apply it only when local configuration changes are in scope:

   ```bash
   scripts/configure-env.sh --repo /absolute/path/to/saas-frontend
   scripts/configure-env.sh --repo /absolute/path/to/saas-frontend --apply
   ```

   The script only normalizes four non-secret OIDC keys and never prints or changes the client secret. It deliberately does not set global `NODE_TLS_REJECT_UNAUTHORIZED` configuration.

3. If the Vite certificate has not been generated, run:

   ```bash
   scripts/prepare-vite-cert.sh --repo /absolute/path/to/saas-frontend
   ```

   This starts a temporary Vite process only when port 3000 is free, waits for the certificate, and terminates only the process it created.

4. Installing certificate trust changes macOS security settings. Immediately before running the next command, obtain explicit user confirmation that the two named public certificates will be added to the System keychain. Then run:

   ```bash
   scripts/install-trust.sh --repo /absolute/path/to/saas-frontend
   ```

   If it reports `codex_restart_required=true`, stop and ask the user to restart Codex. Resume only after the user confirms the restart.

5. Start the intended checkout with:

   ```bash
   scripts/start.sh --repo /absolute/path/to/saas-frontend
   ```

   Keep this process running. The script disables Agentation for this process by default so its “Block page interactions” mode cannot intercept browser automation. Pass `--agentation` only when the user explicitly needs that overlay.

6. In a separate command, require a fully ready probe:

   ```bash
   scripts/probe.sh --repo /absolute/path/to/saas-frontend --path /saas
   ```

   Continue only when it returns `result=ready` and a `browser_url`.

7. Use `browser:control-in-app-browser` and follow its instructions. Claim an already-open matching in-app tab when available; otherwise create one. Navigate to the exact `browser_url` from the probe. Do not substitute Chrome unless the user asks.

8. If CogDB authentication appears, use the supported browser flow and existing signed-in session. Do not inspect credentials or session storage. When credentials, OTP, or a CAPTCHA require user action, hand the browser back and resume after the user says it is ready.

9. Verify all three signals before claiming success:

   - the URL origin is exactly `https://localhost:3000`;
   - the path begins with `/saas` (or equals the requested deeper SaaS route);
   - the rendered page contains the authenticated SaaS application shell, not an OAuth management page or an SSL error.

## Failure routing

- `cogdb_trust=missing` or `vite_trust=missing`: run the trust step after confirmation, then restart Codex.
- `vite_cert=missing`: generate it with `prepare-vite-cert.sh`; do not trust the combined private-key file directly.
- `port_owner=other_worktree`: stop. Do not change the redirect to that worktree's port and do not kill it automatically.
- `oidc_redirect=wrong`: normalize `.env`, restart the dev server, and separately confirm the OAuth client has the same exact callback.
- Browser remains on `account.cogdb.idic`: inspect the visible OAuth error and registered callback. Do not invent a redirect or modify the OAuth client without separate authorization.
- Browser shows an HTTPS interstitial after both fingerprints are trusted: do not bypass it; restart Codex and rerun `check.sh` plus `probe.sh`.
- Page clicks create annotations: the server was not started through `start.sh` or Agentation was explicitly enabled. Restart through `start.sh`, or visibly turn off “Block page interactions” before continuing.
