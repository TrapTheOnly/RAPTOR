#!/usr/bin/env bash
# RAPTOR guided installer (OpenClaw-style).
# Interactive by default: writes .env, generates secrets, starts Compose.
set -euo pipefail

CLEAN=false
NO_SCANNER=false
FORCE_SCANNER=false
BUILD=false
YES=false
MODE=""
SHOW_HELP=false

usage() {
  cat <<'EOF'
RAPTOR installer — configure .env and start the Docker stack.

Usage:
  ./scripts/docker_runner.sh [options]

Options:
  --dev                 Development stack (default in the wizard)
  --prod                Production stack (fail-closed secrets / CORS)
  --yes, -y             Non-interactive: use .env + defaults, generate missing secrets
  --build, -b           Rebuild images
  --clean, -v           docker compose down -v (destroys volumes)
  --no-scanner, -n      Do not start Kali + scanner + local model runtime
  --with-scanner        Start Kali + scanner + local model runtime
  -h, --help            Show this help

Examples:
  ./scripts/docker_runner.sh
  ./scripts/docker_runner.sh --prod --build
  ./scripts/docker_runner.sh --dev --yes --no-scanner --build
EOF
}

for arg in "$@"; do
  case "$arg" in
    --clean|-v)       CLEAN=true ;;
    --no-scanner|-n)  NO_SCANNER=true ;;
    --with-scanner)   FORCE_SCANNER=true ;;
    --build|-b)       BUILD=true ;;
    --yes|-y)         YES=true ;;
    --dev)            MODE="dev" ;;
    --prod)           MODE="prod" ;;
    -h|--help)        SHOW_HELP=true ;;
    *)
      echo "Unknown option: $arg" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$SHOW_HELP" == true ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT/.env"
INTERACTIVE=false
if [[ "$YES" == false && -t 0 && -t 1 ]]; then
  INTERACTIVE=true
fi

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing dependency: $1"
}

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

generate_secret() {
  local bytes="${1:-32}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
  else
    python3 - "$bytes" <<'PY'
import secrets, sys
print(secrets.token_hex(int(sys.argv[1])))
PY
  fi
}

ask() {
  local prompt="$1"
  local default="${2:-}"
  local reply=""
  if [[ -n "$default" ]]; then
    read -r -p "$prompt [$default]: " reply || true
    reply="$(trim "${reply:-}")"
    printf '%s' "${reply:-$default}"
  else
    read -r -p "$prompt: " reply || true
    printf '%s' "$(trim "${reply:-}")"
  fi
}

ask_yes() {
  local prompt="$1"
  local default="${2:-y}"
  local hint="Y/n"
  [[ "$default" == "n" ]] && hint="y/N"
  local reply=""
  read -r -p "$prompt [$hint]: " reply || true
  reply="$(trim "${reply:-}")"
  reply="$(printf '%s' "$reply" | tr '[:upper:]' '[:lower:]')"
  if [[ -z "$reply" ]]; then
    [[ "$default" == "y" ]]
    return
  fi
  [[ "$reply" == "y" || "$reply" == "yes" ]]
}

ask_secret_or_generate() {
  local var_name="$1"
  local label="$2"
  local current="${!var_name:-}"
  local choice="" reply=""
  if [[ -n "$current" ]]; then
    echo "  $label: already set (hidden)."
    if ask_yes "  Keep existing $label?" "y"; then
      return 0
    fi
  fi
  read -r -p "  $label: [g]enerate new, or paste a value: " choice || true
  choice="$(trim "${choice:-}")"
  choice="$(printf '%s' "$choice" | tr '[:upper:]' '[:lower:]')"
  if [[ -z "$choice" || "$choice" == "g" || "$choice" == "generate" ]]; then
    printf -v "$var_name" '%s' "$(generate_secret 32)"
    echo "  Generated $label."
  else
    printf -v "$var_name" '%s' "$choice"
  fi
  export "$var_name"
}

load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$(trim "$line")" ]] && continue
    [[ "$(trim "$line")" == \#* ]] && continue
    [[ "$line" == *=* ]] || continue
    local key="${line%%=*}"
    local val="${line#*=}"
    key="$(trim "$key")"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ "${val:0:1}" == '"' && "${val: -1}" == '"' ]]; then
      val="${val:1:${#val}-2}"
    elif [[ "${val:0:1}" == "'" && "${val: -1}" == "'" ]]; then
      val="${val:1:${#val}-2}"
    fi
    if [[ -z "${!key:-}" ]]; then
      export "$key=$val"
    fi
  done < "$file"
}

