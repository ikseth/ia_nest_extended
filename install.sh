#!/usr/bin/env bash
#
# Proposito:
#   Preparar el entorno de desarrollo local de ia_nest_extended y verificarlo.
#
# Entradas:
#   --assume-yes  autoriza sin pregunta la instalacion de paquetes con zypper.
#   --skip-db     omite runtime, postgres y pruebas de DB.
#   --skip-tests  prepara el entorno pero no ejecuta pytest.
#   --pull-models descarga los modelos configurados tras comprobar Ollama.
#
# Salidas:
#   .venv con el paquete editable y sus dependencias de prueba instaladas.
#   PostgreSQL+pgvector local levantado por docker-compose.dev.yml, salvo
#   --skip-db.
#
# Efectos:
#   Puede instalar paquetes openSUSE, crear o actualizar .venv, descargar la
#   imagen pgvector, crear el volumen local y ejecutar la suite de pruebas.
#
# Requisitos:
#   openSUSE con zypper para instalar recursos ausentes; acceso root o sudo para
#   esa instalacion. Otras distribuciones se detectan, pero aun no se soportan.
#
# Seguridad:
#   La DB escucha solo en 127.0.0.1. El DSN de pruebas debe apuntar a loopback.
#   No conecta a bases de datos ni hosts de laboratorio.

set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly script_dir
readonly compose_file="${script_dir}/docker-compose.dev.yml"
readonly test_dsn="postgresql://ianest:ianest_local@127.0.0.1:55432/ianest_extended"
readonly db_wait_seconds=90
readonly default_core_url="http://127.0.0.1:8000"
readonly default_ollama_url="http://127.0.0.1:11434"
readonly default_embedding_model="bge-m3"
readonly default_embedding_dimension=1024
readonly default_extraction_model="qwen2.5:7b"

assume_yes=false
skip_db=false
skip_tests=false
pull_models=false
core_url="${default_core_url}"
ollama_url="${default_ollama_url}"
embedding_model="${default_embedding_model}"
embedding_dimension="${default_embedding_dimension}"
extraction_model="${default_extraction_model}"
core_url_set=false
ollama_url_set=false
embedding_model_set=false
embedding_dimension_set=false
extraction_model_set=false
os_id=""
os_id_like=""
runtime=""
compose_command=()
test_output=""

