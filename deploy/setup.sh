#!/usr/bin/env bash
#
# Proposito:
#   Desplegar ia_nest_extended de forma declarativa, incluida su configuracion,
#   almacen, esquema, corpus, comandos, servicios y verificacion ejecutable.
#
# Entradas:
#   --config PATH, --print-config y overrides de las claves documentadas en
#   deploy/ejemplo.setup.conf.
#
# Salidas:
#   /opt/ia_nest/config/extended/<instancia>,
#   /opt/ia_nest/state/extended/<instancia>, comandos en /usr/local/bin y,
#   si se solicita, units systemd por instancia.
#
# Requisitos:
#   Bash, curl y Python >= 3.13. Solo PROVISION_STORE=true exige Docker Compose
#   o Podman Compose. El backend de modelos y el core deben existir aparte.

set -Eeuo pipefail

readonly REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly COMPOSE_FILE="${REPO_DIR}/deploy/postgres.compose.yaml"
readonly INSTALL_ROOT="${IANEST_INSTALL_ROOT:-/opt/ia_nest}"
readonly BIN_DIR="${IANEST_BIN_DIR:-/usr/local/bin}"
readonly SYSTEMD_DIR="${IANEST_SYSTEMD_DIR:-/etc/systemd/system}"
readonly -a CONFIG_KEYS=(
  INSTANCE_NAME STORE_DSN PROVISION_STORE CORE_URL EMBEDDINGS_ENDPOINT
  EMBEDDING_MODEL EMBEDDING_DIMENSION EXTRACTION_MODEL REST_HOST REST_PORT
  MCP_HOST MCP_PORT SERVICE_INSTALL SERVICE_ENABLE VERIFY CORPUS_PATH
  CORPUS_NAME CORPUS_DOMAINS OPERATOR_USER REPLACE_CONFIG
)
readonly -a OWN_CAPABILITIES=(
  memory_type.list memory_type.validate memory.recall memory.write
  memory.consolidate memory.maintain knowledge.ingest knowledge.status
  knowledge.suggest knowledge.confirm knowledge.reject
)

declare -A VALUES=(
  [INSTANCE_NAME]=extended
  [STORE_DSN]=postgresql://ianest:ianest_local@127.0.0.1:55432/ianest_extended
  [PROVISION_STORE]=false
  [CORE_URL]=http://127.0.0.1:8000
  [EMBEDDINGS_ENDPOINT]=http://127.0.0.1:11434
  [EMBEDDING_MODEL]=bge-m3
  [EMBEDDING_DIMENSION]=1024
  [EXTRACTION_MODEL]=qwen_tech
  [REST_HOST]=127.0.0.1
  [REST_PORT]=8001
  [MCP_HOST]=127.0.0.1
  [MCP_PORT]=8091
  [SERVICE_INSTALL]=true
  [SERVICE_ENABLE]=true
  [VERIFY]=strict
  [CORPUS_PATH]=''
  [CORPUS_NAME]=''
  [CORPUS_DOMAINS]=''
  [OPERATOR_USER]="${SUDO_USER:-$(id -un)}"
  [REPLACE_CONFIG]=false
)
declare -A SOURCES=()
declare -A ARGUMENTS=()
for key in "${CONFIG_KEYS[@]}"; do SOURCES["${key}"]=default; done

CONFIG_FILE=''
PRINT_CONFIG=false
CONFIG_DIR=''
STATE_DIR=''
ENV_FILE=''
EFFECTIVE_SETUP=''
VENV_DIR=''
RUNTIME=''
declare -a COMPOSE_COMMAND=()

usage() {
  sed -n '2,23p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Overrides:
  --instance-name NAME       --store-dsn DSN
  --provision-store BOOL     --core-url URL
  --embeddings-endpoint URL  --embedding-model MODEL
  --embedding-dimension N    --extraction-model MODEL
  --rest-host HOST           --rest-port PORT
  --mcp-host HOST            --mcp-port PORT
  --service-install BOOL     --service-enable BOOL
  --verify strict|warn|skip  --corpus-path PATH
  --corpus-name NAME         --corpus-domains D1,D2
  --operator-user USER       --replace-config BOOL
EOF
}