upsert_env() {
  local file="$1"
  shift
  local tmp
  tmp="$(mktemp)"
  local seen=" "
  if [[ -f "$file" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      line="${line%$'\r'}"
      if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)= ]]; then
        local k="${BASH_REMATCH[1]}"
        local managed=false
        local candidate
        for candidate in "$@"; do
          if [[ "$k" == "$candidate" ]]; then
            managed=true
            break
          fi
        done
        if [[ "$managed" == true ]]; then
          printf '%s=%s\n' "$k" "${!k-}" >>"$tmp"
          seen+="$k "
          continue
        fi
      fi
      printf '%s\n' "$line" >>"$tmp"
    done < "$file"
  else
    {
      echo "# RAPTOR environment — written by scripts/docker_runner.sh"
      echo "# $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo
    } >>"$tmp"
  fi
  local k
  for k in "$@"; do
    if [[ "$seen" != *" $k "* ]]; then
      printf '%s=%s\n' "$k" "${!k-}" >>"$tmp"
    fi
  done
  mv "$tmp" "$file"
}

sync_database_url() {
  export POSTGRES_DB="${POSTGRES_DB:-raptor}"
  export POSTGRES_USER="${POSTGRES_USER:-raptor}"
  export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
  export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"
}

apply_fixed_defaults() {
  export DATA_PATH="${DATA_PATH:-/appdata/data}"
  export APP_PORT="${APP_PORT:-5000}"
  export RAPTOR_API_BASE_URL="${RAPTOR_API_BASE_URL:-http://app:5000}"
  export MCP_PORT="${MCP_PORT:-8081}"
  export RAPTOR_API_TIMEOUT_SECONDS="${RAPTOR_API_TIMEOUT_SECONDS:-30}"
  export MCP_BASE_URL="${MCP_BASE_URL:-http://mcp:8081}"
  export SCANNER_BASE_URL="${SCANNER_BASE_URL:-http://scanner:8082}"
  export LOCAL_LLM_BASE_URL="${LOCAL_LLM_BASE_URL:-http://local-llm:8083}"
  export KALI_SERVER_URL="${KALI_SERVER_URL:-http://kali:5000}"
  export KALI_CLIENT_PATH="${KALI_CLIENT_PATH:-/usr/app/src/scanner/mcp-kali-server/client.py}"
  export ADMIN_USERNAME="${ADMIN_USERNAME:-awadmin}"
  export KEYCLOAK_URL="${KEYCLOAK_URL:-http://keycloak:8080}"
  export KEYCLOAK_PUBLIC_URL="${KEYCLOAK_PUBLIC_URL:-http://localhost:8180}"
  export RAPTOR_PUBLIC_URL="${RAPTOR_PUBLIC_URL:-http://localhost:1337}"
  export KEYCLOAK_REALM="${KEYCLOAK_REALM:-raptor}"
  export KEYCLOAK_ADMIN="${KEYCLOAK_ADMIN:-admin}"
  export KEYCLOAK_LOGIN_CLIENT_ID="${KEYCLOAK_LOGIN_CLIENT_ID:-raptor-login}"
  export KEYCLOAK_BACKEND_CLIENT_ID="${KEYCLOAK_BACKEND_CLIENT_ID:-raptor-backend}"
  export APP_USE_TLS="${APP_USE_TLS:-false}"
  export SESSION_COOKIE_SAMESITE="${SESSION_COOKIE_SAMESITE:-Lax}"
  export FTP_HOST="${FTP_HOST:-ftp}"
  export AWS_REGION="${AWS_REGION:-us-east-1}"
  export SCANNER_MAX_CONCURRENT="${SCANNER_MAX_CONCURRENT:-2}"
}

has_saved_defaults() {
  [[ -f "$ENV_FILE" ]] && [[ -n "${SECRET_KEY:-}" || -n "${POSTGRES_PASSWORD:-}" || -n "${DATABASE_URL:-}" ]]
}

