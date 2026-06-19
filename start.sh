#!/bin/sh
set -e

# start.sh — Secure startup wrapper for antigravity-cli-proxy.
# Authenticates with Infisical via Universal Auth (credentials come from
# /etc/environment, which systemd user services inherit automatically) and
# injects AGENTMEMORY_OPENROUTER_TOKEN into the proxy process environment.
# The token is NEVER written to disk or logged.

# Resolve credential aliases: support both INFISICAL_CLIENT_ID and
# INFISICAL_UNIVERSAL_AUTH_CLIENT_ID naming conventions.
_CLIENT_ID="${INFISICAL_UNIVERSAL_AUTH_CLIENT_ID:-${INFISICAL_CLIENT_ID}}"
_CLIENT_SECRET="${INFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET:-${INFISICAL_CLIENT_SECRET}}"
_DOMAIN="${INFISICAL_HOST_URL:-http://localhost:3080}"
_PROJECT_ID="6154b204-a661-480c-b133-5f8a32328537"
_ENV="dev"

if [ -z "$_CLIENT_ID" ] || [ -z "$_CLIENT_SECRET" ]; then
    echo "ERROR: Infisical credentials not found (INFISICAL_CLIENT_ID / INFISICAL_CLIENT_SECRET)." >&2
    echo "       Ensure /etc/environment is populated with Nimblerbox machine identity creds." >&2
    exit 1
fi

# Obtain a short-lived Infisical access token via Universal Auth.
# --plain --silent outputs only the token string to stdout.
export INFISICAL_TOKEN
INFISICAL_TOKEN=$(infisical login \
    --method=universal-auth \
    --client-id="$_CLIENT_ID" \
    --client-secret="$_CLIENT_SECRET" \
    --domain="$_DOMAIN" \
    --plain --silent)

if [ -z "$INFISICAL_TOKEN" ]; then
    echo "ERROR: infisical login returned an empty token. Check Infisical connectivity at $_DOMAIN." >&2
    exit 1
fi

# Inject secrets from the Nimblerbox project (dev environment) and exec the proxy.
# infisical run exports secrets as env vars into the child process without
# writing them to disk.
exec infisical run \
    --projectId="$_PROJECT_ID" \
    --env="$_ENV" \
    --domain="$_DOMAIN" \
    -- /home/ericmaster/agentic/antigravity-cli-proxy/.venv/bin/python -m src