log() { printf '[setup] %s\n' "$*"; }
warning() { printf '[setup] WARNING: %s\n' "$*" >&2; }
error() { printf '[setup] ERROR: %s\n' "$*" >&2; exit 1; }

set_argument() { ARGUMENTS["$1"]="$2"; }

load_config_file() {
  local path="$1" line key value line_number=0
  [[ -r "$path" ]] || error "no se puede leer la configuracion: $path"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line_number=$((line_number + 1))
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" == *=* ]] || error "$path:$line_number: se esperaba CLAVE=VALOR"
    key="${line%%=*}"
    value="${line#*=}"
    [[ -n "${VALUES[$key]+present}" ]] || error "$path:$line_number: clave desconocida '$key'"
    VALUES["$key"]="$value"
    SOURCES["$key"]=file
  done < "$path"
}

apply_arguments() {
  local key
  for key in "${CONFIG_KEYS[@]}"; do
    if [[ -n "${ARGUMENTS[$key]+present}" ]]; then
      VALUES["$key"]="${ARGUMENTS[$key]}"
      SOURCES["$key"]=argument
    fi
  done
}

require_bool() {
  [[ "$2" == true || "$2" == false ]] || error "$1 debe ser true o false"
}

resolve_implicit_values() {
  if [[ -z "${VALUES[OPERATOR_USER]}" ]]; then
    VALUES[OPERATOR_USER]="${SUDO_USER:-$(id -un)}"
  fi
}

validate_config() {
  local key
  for key in PROVISION_STORE SERVICE_INSTALL SERVICE_ENABLE REPLACE_CONFIG; do
    require_bool "$key" "${VALUES[$key]}"
  done
  [[ "${VALUES[VERIFY]}" == strict || "${VALUES[VERIFY]}" == warn || "${VALUES[VERIFY]}" == skip ]] ||
    error "VERIFY debe ser strict, warn o skip"
  [[ "${VALUES[INSTANCE_NAME]}" =~ ^[A-Za-z0-9_-]+$ ]] ||
    error "INSTANCE_NAME solo admite letras, numeros, guion y guion bajo"
  [[ "${VALUES[REST_PORT]}" =~ ^[0-9]+$ && "${VALUES[MCP_PORT]}" =~ ^[0-9]+$ ]] ||
    error "REST_PORT y MCP_PORT deben ser numeros"
  ((VALUES[REST_PORT] >= 1 && VALUES[REST_PORT] <= 65535)) || error "REST_PORT fuera de rango"
  ((VALUES[MCP_PORT] >= 1 && VALUES[MCP_PORT] <= 65535)) || error "MCP_PORT fuera de rango"
  [[ "${VALUES[EMBEDDING_DIMENSION]}" =~ ^[1-9][0-9]*$ ]] ||
    error "EMBEDDING_DIMENSION debe ser un entero positivo"
  for key in STORE_DSN CORE_URL EMBEDDINGS_ENDPOINT EMBEDDING_MODEL EXTRACTION_MODEL REST_HOST MCP_HOST OPERATOR_USER; do
    [[ -n "${VALUES[$key]}" ]] || error "$key no puede estar vacio"
  done
  id "${VALUES[OPERATOR_USER]}" >/dev/null 2>&1 || error "OPERATOR_USER no existe: ${VALUES[OPERATOR_USER]}"
  if [[ "${VALUES[SERVICE_ENABLE]}" == true && "${VALUES[SERVICE_INSTALL]}" == false ]]; then
    error "SERVICE_ENABLE=true requiere SERVICE_INSTALL=true"
  fi
  if [[ "${VALUES[VERIFY]}" == strict && "${VALUES[SERVICE_ENABLE]}" == false ]]; then
    error "VERIFY=strict requiere SERVICE_ENABLE=true para verificar REST y MCP escuchando"
  fi
  if [[ -n "${VALUES[CORPUS_PATH]}" ]]; then
    [[ -n "${VALUES[CORPUS_NAME]}" ]] || error "CORPUS_PATH requiere CORPUS_NAME"
    [[ -n "${VALUES[CORPUS_DOMAINS]}" ]] || error "CORPUS_PATH requiere CORPUS_DOMAINS para confirmar vinculos"
  elif [[ -n "${VALUES[CORPUS_NAME]}" || -n "${VALUES[CORPUS_DOMAINS]}" ]]; then
    error "CORPUS_NAME y CORPUS_DOMAINS requieren CORPUS_PATH"
  fi
}