summarize_defaults() {
  echo "  ADMIN_USERNAME=${ADMIN_USERNAME:-}"
  echo "  POSTGRES_DB=${POSTGRES_DB:-}  POSTGRES_USER=${POSTGRES_USER:-}"
  echo "  CORS_ORIGINS=${CORS_ORIGINS:-}"
  echo "  FTP_USER=${FTP_USER:-}"
  echo "  LDAP_SERVER=${LDAP_SERVER:-<unset>}"
  echo "  AWS_REGION=${AWS_REGION:-}"
  if [[ -n "${AWS_BEARER_TOKEN_BEDROCK:-}" ]]; then
    echo "  AWS_BEARER_TOKEN_BEDROCK=<set>"
  else
    echo "  AWS_BEARER_TOKEN_BEDROCK=<not set>"
  fi
  echo "  Secrets already present: SECRET_KEY, MCP, scanner, Kali, DB, FTP, Keycloak (kept hidden)."
}

ensure_secrets() {
  local weak_ok="$1"
  [[ -n "${SECRET_KEY:-}" && "${SECRET_KEY}" != "your_secret_key" ]] || export SECRET_KEY="$(generate_secret 32)"
  [[ -n "${MCP_SERVER_TOKEN:-}" ]] || export MCP_SERVER_TOKEN="$(generate_secret 32)"
  [[ -n "${RAPTOR_SERVICE_API_KEY:-}" ]] || export RAPTOR_SERVICE_API_KEY="$(generate_secret 32)"
  [[ -n "${SCANNER_INTERNAL_TOKEN:-}" ]] || export SCANNER_INTERNAL_TOKEN="$(generate_secret 32)"
  [[ -n "${KALI_INTERNAL_TOKEN:-}" ]] || export KALI_INTERNAL_TOKEN="$(generate_secret 32)"
  [[ -n "${KEYCLOAK_ADMIN:-}" ]] || export KEYCLOAK_ADMIN="admin"
  [[ -n "${KEYCLOAK_ADMIN_PASSWORD:-}" ]] || export KEYCLOAK_ADMIN_PASSWORD="$(generate_secret 24)"
  [[ -n "${KEYCLOAK_LOGIN_CLIENT_SECRET:-}" ]] || export KEYCLOAK_LOGIN_CLIENT_SECRET="$(generate_secret 32)"
  [[ -n "${KEYCLOAK_BACKEND_CLIENT_SECRET:-}" ]] || export KEYCLOAK_BACKEND_CLIENT_SECRET="$(generate_secret 32)"
  if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
    if [[ "$weak_ok" == true ]]; then
      export POSTGRES_PASSWORD="raptor"
    else
      export POSTGRES_PASSWORD="$(generate_secret 16)"
    fi
  fi
  if [[ -z "${FTP_USER:-}" ]]; then
    export FTP_USER="raptor_ftp_user"
  fi
  if [[ -z "${FTP_PASS:-}" ]]; then
    if [[ "$weak_ok" == true ]]; then
      export FTP_PASS="raptor_ftp_pass"
    else
      export FTP_PASS="$(generate_secret 12)"
    fi
  fi
}