usage() {
    cat <<'EOF'
Uso: ./install.sh [opciones]

Prepara el entorno de desarrollo local y ejecuta sus pruebas.

Opciones:
  --assume-yes  No preguntar antes de instalar paquetes con zypper.
  --skip-db     Omitir runtime, postgres y pruebas que necesitan DB.
  --skip-tests  Preparar recursos sin ejecutar pytest.
  --core-url URL
                URL REST del core (default: http://127.0.0.1:8000).
  --ollama-url URL
                URL de Ollama (default: http://127.0.0.1:11434).
  --embedding-model MODELO
                Modelo de embeddings (default: bge-m3).
  --embedding-dimension N
                Dimension del embedding (default: 1024).
  --extraction-model MODELO
                Modelo de extraccion (default: qwen2.5:7b).
  --pull-models Descargar los modelos solo si Ollama es alcanzable.
  --help        Mostrar esta ayuda.
EOF
}

log() {
    printf '[install] %s\n' "$*"
}

fail() {
    printf '[install] ERROR: %s\n' "$*" >&2
    exit 1
}

require_option_value() {
    local option="$1"
    local value="${2:-}"
    [[ -n "${value}" && "${value}" != --* ]] ||
        fail "${option} exige un valor"
}

prompt_setting() {
    local label="$1"
    local current="$2"
    local result_name="$3"
    local answer=""

    [[ -t 0 ]] ||
        fail "la configuracion interactiva exige terminal; usa --assume-yes"
    printf '[install] %s [%s]: ' "${label}" "${current}"
    read -r answer
    if [[ -n "${answer}" ]]; then
        printf -v "${result_name}" '%s' "${answer}"
    fi
}

configure_extended() {
    if [[ "${assume_yes}" == false ]]; then
        if [[ "${core_url_set}" == false ]]; then
            prompt_setting "URL del core" "${core_url}" core_url
        fi
        if [[ "${ollama_url_set}" == false ]]; then
            prompt_setting "URL de Ollama" "${ollama_url}" ollama_url
        fi
        if [[ "${embedding_model_set}" == false ]]; then
            prompt_setting \
                "Modelo de embeddings" "${embedding_model}" embedding_model
        fi
        if [[ "${embedding_dimension_set}" == false ]]; then
            prompt_setting \
                "Dimension del embedding" \
                "${embedding_dimension}" \
                embedding_dimension
        fi
        if [[ "${extraction_model_set}" == false ]]; then
            prompt_setting \
                "Modelo de extraccion" \
                "${extraction_model}" \
                extraction_model
        fi
    fi

    [[ "${embedding_dimension}" =~ ^[1-9][0-9]*$ ]] ||
        fail "embedding-dimension debe ser un entero positivo"
    [[ -n "${core_url}" && -n "${ollama_url}" ]] ||
        fail "las URL configuradas no pueden estar vacias"
    [[ -n "${embedding_model}" && -n "${extraction_model}" ]] ||
        fail "los modelos configurados no pueden estar vacios"
}

update_env_value() {
    local key="$1"
    local value="$2"
    local env_file="${script_dir}/.env"
    local temp_file=""
    temp_file="$(mktemp "${TMPDIR:-/tmp}/ianest-extended-env.XXXXXX")"

    if [[ -f "${env_file}" ]]; then
        awk -v key="${key}" -v value="${value}" '
            BEGIN { found = 0 }
            index($0, key "=") == 1 {
                if (!found) {
                    print key "=" value
                    found = 1
                }
                next
            }
            { print }
            END {
                if (!found) {
                    print key "=" value
                }
            }
        ' "${env_file}" >"${temp_file}"
    else
        printf '%s=%s\n' "${key}" "${value}" >"${temp_file}"
    fi
    mv -- "${temp_file}" "${env_file}"
}

write_extended_env() {
    log "Escribiendo configuracion local en .env."
    update_env_value IANEST_EXTENDED_CORE_URL "${core_url}"
    update_env_value IANEST_EXTENDED_OLLAMA_URL "${ollama_url}"
    update_env_value IANEST_EXTENDED_DATABASE_DSN "${test_dsn}"
    update_env_value IANEST_EXTENDED_EMBEDDING_MODEL "${embedding_model}"
    update_env_value \
        IANEST_EXTENDED_EMBEDDING_DIMENSION "${embedding_dimension}"
    update_env_value IANEST_EXTENDED_EXTRACTION_MODEL "${extraction_model}"
    update_env_value IANEST_EXTENDED_TELEMETRY_DIR "telemetry/"
}

pull_configured_models() {
    if [[ "${pull_models}" == false ]]; then
        return 0
    fi
    command -v curl >/dev/null 2>&1 ||
        fail "--pull-models exige curl para comprobar Ollama"
    if ! curl --fail --silent --show-error --max-time 3 \
        "${ollama_url%/}/api/tags" >/dev/null; then
        fail "Ollama no es alcanzable en ${ollama_url}; no se descargaron modelos"
    fi
    command -v ollama >/dev/null 2>&1 ||
        fail "Ollama responde, pero el comando ollama no esta disponible"

    log "Descargando modelo de embeddings: ${embedding_model}"
    OLLAMA_HOST="${ollama_url}" ollama pull "${embedding_model}"
    if [[ "${extraction_model}" != "${embedding_model}" ]]; then
        log "Descargando modelo de extraccion: ${extraction_model}"
        OLLAMA_HOST="${ollama_url}" ollama pull "${extraction_model}"
    fi
}

read_os_release() {
    [[ -r /etc/os-release ]] || fail "no se puede leer /etc/os-release"

    # Los nombres de estas variables vienen definidos por os-release.
    # shellcheck disable=SC1091
    source /etc/os-release
    os_id="${ID:-}"
    os_id_like="${ID_LIKE:-}"
}

is_opensuse() {
    [[ "${os_id}" == opensuse* || " ${os_id_like} " == *" suse "* ]]
}

confirm_package_install() {
    local packages="$1"

    if [[ "${assume_yes}" == true ]]; then
        return
    fi
    if [[ ! -t 0 ]]; then
        fail "faltan paquetes (${packages}); repite con --assume-yes o ejecuta en una terminal"
    fi

    printf '[install] Se instalaran con zypper: %s. Continuar? [y/N] ' "${packages}"
    local answer=""
    read -r answer
    [[ "${answer}" == "y" || "${answer}" == "Y" ]] ||
        fail "instalacion cancelada por el usuario"
}

install_opensuse_packages() {
    (($# > 0)) || return
    is_opensuse ||
        fail "instalacion automatica no soportada para esta distribucion (ID=${os_id:-desconocido})"
    command -v zypper >/dev/null 2>&1 ||
        fail "openSUSE detectado, pero zypper no esta disponible"

    confirm_package_install "$*"

    local privilege_command=()
    if ((EUID != 0)); then
        command -v sudo >/dev/null 2>&1 ||
            fail "se necesita root o sudo para instalar paquetes con zypper"
        privilege_command=(sudo)
    fi

    log "Instalando paquetes openSUSE: $*"
    "${privilege_command[@]}" zypper --non-interactive install "$@"
}

ensure_python() {
    if command -v python3.13 >/dev/null 2>&1; then
        return
    fi

    install_opensuse_packages python313 python313-pip
    command -v python3.13 >/dev/null 2>&1 ||
        fail "python3.13 no quedo disponible despues de instalarlo"
}

docker_is_functional() {
    command -v docker >/dev/null 2>&1 &&
        docker info >/dev/null 2>&1 &&
        docker compose version >/dev/null 2>&1
}

podman_is_functional() {
    command -v podman >/dev/null 2>&1 &&
        podman info >/dev/null 2>&1
}

select_podman_compose() {
    if podman compose version >/dev/null 2>&1; then
        compose_command=(podman compose)
    elif command -v podman-compose >/dev/null 2>&1; then
        compose_command=(podman-compose)
    else
        return 1
    fi
}

select_container_runtime() {
    if docker_is_functional; then
        runtime="docker"
        compose_command=(docker compose)
        return
    fi

    if podman_is_functional && select_podman_compose; then
        runtime="podman"
        return
    fi

    log "No hay un runtime de contenedores funcional con soporte compose."
    install_opensuse_packages podman podman-compose

    podman_is_functional ||
        fail "podman se instalo, pero no responde; revisa su configuracion y permisos"
    select_podman_compose ||
        fail "podman esta disponible, pero falta podman compose o podman-compose"
    runtime="podman"
}

compose() {
    "${compose_command[@]}" -f "${compose_file}" "$@"
}

start_database() {
    log "Runtime seleccionado: ${runtime}"
    log "Levantando PostgreSQL+pgvector local."
    compose up -d postgres

    local deadline=$((SECONDS + db_wait_seconds))
    while ((SECONDS < deadline)); do
        if compose exec -T postgres \
            pg_isready -U ianest -d ianest_extended >/dev/null 2>&1; then
            log "PostgreSQL esta listo."
            return
        fi
        sleep 2
    done

    compose ps >&2 || true
    fail "PostgreSQL no estuvo listo en ${db_wait_seconds}s; revisa el estado anterior y ejecuta ${compose_command[*]} -f ${compose_file} logs postgres"
}

prepare_venv() {
    ensure_python

    if [[ ! -x "${script_dir}/.venv/bin/python" ]]; then
        log "Creando .venv con Python 3.13."
        python3.13 -m venv "${script_dir}/.venv"
    else
        log "Reutilizando .venv existente."
    fi

    local venv_version=""
    venv_version="$("${script_dir}/.venv/bin/python" -c \
        'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    [[ "${venv_version}" == "3.13" ]] ||
        fail ".venv usa Python ${venv_version}; elimina o renombra .venv y repite con Python 3.13"

    log "Instalando el paquete editable y dependencias de prueba."
    "${script_dir}/.venv/bin/python" -m pip install -e "${script_dir}[test]"
}

count_skips() {
    local summary=""
    summary="$(grep -Eo '[0-9]+ skipped' "${test_output}" | tail -n 1 || true)"
    if [[ -n "${summary}" ]]; then
        printf '%s\n' "${summary%% *}"
    else
        printf '0\n'
    fi
}

run_tests() {
    test_output="$(mktemp "${TMPDIR:-/tmp}/ianest-extended-pytest.XXXXXX")"
    trap 'rm -f -- "${test_output}"' EXIT

    if [[ "${skip_db}" == true ]]; then
        unset IANEST_EXTENDED_TEST_DSN
        log "IANEST_EXTENDED_TEST_DSN no definido (--skip-db)."
    else
        export IANEST_EXTENDED_TEST_DSN="${test_dsn}"
        export IANEST_EXTENDED_EMBEDDING_DIMENSION="${embedding_dimension}"
        log "IANEST_EXTENDED_TEST_DSN=${IANEST_EXTENDED_TEST_DSN}"
    fi

    log "Ejecutando pytest."
    set +e
    "${script_dir}/.venv/bin/python" -m pytest 2>&1 | tee "${test_output}"
    local pytest_status=${PIPESTATUS[0]}
    set -e

    local skipped=""
    skipped="$(count_skips)"
    if ((pytest_status != 0)); then
        fail "pytest termino en rojo (codigo ${pytest_status}, ${skipped} skips)"
    fi
    if [[ "${skip_db}" == false && "${skipped}" != "0" ]]; then
        fail "pytest termino en verde, pero hubo ${skipped} skips con la DB habilitada"
    fi

    if [[ "${skip_db}" == true ]]; then
        log "Resultado VERDE: pytest completo con ${skipped} skips esperados de PostgreSQL (--skip-db)."
        log "Las razones de skip aparecen en el resumen de pytest anterior."
    else
        log "Resultado VERDE: pytest completo sin skips."
    fi
}

main() {
    while (($# > 0)); do
        case "$1" in
            --assume-yes)
                assume_yes=true
                ;;
            --skip-db)
                skip_db=true
                ;;
            --skip-tests)
                skip_tests=true
                ;;
            --core-url)
                require_option_value "$1" "${2:-}"
                core_url="$2"
                core_url_set=true
                shift
                ;;
            --ollama-url)
                require_option_value "$1" "${2:-}"
                ollama_url="$2"
                ollama_url_set=true
                shift
                ;;
            --embedding-model)
                require_option_value "$1" "${2:-}"
                embedding_model="$2"
                embedding_model_set=true
                shift
                ;;
            --embedding-dimension)
                require_option_value "$1" "${2:-}"
                embedding_dimension="$2"
                embedding_dimension_set=true
                shift
                ;;
            --extraction-model)
                require_option_value "$1" "${2:-}"
                extraction_model="$2"
                extraction_model_set=true
                shift
                ;;
            --pull-models)
                pull_models=true
                ;;
            --help)
                usage
                exit 0
                ;;
            *)
                usage >&2
                fail "opcion desconocida: $1"
                ;;
        esac
        shift
    done

    cd -- "${script_dir}"
    configure_extended
    write_extended_env
    pull_configured_models
    read_os_release

    if [[ "${skip_db}" == false ]]; then
        select_container_runtime
        start_database
    else
        log "DB omitida por --skip-db."
    fi

    prepare_venv

    if [[ "${skip_tests}" == true ]]; then
        log "Pruebas omitidas por --skip-tests."
        log "Resultado VERDE: entorno preparado; pytest no se ejecuto."
    else
        run_tests
    fi
}

main "$@"