print_config() {
  local key value
  for key in "${CONFIG_KEYS[@]}"; do
    value="${VALUES[$key]}"
    [[ "$key" == STORE_DSN ]] && value='(oculto)'
    printf '%s=%s (%s)\n' "$key" "$value" "${SOURCES[$key]}"
  done
}

check_dependencies() {
  command -v curl >/dev/null 2>&1 || error "curl no encontrado; instalalo y repite"
  local candidate
  for candidate in python3.13 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
      "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 13) or sys.version_info >= (3, 14))'; then
      DEPLOY_PYTHON="$(command -v "$candidate")"
      return
    fi
  done
  error "se requiere Python >=3.13,<3.14; instalalo y repite"
}

prepare_directories() {
  CONFIG_DIR="${INSTALL_ROOT}/config/extended/${VALUES[INSTANCE_NAME]}"
  STATE_DIR="${INSTALL_ROOT}/state/extended/${VALUES[INSTANCE_NAME]}"
  ENV_FILE="${CONFIG_DIR}/extended.env"
  EFFECTIVE_SETUP="${CONFIG_DIR}/setup.conf"
  VENV_DIR="${STATE_DIR}/venv"
  mkdir -p "$CONFIG_DIR" "$STATE_DIR" "${INSTALL_ROOT}/repositories" "$BIN_DIR"
  chown "${VALUES[OPERATOR_USER]}" "$CONFIG_DIR" "$STATE_DIR"
  chmod 700 "$CONFIG_DIR" "$STATE_DIR"
}

respect_existing_config() {
  if [[ -f "$EFFECTIVE_SETUP" && "${VALUES[REPLACE_CONFIG]}" == false ]]; then
    log "Configuracion existente detectada en $EFFECTIVE_SETUP; se preserva (usa REPLACE_CONFIG=true para sustituirla)."
    load_config_file "$EFFECTIVE_SETUP"
    resolve_implicit_values
    validate_config
  elif [[ -f "$ENV_FILE" && "${VALUES[REPLACE_CONFIG]}" == false ]]; then
    log "Configuracion existente detectada en $ENV_FILE; se preserva (no hay snapshot previo)."
  fi
}

write_atomic() {
  local target="$1" mode="$2" temporary
  temporary="$(mktemp "${target}.tmp.XXXXXX")"
  cat > "$temporary"
  chmod "$mode" "$temporary"
  mv -f -- "$temporary" "$target"
}

write_setup_snapshot() {
  local key
  {
    for key in "${CONFIG_KEYS[@]}"; do
      printf '%s=%s\n' "$key" "${VALUES[$key]}"
    done
  } | write_atomic "$EFFECTIVE_SETUP" 600
  chown "${VALUES[OPERATOR_USER]}" "$EFFECTIVE_SETUP"
}