run_wizard() {
  echo
  echo "==> RAPTOR installer"
  echo "    This walks through .env, generates secrets, and starts Docker Compose."
  echo "    Existing .env values are kept unless you replace them."
  echo

  if [[ -z "$MODE" ]]; then
    echo "Deploy mode"
    echo "  1) Development  — MCP published on the host"
    echo "  2) Production   — fail-closed secrets, MCP unpublished, worker required"
    local choice
    choice="$(ask "Choose 1 or 2" "1")"
    case "$choice" in
      2|prod|production) MODE="prod" ;;
      *) MODE="dev" ;;
    esac
  fi
  echo "  Using $MODE stack."
  echo

  local use_saved=false
  if has_saved_defaults; then
    echo "==> Found saved defaults in $ENV_FILE"
    summarize_defaults
    echo
    if ask_yes "Use these saved defaults (autofill)?" "y"; then
      use_saved=true
      echo "  Using saved defaults. Secrets and service settings will not be re-prompted."
    else
      echo "  OK — enter new values. Current defaults are shown in [brackets]."
    fi
    echo
  fi

  if [[ "$use_saved" == false ]]; then
    echo "==> Core application"
  ADMIN_USERNAME="$(ask "Admin username" "${ADMIN_USERNAME:-awadmin}")"
  export ADMIN_USERNAME
  ask_secret_or_generate SECRET_KEY "SECRET_KEY"
  echo

  echo "==> Database"
  POSTGRES_DB="$(ask "Postgres database name" "${POSTGRES_DB:-raptor}")"
  POSTGRES_USER="$(ask "Postgres user" "${POSTGRES_USER:-raptor}")"
  export POSTGRES_DB POSTGRES_USER
  ask_secret_or_generate POSTGRES_PASSWORD "POSTGRES_PASSWORD"
  echo

  echo "==> Browser access / CORS"
  if [[ "$MODE" == "prod" ]]; then
    local cors_default="${CORS_ORIGINS:-}"
    [[ "$cors_default" == "*" ]] && cors_default=""
    CORS_ORIGINS="$(ask "Public origin allowlist (comma-separated, no *)" "$cors_default")"
    [[ -n "$CORS_ORIGINS" && "$CORS_ORIGINS" != "*" ]] || fail "Production requires an explicit CORS_ORIGINS allowlist."
    RAPTOR_PUBLIC_URL="$(ask "Public RAPTOR URL (SSO callback origin)" "${RAPTOR_PUBLIC_URL:-${CORS_ORIGINS%%,*}}")"
    KEYCLOAK_PUBLIC_URL="$(ask "Public Keycloak URL (browser SSO redirects)" "${KEYCLOAK_PUBLIC_URL:-}")"
    export RAPTOR_PUBLIC_URL KEYCLOAK_PUBLIC_URL
    if ask_yes "Terminate TLS inside the app container? (usually no — reverse proxy does TLS)" "n"; then
      APP_USE_TLS="true"
      CERT_FILE="$(ask "CERT_FILE path in container" "${CERT_FILE:-/certs/cert.pem}")"
      KEY_FILE="$(ask "KEY_FILE path in container" "${KEY_FILE:-/certs/key.pem}")"
      export CERT_FILE KEY_FILE
    else
      APP_USE_TLS="false"
    fi
  else
    CORS_ORIGINS="$(ask "CORS_ORIGINS" "${CORS_ORIGINS:-*}")"
    APP_USE_TLS="${APP_USE_TLS:-false}"
  fi
  export CORS_ORIGINS APP_USE_TLS
  echo

  echo "==> FTP (report storage)"
  FTP_USER="$(ask "FTP username" "${FTP_USER:-raptor_ftp_user}")"
  export FTP_USER
  ask_secret_or_generate FTP_PASS "FTP_PASS"
  echo

  echo "==> Internal tokens (MCP, scanner, Kali)"
  ask_secret_or_generate MCP_SERVER_TOKEN "MCP_SERVER_TOKEN"
  ask_secret_or_generate RAPTOR_SERVICE_API_KEY "RAPTOR_SERVICE_API_KEY"
  ask_secret_or_generate SCANNER_INTERNAL_TOKEN "SCANNER_INTERNAL_TOKEN"
  ask_secret_or_generate KALI_INTERNAL_TOKEN "KALI_INTERNAL_TOKEN"
  if [[ "$MODE" == "prod" ]]; then
    MCP_ALLOWED_HOSTS="$(ask "MCP_ALLOWED_HOSTS (public Host header values, optional)" "${MCP_ALLOWED_HOSTS:-}")"
    MCP_ALLOWED_ORIGINS="$(ask "MCP_ALLOWED_ORIGINS (optional)" "${MCP_ALLOWED_ORIGINS:-}")"
    export MCP_ALLOWED_HOSTS MCP_ALLOWED_ORIGINS
  fi
  echo

  echo "==> Optional: LDAP"
  if ask_yes "Configure LDAP now?" "n"; then
    LDAP_SERVER="$(ask "LDAP_SERVER" "${LDAP_SERVER:-}")"
    LDAP_DOMAIN="$(ask "LDAP_DOMAIN" "${LDAP_DOMAIN:-}")"
    LDAP_USER="$(ask "LDAP bind user" "${LDAP_USER:-}")"
    LDAP_PASS="$(ask "LDAP bind password" "${LDAP_PASS:-}")"
    LDAP_USERS_DN="$(ask "LDAP_USERS_DN (blank = DC= from domain)" "${LDAP_USERS_DN:-}")"
    LDAP_USE_SSL="$(ask "LDAP_USE_SSL (true/false/blank=try both)" "${LDAP_USE_SSL:-}")"
    LDAP_TRUSTSTORE="$(ask "LDAP_TRUSTSTORE (never|ldapsOnly|always)" "${LDAP_TRUSTSTORE:-never}")"
    export LDAP_SERVER LDAP_DOMAIN LDAP_USER LDAP_PASS LDAP_USERS_DN LDAP_USE_SSL LDAP_TRUSTSTORE
  fi
  echo

  echo "==> Optional: OIDC/SAML identity provider"
  if ask_yes "Register a Keycloak identity provider from env?" "n"; then
    KEYCLOAK_IDP_ALIAS="$(ask "KEYCLOAK_IDP_ALIAS" "${KEYCLOAK_IDP_ALIAS:-}")"
    KEYCLOAK_IDP_PROVIDER="$(ask "KEYCLOAK_IDP_PROVIDER (oidc|keycloak-oidc|saml)" "${KEYCLOAK_IDP_PROVIDER:-oidc}")"
    KEYCLOAK_IDP_DISPLAY_NAME="$(ask "KEYCLOAK_IDP_DISPLAY_NAME" "${KEYCLOAK_IDP_DISPLAY_NAME:-}")"
    KEYCLOAK_IDP_CLIENT_ID="$(ask "KEYCLOAK_IDP_CLIENT_ID" "${KEYCLOAK_IDP_CLIENT_ID:-}")"
    KEYCLOAK_IDP_CLIENT_SECRET="$(ask "KEYCLOAK_IDP_CLIENT_SECRET" "${KEYCLOAK_IDP_CLIENT_SECRET:-}")"
    KEYCLOAK_IDP_ISSUER="$(ask "KEYCLOAK_IDP_ISSUER" "${KEYCLOAK_IDP_ISSUER:-}")"
    KEYCLOAK_IDP_AUTHORIZATION_URL="$(ask "KEYCLOAK_IDP_AUTHORIZATION_URL (if no issuer)" "${KEYCLOAK_IDP_AUTHORIZATION_URL:-}")"
    KEYCLOAK_IDP_TOKEN_URL="$(ask "KEYCLOAK_IDP_TOKEN_URL (if no issuer)" "${KEYCLOAK_IDP_TOKEN_URL:-}")"
    KEYCLOAK_IDP_ENTITY_ID="$(ask "KEYCLOAK_IDP_ENTITY_ID (SAML)" "${KEYCLOAK_IDP_ENTITY_ID:-}")"
    KEYCLOAK_IDP_SSO_URL="$(ask "KEYCLOAK_IDP_SSO_URL (SAML)" "${KEYCLOAK_IDP_SSO_URL:-}")"
    export KEYCLOAK_IDP_ALIAS KEYCLOAK_IDP_PROVIDER KEYCLOAK_IDP_DISPLAY_NAME \
      KEYCLOAK_IDP_CLIENT_ID KEYCLOAK_IDP_CLIENT_SECRET KEYCLOAK_IDP_ISSUER \
      KEYCLOAK_IDP_AUTHORIZATION_URL KEYCLOAK_IDP_TOKEN_URL KEYCLOAK_IDP_ENTITY_ID KEYCLOAK_IDP_SSO_URL
  fi
  echo

  echo "==> Optional: AI scanner + Kali + local model runtime"
  if [[ "$FORCE_SCANNER" == true ]]; then
    NO_SCANNER=false
    echo "  Scanner requested (--with-scanner)."
  elif [[ "$NO_SCANNER" == true ]]; then
    echo "  Skipping (--no-scanner)."
  elif ask_yes "Start Kali, the AI scanner, and the local model runtime?" "n"; then
    NO_SCANNER=false
  else
    NO_SCANNER=true
  fi
  if [[ "$NO_SCANNER" == false ]]; then
    echo "  Providers and the bundled Qwen model are configured in Admin Settings."
    AWS_REGION="${AWS_REGION:-us-east-1}"
    export AWS_REGION
    if [[ -n "${AWS_BEARER_TOKEN_BEDROCK:-}" ]]; then
      if ! ask_yes "Keep existing AWS_BEARER_TOKEN_BEDROCK as a Bedrock fallback?" "y"; then
        AWS_BEARER_TOKEN_BEDROCK="$(ask "AWS_BEARER_TOKEN_BEDROCK (optional fallback)" "")"
      fi
      export AWS_BEARER_TOKEN_BEDROCK
    fi
  fi
  echo
  fi

  if [[ "$NO_SCANNER" == false && -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]]; then
    echo "NOTE: AWS_BEARER_TOKEN_BEDROCK is unset. Bedrock can still be added later in Admin Settings." >&2
  fi

  if [[ "$BUILD" == false ]]; then
    if ask_yes "Rebuild images (--build)?" "y"; then
      BUILD=true
    fi
  fi
  if [[ "$CLEAN" == false ]] && ! postgres_volume_exists; then
    if ask_yes "Wipe Docker volumes on this start (--clean)? This deletes DB data." "n"; then
      CLEAN=true
    fi
  fi
}

validate_config() {
  apply_fixed_defaults
  sync_database_url
  [[ -n "${SECRET_KEY:-}" && "${SECRET_KEY}" != "your_secret_key" ]] || fail "SECRET_KEY is missing."
  [[ -n "${POSTGRES_PASSWORD:-}" ]] || fail "POSTGRES_PASSWORD is missing."
  [[ -n "${DATABASE_URL:-}" ]] || fail "DATABASE_URL is missing."
  [[ -n "${MCP_SERVER_TOKEN:-}" ]] || fail "MCP_SERVER_TOKEN is missing."
  [[ -n "${RAPTOR_SERVICE_API_KEY:-}" ]] || fail "RAPTOR_SERVICE_API_KEY is missing."
  [[ -n "${SCANNER_INTERNAL_TOKEN:-}" ]] || fail "SCANNER_INTERNAL_TOKEN is missing."
  [[ -n "${KEYCLOAK_ADMIN_PASSWORD:-}" ]] || fail "KEYCLOAK_ADMIN_PASSWORD is missing."
  [[ -n "${KEYCLOAK_LOGIN_CLIENT_SECRET:-}" ]] || fail "KEYCLOAK_LOGIN_CLIENT_SECRET is missing."
  [[ -n "${KEYCLOAK_BACKEND_CLIENT_SECRET:-}" ]] || fail "KEYCLOAK_BACKEND_CLIENT_SECRET is missing."
  if [[ "$MODE" == "prod" ]]; then
    [[ -n "${CORS_ORIGINS:-}" && "${CORS_ORIGINS}" != "*" ]] || fail "Production CORS_ORIGINS must be an explicit allowlist."
    [[ -n "${FTP_USER:-}" && -n "${FTP_PASS:-}" ]] || fail "Production requires FTP_USER and FTP_PASS."
  fi
  if [[ "$NO_SCANNER" == false && -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]]; then
    echo "NOTE: AWS_BEARER_TOKEN_BEDROCK is unset. Configure providers in Admin Settings." >&2
  fi
}