write_environment() {
  {
    printf 'IANEST_EXTENDED_CORE_URL=%s\n' "${VALUES[CORE_URL]}"
    printf 'IANEST_EXTENDED_OLLAMA_URL=%s\n' "${VALUES[EMBEDDINGS_ENDPOINT]}"
    printf 'IANEST_EXTENDED_DATABASE_DSN=%s\n' "${VALUES[STORE_DSN]}"
    printf 'IANEST_EXTENDED_EMBEDDING_MODEL=%s\n' "${VALUES[EMBEDDING_MODEL]}"
    printf 'IANEST_EXTENDED_EMBEDDING_DIMENSION=%s\n' "${VALUES[EMBEDDING_DIMENSION]}"
    printf 'IANEST_EXTENDED_EXTRACTION_MODEL=%s\n' "${VALUES[EXTRACTION_MODEL]}"
    printf 'IANEST_EXTENDED_REST_HOST=%s\n' "${VALUES[REST_HOST]}"
    printf 'IANEST_EXTENDED_REST_PORT=%s\n' "${VALUES[REST_PORT]}"
    printf 'IANEST_EXTENDED_TELEMETRY_DIR=%s\n' "${STATE_DIR}/telemetry"
    printf 'IANEST_EXTENDED_SESSION_STATE_PATH=%s\n' "${STATE_DIR}/session_id"
    printf 'IANEST_EXTENDED_CATALOG_CACHE_PATH=%s\n' "${STATE_DIR}/catalog_cache.json"
  } | write_atomic "$ENV_FILE" 600
  chown "${VALUES[OPERATOR_USER]}" "$ENV_FILE"
}

prepare_venv() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log "Creando entorno Python de despliegue en $VENV_DIR."
    "$DEPLOY_PYTHON" -m venv "$VENV_DIR"
  else
    log "Reutilizando entorno Python de despliegue."
  fi
  "$VENV_DIR/bin/python" -c 'import sys; raise SystemExit(sys.version_info < (3, 13) or sys.version_info >= (3, 14))' ||
    error "el entorno existente no usa Python >=3.13,<3.14"
  log "Comprobando acceso de red al indice de paquetes de pip."
  local package_index="${PIP_INDEX_URL:-}"
  if [[ -z "$package_index" ]]; then
    package_index="$("$VENV_DIR/bin/python" -m pip config get global.index-url 2>/dev/null || true)"
  fi
  package_index="${package_index:-https://pypi.org/simple/}"
  if ! curl --fail --silent --location --connect-timeout 5 --max-time 10 \
    "$package_index" >/dev/null 2>&1; then
    error "red no disponible: no se puede alcanzar el indice de paquetes de pip"
  fi
  log "Instalando o actualizando ia_nest_extended con REST y MCP."
  "$VENV_DIR/bin/python" -m pip install --upgrade "${REPO_DIR}[rest,mcp]"
}

select_container_runtime() {
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    RUNTIME=docker
    COMPOSE_COMMAND=(docker compose)
    return
  fi
  if command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
    if podman compose version >/dev/null 2>&1; then
      RUNTIME=podman
      COMPOSE_COMMAND=(podman compose)
      return
    fi
    if command -v podman-compose >/dev/null 2>&1; then
      RUNTIME=podman
      COMPOSE_COMMAND=(podman-compose)
      return
    fi
  fi
  error "PROVISION_STORE=true pero no hay Docker Compose ni Podman Compose funcional"
}

compose() {
  "${COMPOSE_COMMAND[@]}" --project-name "ianest-extended-${VALUES[INSTANCE_NAME]}" -f "$COMPOSE_FILE" "$@"
}