write_env() {
  upsert_env "$ENV_FILE" \
    SECRET_KEY \
    ADMIN_USERNAME \
    CORS_ORIGINS \
    SESSION_COOKIE_SAMESITE \
    APP_PORT \
    APP_USE_TLS \
    CERT_FILE \
    KEY_FILE \
    POSTGRES_DB \
    POSTGRES_USER \
    POSTGRES_PASSWORD \
    DATABASE_URL \
    DATA_PATH \
    FTP_USER \
    FTP_PASS \
    FTP_HOST \
    MCP_SERVER_TOKEN \
    RAPTOR_SERVICE_API_KEY \
    RAPTOR_API_BASE_URL \
    MCP_PORT \
    MCP_BASE_URL \
    RAPTOR_API_TIMEOUT_SECONDS \
    MCP_ALLOWED_HOSTS \
    MCP_ALLOWED_ORIGINS \
    SCANNER_INTERNAL_TOKEN \
    SCANNER_BASE_URL \
    LOCAL_LLM_BASE_URL \
    SCANNER_MAX_CONCURRENT \
    AWS_BEARER_TOKEN_BEDROCK \
    AWS_REGION \
    KALI_INTERNAL_TOKEN \
    KALI_SERVER_URL \
    KALI_CLIENT_PATH \
    LDAP_SERVER \
    LDAP_DOMAIN \
    LDAP_USER \
    LDAP_PASS \
    LDAP_USERS_DN \
    LDAP_VENDOR \
    LDAP_USE_SSL \
    LDAP_START_TLS \
    LDAP_TRUSTSTORE \
    LDAP_USERNAME_ATTR \
    LDAP_UUID_ATTR \
    LDAP_USER_OBJECT_CLASSES \
    KEYCLOAK_IDP_ALIAS \
    KEYCLOAK_IDP_PROVIDER \
    KEYCLOAK_IDP_DISPLAY_NAME \
    KEYCLOAK_IDP_ISSUER \
    KEYCLOAK_IDP_AUTHORIZATION_URL \
    KEYCLOAK_IDP_TOKEN_URL \
    KEYCLOAK_IDP_JWKS_URL \
    KEYCLOAK_IDP_LOGOUT_URL \
    KEYCLOAK_IDP_CLIENT_ID \
    KEYCLOAK_IDP_CLIENT_SECRET \
    KEYCLOAK_IDP_ENTITY_ID \
    KEYCLOAK_IDP_SSO_URL \
    KEYCLOAK_URL \
    KEYCLOAK_PUBLIC_URL \
    RAPTOR_PUBLIC_URL \
    KEYCLOAK_REALM \
    KEYCLOAK_ADMIN \
    KEYCLOAK_ADMIN_PASSWORD \
    KEYCLOAK_LOGIN_CLIENT_ID \
    KEYCLOAK_LOGIN_CLIENT_SECRET \
    KEYCLOAK_BACKEND_CLIENT_ID \
    KEYCLOAK_BACKEND_CLIENT_SECRET \
    DB_AND_BACKUPS_VOLUME_NAME \
    CERTS_VOLUME_NAME \
    FTP_VOLUME_NAME \
    POSTGRES_DATA_VOLUME_NAME \
    LLM_MODELS_VOLUME_NAME
  echo "==> Wrote $ENV_FILE"
}

postgres_volume_name() {
  printf '%s' "${POSTGRES_DATA_VOLUME_NAME:-raptor_postgres_data_volume}"
}

postgres_volume_exists() {
  docker volume inspect "$(postgres_volume_name)" >/dev/null 2>&1
}

align_postgres_with_existing_volume() {
  if [[ "$CLEAN" == true ]]; then
    return 0
  fi
  postgres_volume_exists || return 0
  echo
  echo "==> Existing PostgreSQL volume: $(postgres_volume_name)"
  echo "    Docker sets POSTGRES_PASSWORD only the first time this volume is created."
  echo "    A new password in .env will not change the database, and the app will fail to log in."
  if [[ "$INTERACTIVE" != true ]]; then
    if [[ "$PASSWORD_WAS_LOADED" != true ]]; then
      fail "Existing Postgres volume found, but no POSTGRES_PASSWORD in .env. Set it to the original password or re-run with --clean."
    fi
    echo "    Reusing the volume with the current .env password. Use --clean to wipe it."
    return 0
  fi
  echo
  echo "  1) Reuse the volume with the current .env password"
  echo "  2) Wipe all Docker volumes (--clean) and initialize with the current .env password"
  echo "  3) Keep the data and set POSTGRES_PASSWORD to the old default 'raptor'"
  echo "     (choose 3 if you just saw 'password authentication failed')"
  local choice
  choice="$(ask "Choose 1, 2, or 3" "1")"
  case "$choice" in
    2)
      CLEAN=true
      echo "  Will wipe Docker volumes on start."
      ;;
    3)
      export POSTGRES_PASSWORD="raptor"
      sync_database_url
      echo "  POSTGRES_PASSWORD set to the legacy default. DATABASE_URL updated."
      ;;
    1)
      echo "  Reusing the existing volume."
      ;;
    *)
      echo "  Reusing the existing volume."
      ;;
  esac
}

diagnose_startup_failure() {
  echo
  echo "==> App did not become healthy. Recent app/worker logs:"
  docker compose -f "$COMPOSE" logs --no-color --tail 40 app worker >&2 || true
  if docker compose -f "$COMPOSE" logs --no-color --tail 80 app worker 2>/dev/null | grep -q "password authentication failed"; then
    cat <<EOF >&2

The database rejected the password in .env. The Postgres volume was likely
created earlier with a different password (often 'raptor' from the old runner).

Fix (pick one):
  ./scripts/docker_runner.sh --no-scanner
    then choose option 3 (legacy password 'raptor'), or option 2 (wipe DB)

  ./scripts/docker_runner.sh --no-scanner --clean
    wipes volumes and initializes Postgres with the current .env password
EOF
  fi
}