provision_store() {
  [[ "${VALUES[PROVISION_STORE]}" == true ]] || {
    log "Almacen existente seleccionado; no se consulta runtime de contenedores."
    return
  }
  select_container_runtime
  local -a parts=()
  local parsed_dsn
  parsed_dsn="$("$DEPLOY_PYTHON" - "${VALUES[STORE_DSN]}" <<'PY'
import sys
from urllib.parse import unquote, urlparse

parsed = urlparse(sys.argv[1])
if parsed.scheme not in {"postgres", "postgresql"}:
    raise SystemExit("STORE_DSN debe usar postgresql://")
values = [parsed.hostname or "", str(parsed.port or 5432), unquote(parsed.username or ""), unquote(parsed.password or ""), parsed.path.lstrip("/")]
if any("\n" in item or "\r" in item for item in values):
    raise SystemExit("STORE_DSN contiene un valor no valido")
print("\n".join(values))
PY
  )" || error "no se pudo interpretar STORE_DSN para provisionar el almacen"
  mapfile -t parts <<< "$parsed_dsn"
  ((${#parts[@]} == 5)) || error "STORE_DSN incompleto para provisionar el almacen"
  [[ "${parts[0]}" == 127.0.0.1 || "${parts[0]}" == localhost ]] ||
    error "PROVISION_STORE=true exige STORE_DSN local (127.0.0.1 o localhost)"
  [[ -n "${parts[2]}" && -n "${parts[3]}" && -n "${parts[4]}" ]] ||
    error "STORE_DSN debe incluir usuario, password y base al provisionar"
  export IANEST_EXTENDED_STORE_PORT="${parts[1]}"
  export IANEST_EXTENDED_STORE_USER="${parts[2]}"
  export IANEST_EXTENDED_STORE_PASSWORD="${parts[3]}"
  export IANEST_EXTENDED_STORE_DATABASE="${parts[4]}"
  log "Provisionando PostgreSQL+pgvector local con $RUNTIME."
  compose up -d postgres
  local attempt
  for ((attempt = 1; attempt <= 45; attempt++)); do
    if compose exec -T postgres pg_isready -U "${parts[2]}" -d "${parts[4]}" >/dev/null 2>&1; then
      return
    fi
    sleep 2
  done
  compose ps >&2 || true
  error "el almacen PostgreSQL local no quedo listo tras 90 segundos"
}

extended_cli() {
  (
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ -z "$line" || "$line" == \#* ]] && continue
      export "$line"
    done < "$ENV_FILE"
    "$VENV_DIR/bin/ianest-extended" --env-file "$ENV_FILE" "$@"
  )
}

migrate_schema() {
  log "Verificando conectividad y migrando el esquema."
  local output status
  set +e
  output="$(extended_cli runtime migrate 2>&1)"
  status=$?
  set -e
  if ((status != 0)); then
    printf '%s\n' "$output" >&2
    error "almacen no accesible o migracion fallida con STORE_DSN; causa: ${output:-sin detalle}"
  fi
  printf '%s\n' "$output"
}

ingest_corpus() {
  [[ -n "${VALUES[CORPUS_PATH]}" ]] || return 0
  [[ -r "${VALUES[CORPUS_PATH]}" ]] || error "CORPUS_PATH no es legible: ${VALUES[CORPUS_PATH]}"
  local -a domains=() ingest_args=(knowledge ingest --corpus "${VALUES[CORPUS_NAME]}")
  IFS=',' read -r -a domains <<< "${VALUES[CORPUS_DOMAINS]}"
  local domain trimmed
  for domain in "${domains[@]}"; do
    trimmed="${domain#"${domain%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    [[ -n "$trimmed" ]] || error "CORPUS_DOMAINS contiene un dominio vacio"
    ingest_args+=(--domain "$trimmed")
  done
  ingest_args+=("${VALUES[CORPUS_PATH]}")
  log "Ingeriendo TEXTO del corpus ${VALUES[CORPUS_NAME]}; no se copian vectores."
  extended_cli "${ingest_args[@]}"
  for domain in "${domains[@]}"; do
    trimmed="${domain#"${domain%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    extended_cli knowledge confirm --corpus "${VALUES[CORPUS_NAME]}" --domain "$trimmed"
  done
}

write_wrapper() {
  local name="$1" executable="$2" env_mode="$3"
  {
    printf '#!/usr/bin/env bash\nset -Eeuo pipefail\n'
    if [[ "$env_mode" == argument ]]; then
      printf 'while IFS= read -r line || [[ -n "$line" ]]; do\n'
      printf '  [[ -z "$line" || "$line" == \\#* ]] && continue\n'
      printf '  export "$line"\n'
      printf 'done < %q\n' "$ENV_FILE"
      printf 'exec %q --env-file %q "$@"\n' "$executable" "$ENV_FILE"
    else
      printf 'while IFS= read -r line || [[ -n "$line" ]]; do\n'
      printf '  [[ -z "$line" || "$line" == \\#* ]] && continue\n'
      printf '  export "$line"\n'
      printf 'done < %q\n' "$ENV_FILE"
      printf 'exec %q "$@"\n' "$executable"
    fi
  } | write_atomic "${BIN_DIR}/${name}" 755
}

install_commands() {
  write_wrapper ianest-extended "$VENV_DIR/bin/ianest-extended" argument
  write_wrapper ianest-extended-rest "$VENV_DIR/bin/ianest-extended-rest" environment
  write_wrapper ianest-extended-mcp "$VENV_DIR/bin/ianest-extended-mcp" argument
  log "Comandos instalados en $BIN_DIR; no requieren activar el venv."
}

unit_name() { printf 'ianest-extended-%s-%s.service\n' "${VALUES[INSTANCE_NAME]}" "$1"; }

install_services() {
  [[ "${VALUES[SERVICE_INSTALL]}" == true ]] || return 0
  local rest_unit mcp_unit
  mkdir -p "$SYSTEMD_DIR"
  rest_unit="$(unit_name rest)"
  mcp_unit="$(unit_name mcp)"
  {
    cat <<EOF
[Unit]
Description=IA_NEST Extended REST (${VALUES[INSTANCE_NAME]})
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=${VALUES[OPERATOR_USER]}
WorkingDirectory=${STATE_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/ianest-extended-rest
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
  } | write_atomic "${SYSTEMD_DIR}/${rest_unit}" 644
  {
    cat <<EOF
[Unit]
Description=IA_NEST Extended MCP SSE (${VALUES[INSTANCE_NAME]})
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=${VALUES[OPERATOR_USER]}
WorkingDirectory=${STATE_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/ianest-extended-mcp --transport sse --host ${VALUES[MCP_HOST]} --port ${VALUES[MCP_PORT]} --env-file ${ENV_FILE}
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
  } | write_atomic "${SYSTEMD_DIR}/${mcp_unit}" 644
  systemctl daemon-reload
  if [[ "${VALUES[SERVICE_ENABLE]}" == true ]]; then
    systemctl enable "$rest_unit" "$mcp_unit"
    systemctl restart "$rest_unit" "$mcp_unit"
    wait_for_service "$rest_unit" "${VALUES[REST_HOST]}" "${VALUES[REST_PORT]}" REST
    wait_for_service "$mcp_unit" "${VALUES[MCP_HOST]}" "${VALUES[MCP_PORT]}" MCP
  fi
}

probe_host() {
  case "$1" in
    0.0.0.0) printf '127.0.0.1\n' ;;
    ::|'[::]') printf '::1\n' ;;
    *) printf '%s\n' "$1" ;;
  esac
}

wait_for_port() {
  local host port label attempt target
  host="$1"; port="$2"; label="$3"; target="$(probe_host "$host")"
  for ((attempt = 1; attempt <= 30; attempt++)); do
    if "$VENV_DIR/bin/python" - "$target" "$port" <<'PY' >/dev/null 2>&1
import socket
import sys
with socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=1):
    pass
PY
    then
      log "$label escucha en $host:$port."
      return
    fi
    sleep 1
  done
  printf '[setup] ERROR: %s no escucha en %s:%s tras 30 segundos\n' "$label" "$host" "$port" >&2
  return 1
}

wait_for_service() {
  local unit="$1" host="$2" port="$3" label="$4"
  # Type=simple solo prueba el fork. El puerto es el hecho operativo que manda.
  wait_for_port "$host" "$port" "$label" || error "$label no abrio su puerto"
  systemctl is-active --quiet "$unit" || error "$unit no quedo activo despues de abrir el puerto"
}

verify_rest_catalog() {
  local host response
  host="$(probe_host "${VALUES[REST_HOST]}")"
  [[ "$host" == *:* ]] && host="[$host]"
  response="$(curl --fail --silent --show-error --max-time 10 "http://${host}:${VALUES[REST_PORT]}/capability/list")" ||
    return 1
  printf '%s' "$response" | "$VENV_DIR/bin/python" -c '
import json
import sys
payload = json.load(sys.stdin)
if payload.get("error"):
    raise SystemExit("capability.list declara degradacion: %s" % payload["error"])
found = {item.get("name") for item in payload.get("capabilities", [])}
missing = sorted(set(sys.argv[1:]) - found)
if missing:
    raise SystemExit("faltan capacidades propias: " + ", ".join(missing))
' "${OWN_CAPABILITIES[@]}"
}

verify_runtime() {
  [[ "${VALUES[VERIFY]}" == skip ]] && { log "Verificacion final omitida por VERIFY=skip."; return; }
  local status=0 host
  extended_cli memory_type list --json >/dev/null || status=1
  extended_cli knowledge status --json >/dev/null || status=1
  if [[ "${VALUES[SERVICE_ENABLE]}" == true ]]; then
    wait_for_port "${VALUES[REST_HOST]}" "${VALUES[REST_PORT]}" REST || status=1
    wait_for_port "${VALUES[MCP_HOST]}" "${VALUES[MCP_PORT]}" MCP || status=1
    verify_rest_catalog || status=1
    host="$(probe_host "${VALUES[REST_HOST]}")"
    [[ "$host" == *:* ]] && host="[$host]"
    curl --fail --silent --show-error --max-time 10 "http://${host}:${VALUES[REST_PORT]}/memory_type/list" >/dev/null || status=1
    curl --fail --silent --show-error --max-time 10 "http://${host}:${VALUES[REST_PORT]}/knowledge/status" >/dev/null || status=1
  else
    warning "servicios no habilitados; no se verifican puertos ni REST"
  fi
  if ((status != 0)); then
    if [[ "${VALUES[VERIFY]}" == strict ]]; then
      error "verificacion estricta fallida: revisa esquema, core, puertos y capability.list"
    fi
    warning "verificacion no completada (VERIFY=warn)"
    return
  fi
  log "Verificacion ejecutada con exito: esquema, capacidades propias, REST y MCP."
}

while (($# > 0)); do
  case "$1" in
    --config) (($# >= 2)) || error "--config requiere una ruta"; CONFIG_FILE="$2"; shift 2 ;;
    --print-config) PRINT_CONFIG=true; shift ;;
    --instance-name|--store-dsn|--provision-store|--core-url|--embeddings-endpoint|--embedding-model|--embedding-dimension|--extraction-model|--rest-host|--rest-port|--mcp-host|--mcp-port|--service-install|--service-enable|--verify|--corpus-path|--corpus-name|--corpus-domains|--operator-user|--replace-config)
      (($# >= 2)) || error "$1 requiere un valor"
      key="${1#--}"; key="${key//-/_}"; set_argument "${key^^}" "$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) error "argumento no reconocido: $1" ;;
  esac
done

if [[ -n "$CONFIG_FILE" ]]; then load_config_file "$CONFIG_FILE"; fi
apply_arguments
resolve_implicit_values
validate_config
if [[ "$PRINT_CONFIG" == true ]]; then print_config; exit 0; fi

if [[ "${VALUES[REST_HOST]}" != 127.0.0.1 || "${VALUES[MCP_HOST]}" != 127.0.0.1 ]]; then
  warning "una interfaz no local no tiene autenticacion; protege la red antes de exponerla"
fi

check_dependencies
prepare_directories
respect_existing_config
if [[ ! -f "$ENV_FILE" || "${VALUES[REPLACE_CONFIG]}" == true ]]; then
  write_environment
fi
write_setup_snapshot
mkdir -p "$STATE_DIR/telemetry"
chown -R "${VALUES[OPERATOR_USER]}" "$STATE_DIR"
provision_store
prepare_venv
migrate_schema
ingest_corpus
install_commands
install_services
verify_runtime
log "setup completado: instancia ${VALUES[INSTANCE_NAME]}"