wait_for_health() {
  local url="$1"
  local tries=60
  [[ "$BUILD" == true ]] && tries=120
  local i
  for i in $(seq 1 "$tries"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "==> Healthy: $url"
      return 0
    fi
    sleep 2
  done
  echo "WARNING: $url did not become healthy in time." >&2
  diagnose_startup_failure
}

require_cmd docker
if ! docker compose version >/dev/null 2>&1; then
  fail "Docker Compose is not available (try: docker compose version)"
fi

cd "$ROOT"
load_env_file "$ENV_FILE"
PASSWORD_WAS_LOADED=false
if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
  PASSWORD_WAS_LOADED=true
fi
apply_fixed_defaults

if [[ "$INTERACTIVE" == true ]]; then
  run_wizard
else
  MODE="${MODE:-dev}"
  if [[ "$FORCE_SCANNER" == true ]]; then
    NO_SCANNER=false
  elif [[ "$NO_SCANNER" == false && -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]]; then
    echo "NOTE: AWS_BEARER_TOKEN_BEDROCK is unset. Configure providers in Admin Settings." >&2
  fi
  ensure_secrets "$([[ "$MODE" == "dev" ]] && echo true || echo false)"
  export CORS_ORIGINS="${CORS_ORIGINS:-*}"
  if [[ "$MODE" == "prod" && ( -z "${CORS_ORIGINS:-}" || "${CORS_ORIGINS}" == "*" ) ]]; then
    fail "Non-interactive production requires CORS_ORIGINS in the environment or .env (no *)."
  fi
fi

[[ "$MODE" == "prod" || "$MODE" == "dev" ]] || fail "Mode must be dev or prod."
if [[ "$MODE" == "prod" ]]; then
  COMPOSE="docker-compose.prod.yml"
  APP_CONTAINER="raptor-prod"
else
  COMPOSE="docker-compose.dev.yml"
  APP_CONTAINER="raptor-dev"
  export CORS_ORIGINS="${CORS_ORIGINS:-*}"
fi

ensure_secrets "$([[ "$MODE" == "dev" ]] && echo true || echo false)"
align_postgres_with_existing_volume
validate_config

if [[ "$INTERACTIVE" == true ]]; then
  echo "==> Ready to start"
  echo "    Mode:     $MODE"
  echo "    Compose:  $COMPOSE"
  echo "    Build:    $BUILD"
  echo "    Clean:    $CLEAN"
  echo "    Scanner:  $([[ "$NO_SCANNER" == true ]] && echo skipped || echo enabled)"
  echo "    Env file: $ENV_FILE"
  if ! ask_yes "Write .env and start the stack?" "y"; then
    echo "Aborted."
    exit 0
  fi
fi

write_env

echo "==> Stopping existing stack"
DOWN_ARGS=("-f" "$COMPOSE" "down" "--remove-orphans")
if [[ "$CLEAN" == true ]]; then
  DOWN_ARGS+=("-v")
fi
docker compose "${DOWN_ARGS[@]}"

SERVICES=("postgres" "ftp" "keycloak" "app" "worker" "mcp")
if [[ "$NO_SCANNER" == false ]]; then
  SERVICES+=("kali" "scanner" "local-llm")
fi

echo "==> Starting: ${SERVICES[*]}"
UP_ARGS=("-f" "$COMPOSE" "up" "-d")
if [[ "$BUILD" == true ]]; then
  UP_ARGS+=("--build")
fi
UP_ARGS+=("${SERVICES[@]}")
docker compose "${UP_ARGS[@]}"

if command -v curl >/dev/null 2>&1; then
  wait_for_health "http://localhost:1337/healthz"
fi

echo
echo "RAPTOR $MODE stack is up."
echo "  App:     http://localhost:1337"
echo "  Health:  http://localhost:1337/healthz"
if [[ "$MODE" == "dev" ]]; then
  echo "  MCP:     http://localhost:${MCP_PORT}/mcp"
  echo "  Keycloak console (ops only): http://localhost:8180"
else
  echo "  MCP:     unpublished on the host (app_network only)"
fi
if [[ "$NO_SCANNER" == false ]]; then
  echo "  Scanner: internal (http://scanner:8082)"
  echo "  Kali:    internal (http://kali:5000)"
  echo "  Local LLM manager: internal (http://local-llm:8083)"
fi
echo
echo "Next steps:"
echo "  1. Open the app and sign in as ${ADMIN_USERNAME}."
echo "     First-run credentials are written inside the app volume:"
echo "     docker exec $APP_CONTAINER sh -c 'cat \"\$DATA_PATH/initial_admin_credentials.txt\"'"
echo "  2. Delete that credentials file after you log in."
echo "  3. Create a service account in Admin Settings if external MCP clients need a hashed API key."
echo
echo "Logs:"
echo "  docker compose -f $COMPOSE logs -f app worker"
echo "  docker compose -f $COMPOSE ps"
