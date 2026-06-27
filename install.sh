#!/usr/bin/env bash
# =============================================================================
#  song-dl — Installer Script
#  Downloads songs with rich metadata. This script sets up everything needed:
#  system dependencies, Python virtual environment, and command launcher.
# =============================================================================
set -euo pipefail

# =============================================================================
#  CONSTANTS
# =============================================================================
SONGDL_VERSION="0.2.1"

# Log file for install operations
LOGFILE=$(mktemp /tmp/songdl_install.XXXXXX) 2>/dev/null || LOGFILE="/tmp/songdl_install.log"

# Detect project root (where this install script lives)
# Supports both local install (./install.sh) and curl-piped install (curl ... | bash)
PROJECT_DIR=""
_guess_project_dir() {
    # Try local directory first (./install.sh from repo)
    local self
    self="$(readlink -f "$0" 2>/dev/null)" || self=""
    if [[ -n "$self" && -f "$(dirname "$self")/main.py" ]]; then
        PROJECT_DIR="$(cd "$(dirname "$self")" && pwd)"
        return 0
    fi
    # Fallback: check if we're already in the project dir
    if [[ -f "$PWD/main.py" && -d "$PWD/songdl" ]]; then
        PROJECT_DIR="$PWD"
        return 0
    fi
    # Last resort: download from GitHub
    local tarball_url="https://github.com/Kelvris/song-dl/archive/refs/tags/v${SONGDL_VERSION}.tar.gz"
    local extract_dir="$SONGDL_DATA_DIR/src"
    mkdir -p "$extract_dir"
    info "Downloading song-dl v${SONGDL_VERSION} from GitHub..."
    if command -v curl &>/dev/null; then
        curl -fsSL "$tarball_url" | tar -xz -C "$extract_dir" --strip-components=1 2>/dev/null
    elif command -v wget &>/dev/null; then
        wget -qO- "$tarball_url" | tar -xz -C "$extract_dir" --strip-components=1 2>/dev/null
    else
        die "Neither curl nor wget found. Please install curl or wget."
    fi
    if [[ -f "$extract_dir/main.py" ]]; then
        PROJECT_DIR="$extract_dir"
        _FILES_COPIED=true  # already in the data dir, no need to copy later
        return 0
    fi
    die "Failed to download song-dl source. Please check your internet connection."
}
_guess_project_dir

# XDG-compliant installation paths
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"

SONGDL_DATA_DIR="$XDG_DATA_HOME/song-dl"
VENV_DIR="$SONGDL_DATA_DIR/venv"
LAUNCHER_PATH="$XDG_BIN_HOME/song-dl"

# Minimum Python version required
PYTHON_REQUIRED_MAJOR=3
PYTHON_REQUIRED_MINOR=8

# State tracking for cleanup
_INSTALL_STARTED=false
_VENV_CREATED=false
_FILES_COPIED=false
_LAUNCHER_CREATED=false

# =============================================================================
#  COLOR / OUTPUT HELPERS  (tput with fallback)
# =============================================================================
if [[ -t 1 ]] && command -v tput &>/dev/null; then
    _BOLD=$(tput bold)
    _DIM=$(tput dim)
    _UNDERLINE=$(tput smul)
    _RESET=$(tput sgr0)

    # Foreground colors
    _RED=$(tput setaf 1)
    _GREEN=$(tput setaf 2)
    _YELLOW=$(tput setaf 3)
    _BLUE=$(tput setaf 4)
    _MAGENTA=$(tput setaf 5)
    _CYAN=$(tput setaf 6)
    _WHITE=$(tput setaf 7)
else
    _BOLD='' _DIM='' _UNDERLINE='' _RESET=''
    _RED='' _GREEN='' _YELLOW='' _BLUE='' _MAGENTA='' _CYAN='' _WHITE=''
fi

# ----- Print helpers ---------------------------------------------------------
info()  { printf "  %s•%s %s%s\n" "$_BLUE" "$_RESET" "$*" "$_RESET"; }
ok()    { printf "  %s✓%s %s%s\n" "$_GREEN" "$_RESET" "$*" "$_RESET"; }
warn()  { printf "  %s⚠ %s%s%s\n" "$_YELLOW" "$_RESET" "$*" "$_RESET"; }
error() { printf "  %s✗ %s%s%s\n" "$_RED" "$_RESET" "$*" "$_RESET" >&2; }
die()   { error "$*"; exit 1; }

# ----- Section header --------------------------------------------------------
section() {
    local title="$1"
    local len
    len=$((${#title} + 4))
    local pad=2
    local inner=$((len + pad * 2))

    printf "\n  %s╔" "$_CYAN"
    printf '═%.0s' $(seq 1 "$inner")
    printf "╗%s\n" "$_RESET"

    printf "  %s║%s  %s%-*s  %s║%s\n" "$_CYAN" "$_RESET" "$_BOLD" "$len" "$title" "$_CYAN" "$_RESET"

    printf "  %s╚" "$_CYAN"
    printf '═%.0s' $(seq 1 "$inner")
    printf "╝%s\n" "$_RESET"
}

# ----- Sub-header (smaller) --------------------------------------------------
subheader() {
    local title="$1"
    printf "  %s── %s%s\n" "$_CYAN" "$title" "$_RESET"
}

# =============================================================================
#  BANNER
# =============================================================================
print_banner() {
    printf "\n"
    printf "  %s╔══════════════════════════════════════════════════╗%s\n" "$_CYAN" "$_RESET"
    printf "  %s║%s              %s♪  song-dl  Installer  ♪%s            %s║%s\n" \
        "$_CYAN" "$_RESET" "$_BOLD$_BLUE" "$_RESET" "$_CYAN" "$_RESET"
    printf "  %s║%s         %sDownload songs with rich metadata%s         %s║%s\n" \
        "$_CYAN" "$_RESET" "$_DIM" "$_RESET" "$_CYAN" "$_RESET"
    printf "  %s║%s                  %sv%s%s                   %s║%s\n" \
        "$_CYAN" "$_RESET" "$_DIM" "$SONGDL_VERSION" "$_RESET" "$_CYAN" "$_RESET"
    printf "  %s╚══════════════════════════════════════════════════╝%s\n" "$_CYAN" "$_RESET"
    printf "\n"
}

# =============================================================================
#  TRAP / CLEANUP
# =============================================================================
cleanup() {
    trap - EXIT INT TERM
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        printf "\n"
        warn "Installation interrupted or failed (exit code: $exit_code)."
        if $_INSTALL_STARTED; then
            info "Cleaning up partial installation ..."
            if $_VENV_CREATED && [[ -d "$VENV_DIR" ]]; then
                rm -rf "$VENV_DIR" 2>/dev/null || true
                ok "Removed partial venv."
            fi
            if $_FILES_COPIED && [[ -d "$SONGDL_DATA_DIR" ]]; then
                # Only remove copied files, not config
                rm -f "$SONGDL_DATA_DIR/main.py" 2>/dev/null || true
                rm -rf "$SONGDL_DATA_DIR/songdl" 2>/dev/null || true
                ok "Removed copied source files."
            fi
            if $_LAUNCHER_CREATED && [[ -f "$LAUNCHER_PATH" ]]; then
                rm -f "$LAUNCHER_PATH" 2>/dev/null || true
                ok "Removed launcher."
            fi
            info "Cleanup done. You can safely re-run the installer."
        fi
    fi
    [[ -f "$LOGFILE" ]] && rm -f "$LOGFILE"
    exit "$exit_code"
}

trap cleanup EXIT INT TERM

# =============================================================================
#  OS DETECTION
# =============================================================================
detect_os() {
    OS_NAME="unknown"
    PKG_MANAGER=""
    PKG_INSTALL_CMD=""
    SUDO_CMD=""

    # Determine sudo availability
    if [[ $EUID -eq 0 ]]; then
        SUDO_CMD=""
    elif command -v sudo &>/dev/null; then
        SUDO_CMD="sudo"
    else
        SUDO_CMD=""
    fi

    local os_type
    os_type="$(uname -s)"

    case "$os_type" in
        Darwin)
            if command -v brew &>/dev/null; then
                OS_NAME="macOS"
                PKG_MANAGER="brew"
                PKG_INSTALL_CMD="brew install"
            else
                die "Homebrew is not installed. Install it first: https://brew.sh"
            fi
            ;;
        Linux)
            if [[ -f /etc/debian_version ]]; then
                OS_NAME="Linux (Debian/Ubuntu)"
                PKG_MANAGER="apt"
                PKG_INSTALL_CMD="apt install -y"
            elif [[ -f /etc/redhat-release ]]; then
                OS_NAME="Linux (Fedora/RHEL)"
                if command -v dnf &>/dev/null; then
                    PKG_MANAGER="dnf"
                    PKG_INSTALL_CMD="dnf install -y"
                else
                    PKG_MANAGER="yum"
                    PKG_INSTALL_CMD="yum install -y"
                fi
            elif [[ -f /etc/arch-release ]]; then
                OS_NAME="Linux (Arch Linux)"
                PKG_MANAGER="pacman"
                PKG_INSTALL_CMD="pacman -S --noconfirm"
            elif [[ -f /etc/SuSE-release ]] || [[ -f /etc/SUSE-release ]]; then
                OS_NAME="Linux (openSUSE)"
                PKG_MANAGER="zypper"
                PKG_INSTALL_CMD="zypper install -y"
            elif [[ -f /etc/alpine-release ]]; then
                OS_NAME="Linux (Alpine)"
                PKG_MANAGER="apk"
                PKG_INSTALL_CMD="apk add"
            elif [[ -f /etc/void-release ]]; then
                OS_NAME="Linux (Void Linux)"
                PKG_MANAGER="xbps"
                PKG_INSTALL_CMD="xbps-install -y"
            else
                # Fallback: try to detect by available package manager
                if command -v apt-get &>/dev/null; then
                    OS_NAME="Linux (Debian/Ubuntu)"
                    PKG_MANAGER="apt"
                    PKG_INSTALL_CMD="apt install -y"
                elif command -v dnf &>/dev/null; then
                    OS_NAME="Linux (Fedora/RHEL)"
                    PKG_MANAGER="dnf"
                    PKG_INSTALL_CMD="dnf install -y"
                elif command -v pacman &>/dev/null; then
                    OS_NAME="Linux (Arch Linux)"
                    PKG_MANAGER="pacman"
                    PKG_INSTALL_CMD="pacman -S --noconfirm"
                elif command -v zypper &>/dev/null; then
                    OS_NAME="Linux (openSUSE)"
                    PKG_MANAGER="zypper"
                    PKG_INSTALL_CMD="zypper install -y"
                elif command -v apk &>/dev/null; then
                    OS_NAME="Linux (Alpine)"
                    PKG_MANAGER="apk"
                    PKG_INSTALL_CMD="apk add"
                elif command -v xbps-install &>/dev/null; then
                    OS_NAME="Linux (Void Linux)"
                    PKG_MANAGER="xbps"
                    PKG_INSTALL_CMD="xbps-install -y"
                else
                    die "Unsupported Linux distribution. Please install dependencies manually:\n" \
                        "  - Python 3.8+, python3-pip, python3-venv, ffmpeg"
                fi
            fi
            ;;
        MINGW*|MSYS*|CYGWIN*)
            OS_NAME="Windows"
            if command -v winget &>/dev/null; then
                PKG_MANAGER="winget"
                PKG_INSTALL_CMD="winget install"
            elif command -v choco &>/dev/null; then
                PKG_MANAGER="choco"
                PKG_INSTALL_CMD="choco install -y"
            else
                die "No supported package manager found (winget or choco). Please install dependencies manually."
            fi
            SUDO_CMD=""
            ;;
        *)
            die "Unsupported operating system: $os_type"
            ;;
    esac

    # If running as root, no sudo needed
    if [[ $EUID -eq 0 ]]; then
        SUDO_CMD=""
    fi

    # Validate sudo works (if needed)
    if [[ -n "$SUDO_CMD" ]]; then
        if ! command -v sudo &>/dev/null; then
            warn "sudo is not available. Some system packages may fail to install."
            SUDO_CMD=""
        fi
    fi
}

# =============================================================================
#  SYSTEM PACKAGE NAMES BY DISTRO
# =============================================================================
_pkg_name_for() {
    local generic_name="$1"
    case "$PKG_MANAGER" in
        apt)
            case "$generic_name" in
                python3)    echo "python3" ;;
                pip)        echo "python3-pip" ;;
                venv)       echo "python3-venv" ;;
                ffmpeg)     echo "ffmpeg" ;;
                *)          echo "$generic_name" ;;
            esac
            ;;
        dnf|yum)
            case "$generic_name" in
                python3)    echo "python3" ;;
                pip)        echo "python3-pip" ;;
                venv)       echo "python3-virtualenv" ;;
                ffmpeg)     echo "ffmpeg" ;;
                *)          echo "$generic_name" ;;
            esac
            ;;
        pacman)
            case "$generic_name" in
                python3)    echo "python" ;;
                pip)        echo "python-pip" ;;
                venv)       echo "python-virtualenv" ;;
                ffmpeg)     echo "ffmpeg" ;;
                *)          echo "$generic_name" ;;
            esac
            ;;
        zypper)
            case "$generic_name" in
                python3)    echo "python3" ;;
                pip)        echo "python3-pip" ;;
                venv)       echo "python3-virtualenv" ;;
                ffmpeg)     echo "ffmpeg" ;;
                *)          echo "$generic_name" ;;
            esac
            ;;
        apk)
            case "$generic_name" in
                python3)    echo "python3" ;;
                pip)        echo "py3-pip" ;;
                venv)       echo "py3-virtualenv" ;;
                ffmpeg)     echo "ffmpeg" ;;
                *)          echo "$generic_name" ;;
            esac
            ;;
        xbps)
            case "$generic_name" in
                python3)    echo "python3" ;;
                pip)        echo "python3-pip" ;;
                venv)       echo "python3-virtualenv" ;;
                ffmpeg)     echo "ffmpeg" ;;
                *)          echo "$generic_name" ;;
            esac
            ;;
        brew)
            case "$generic_name" in
                python3)    echo "python@3" ;;
                pip)        echo "" ;;  # pip comes with python@3 on brew
                venv)       echo "" ;;  # venv comes with python@3 on brew
                ffmpeg)     echo "ffmpeg" ;;
                *)          echo "$generic_name" ;;
            esac
            ;;
        winget|choco)
            case "$generic_name" in
                python3)    echo "Python.Python.3" ;;
                pip)        echo "" ;;
                venv)       echo "" ;;
                ffmpeg)     echo "FFmpeg" ;;
                *)          echo "$generic_name" ;;
            esac
            ;;
        *)
            echo "$generic_name"
            ;;
    esac
}

# =============================================================================
#  CHECK DEPENDENCIES
# =============================================================================
check_deps() {
    local -a dep_names=(
        "python3:Python 3.8+"
        "pip:pip (python3-pip)"
        "venv:python3-venv"
        "ffmpeg:ffmpeg"
        "jsruntime:JS Runtime (Deno/Node)"
    )

    local -a dep_status=()        # "ok" | "missing"
    local -a dep_version=()       # version string or "NOT FOUND"

    declare -g PYTHON_CMD=""
    declare -g PIP_CMD=""
    declare -g _JS_RUNTIME=""

    for entry in "${dep_names[@]}"; do
        local key="${entry%%:*}"
        local label="${entry#*:}"

        case "$key" in
            python3)
                if command -v python3 &>/dev/null; then
                    local py_ver
                    py_ver="$(python3 --version 2>/dev/null | awk '{print $2}')" || py_ver=""
                    if [[ -n "$py_ver" ]]; then
                        local pymajor pyminor
                        pymajor="${py_ver%%.*}"
                        pyminor="${py_ver#*.}"
                        pyminor="${pyminor%%.*}"
                        pyminor="${pyminor%%[!0-9]*}"
                        if [[ "$pymajor" -gt "$PYTHON_REQUIRED_MAJOR" ]] || \
                           [[ "$pymajor" -eq "$PYTHON_REQUIRED_MAJOR" && "$pyminor" -ge "$PYTHON_REQUIRED_MINOR" ]]; then
                            dep_status+=("ok")
                            dep_version+=("$py_ver")
                            PYTHON_CMD="python3"
                        else
                            dep_status+=("missing")
                            dep_version+=("$py_ver (need 3.8+)")
                        fi
                    else
                        dep_status+=("missing")
                        dep_version+=("ERROR")
                    fi
                else
                    dep_status+=("missing")
                    dep_version+=("NOT FOUND")
                fi
                ;;
            pip)
                if [[ -n "$PYTHON_CMD" ]]; then
                    if "$PYTHON_CMD" -m pip --version &>/dev/null; then
                        local pip_ver
                        pip_ver="$("$PYTHON_CMD" -m pip --version 2>/dev/null | awk '{print $2}')" || pip_ver=""
                        dep_status+=("ok")
                        dep_version+=("${pip_ver:-available}")
                        PIP_CMD="$PYTHON_CMD -m pip"
                    else
                        dep_status+=("missing")
                        dep_version+=("NOT FOUND")
                    fi
                else
                    dep_status+=("missing")
                    dep_version+=("(no python3)")
                fi
                ;;
            venv)
                if [[ -n "$PYTHON_CMD" ]]; then
                    if "$PYTHON_CMD" -c "import venv" &>/dev/null; then
                        dep_status+=("ok")
                        dep_version+=("available")
                    else
                        dep_status+=("missing")
                        dep_version+=("NOT FOUND")
                    fi
                else
                    dep_status+=("missing")
                    dep_version+=("(no python3)")
                fi
                ;;
            ffmpeg)
                if command -v ffmpeg &>/dev/null; then
                    local ff_ver
                    ff_ver="$(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}')" || ff_ver=""
                    dep_status+=("ok")
                    dep_version+=("${ff_ver:-available}")
                else
                    dep_status+=("missing")
                    dep_version+=("NOT FOUND")
                fi
                ;;
            jsruntime)
                if command -v deno &>/dev/null; then
                    local deno_ver
                    deno_ver="$(deno --version 2>/dev/null | head -1 | awk '{print $2}')" || deno_ver=""
                    dep_status+=("ok")
                    dep_version+=("deno ${deno_ver:-available}")
                    _JS_RUNTIME="deno"
                elif command -v node &>/dev/null; then
                    local node_ver
                    node_ver="$(node --version 2>/dev/null)" || node_ver=""
                    dep_status+=("ok")
                    dep_version+=("node ${node_ver:-available}")
                    _JS_RUNTIME="node"
                else
                    dep_status+=("missing")
                    dep_version+=("NOT FOUND")
                    _JS_RUNTIME=""
                fi
                ;;
        esac
    done

    # ----- Print table -------------------------------------------------------
    printf "\n"
    printf "  %s╔══════════════════════════════════════════════════╗%s\n" "$_CYAN" "$_RESET"
    printf "  %s║%s          System Requirements Check              %s║%s\n" "$_CYAN" "$_RESET" "$_CYAN" "$_RESET"
    printf "  %s╠══════════════════════════════════════════════════╣%s\n" "$_CYAN" "$_RESET"
    printf "  %s║%s  %-22s %-9s %-14s %s║%s\n" "$_CYAN" "$_RESET" \
        "Dependency" "Status" "Version" "$_CYAN" "$_RESET"
    printf "  %s║%s  ────────────────────────────────────────────  %s║%s\n" "$_CYAN" "$_RESET" "$_CYAN" "$_RESET"

    local all_ok=true
    for i in "${!dep_names[@]}"; do
        local entry="${dep_names[$i]}"
        local label="${entry#*:}"
        local st="${dep_status[$i]}"
        local ver="${dep_version[$i]}"

        local status_display ver_display
        if [[ "$st" == "ok" ]]; then
            status_display="${_GREEN}✓${_RESET}"
            ver_display="${ver}"
        else
            status_display="${_RED}✗${_RESET}"
            ver_display="${_RED}${ver}${_RESET}"
            all_ok=false
        fi

        printf "  %s║%s  %-22s %-9b %-14b %s║%s\n" "$_CYAN" "$_RESET" \
            "$label" "$status_display" "$ver_display" "$_CYAN" "$_RESET"
    done

    printf "  %s╚══════════════════════════════════════════════════╝%s\n" "$_CYAN" "$_RESET"
    printf "\n"

    if $all_ok; then
        ok "All system dependencies are satisfied."
    else
        warn "Some dependencies are missing and will be installed."
    fi

    # Return success/failure for individual items via global flags
    # These are used later to decide what to install
    declare -g NEED_PIP=false NEED_VENV=false NEED_FFMPEG=false
    for i in "${!dep_names[@]}"; do
        local entry="${dep_names[$i]}"
        local key="${entry%%:*}"
        local st="${dep_status[$i]}"
        if [[ "$st" != "ok" ]]; then
            case "$key" in
                pip)   NEED_PIP=true   ;;
                venv)  NEED_VENV=true  ;;
                ffmpeg) NEED_FFMPEG=true ;;
            esac
        fi
    done

    # Return overall status via exit code simulation — we just use a global
    declare -g ALL_DEPS_OK=$all_ok
}

# =============================================================================
#  CONFIRMATION PROMPT
# =============================================================================
confirm_installation() {
    printf "\n"
    printf "  %s╔══════════════════════════════════════════════════╗%s\n" "$_BLUE" "$_RESET"
    printf "  %s║%s         Installation Plan                       %s║%s\n" "$_BLUE" "$_RESET" "$_BLUE" "$_RESET"
    printf "  %s╠══════════════════════════════════════════════════╣%s\n" "$_BLUE" "$_RESET"

    local plan_items=()
    plan_items+=("~/.local/share/song-dl/venv/    (Python virtual environment)")
    if $NEED_FFMPEG; then
        plan_items+=("ffmpeg                            (system package via ${PKG_MANAGER})")
    fi
    plan_items+=("yt-dlp + mutagen                 (Python packages, inside venv)")
    plan_items+=("~/.local/bin/song-dl             (command launcher)")

    for item in "${plan_items[@]}"; do
        printf "  %s║%s    • %-45s  %s║%s\n" "$_BLUE" "$_RESET" "$item" "$_BLUE" "$_RESET"
    done
    printf "  %s╚══════════════════════════════════════════════════╝%s\n" "$_BLUE" "$_RESET"
    printf "\n"

    if $ALL_DEPS_OK; then
        # All good, but still ask about reinstall/upgrade
        if [[ -d "$VENV_DIR" ]]; then
            printf "  %sDetected existing installation at:%s %s\n" "$_YELLOW" "$_RESET" "$SONGDL_DATA_DIR"
            read -r -p "  $(printf "%s" "Reinstall / upgrade? [Y/n] > ")" REPLY || true
        else
            read -r -p "  $(printf "%s" "Proceed with installation? [Y/n] > ")" REPLY || true
        fi
    else
        read -r -p "  $(printf "%s" "Proceed with installation? [Y/n] > ")" REPLY || true
    fi

    REPLY="${REPLY:-Y}"
    case "${REPLY:0:1}" in
        y|Y) return 0 ;;
        *)   info "Installation cancelled."; exit 0 ;;
    esac
}

# =============================================================================
#  INSTALL SYSTEM PACKAGE
# =============================================================================
install_system_pkg() {
    local generic_name="$1"
    local display_name="${2:-$generic_name}"
    local pkg
    pkg="$(_pkg_name_for "$generic_name")"

    if [[ -z "$pkg" ]]; then
        # Package not needed for this distro (e.g., pip/venv come bundled on macOS)
        ok "$display_name is already available (bundled with Python)."
        return 0
    fi

    info "Installing $display_name ($pkg) via $PKG_MANAGER ..."

    # Check if already installed
    case "$PKG_MANAGER" in
        apt)
            if dpkg -s "$pkg" &>/dev/null 2>&1; then
                ok "$display_name is already installed."
                return 0
            fi
            ;;
        dnf|yum)
            if rpm -q "$pkg" &>/dev/null 2>&1; then
                ok "$display_name is already installed."
                return 0
            fi
            ;;
        pacman)
            if pacman -Qi "$pkg" &>/dev/null 2>&1; then
                ok "$display_name is already installed."
                return 0
            fi
            ;;
        zypper)
            if rpm -q "$pkg" &>/dev/null 2>&1; then
                ok "$display_name is already installed."
                return 0
            fi
            ;;
        apk)
            if apk info -e "$pkg" &>/dev/null 2>&1; then
                ok "$display_name is already installed."
                return 0
            fi
            ;;
        xbps)
            if xbps-query -l "$pkg" &>/dev/null 2>&1; then
                ok "$display_name is already installed."
                return 0
            fi
            ;;
        brew)
            if brew list --formula "$pkg" &>/dev/null 2>&1; then
                ok "$display_name is already installed."
                return 0
            fi
            ;;
    esac

    # Run the install command
    local cmd="$SUDO_CMD $PKG_INSTALL_CMD $pkg"
    if [[ -z "$SUDO_CMD" ]]; then
        cmd="$PKG_INSTALL_CMD $pkg"
    fi

    # Update package cache first for apt
    if [[ "$PKG_MANAGER" == "apt" ]] && [[ -n "$SUDO_CMD" ]]; then
        printf "  %s  Updating package cache ..." "$_DIM"
        $SUDO_CMD apt update -qq 2>/dev/null || true
        printf "\r"
    fi

    # Show a spinner while installing
    printf "  %s  Installing %s ..." "$_DIM" "$display_name"
    if $cmd &>"$LOGFILE"; then
        printf "\r"
        ok "$display_name installed successfully."
    else
        printf "\r"
        error "Failed to install $display_name."
        error "Command was: $cmd"
        error "Check $LOGFILE for details."
        die "Aborting installation due to system package failure."
    fi
}

# =============================================================================
#  INSTALL PYTHON DEPENDENCIES (venv + pip)
# =============================================================================
install_python_deps() {
    subheader "Setting up Python virtual environment"

    # Create data directory
    mkdir -p "$SONGDL_DATA_DIR"

    # Create venv if not exists (or recreate)
    if [[ -d "$VENV_DIR" ]]; then
        info "Removing existing virtual environment ..."
        rm -rf "$VENV_DIR"
    fi

    printf "  %s  Creating venv at %s ..." "$_DIM" "$VENV_DIR"
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    printf "\r"
    _VENV_CREATED=true
    ok "Virtual environment created."

    # Upgrade pip
    printf "  %s  Upgrading pip ..." "$_DIM"
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip 2>/tmp/songdl_pip_upgrade.log
    printf "\r"
    ok "pip upgraded."

    # Copy project source files into the data dir (so user can delete original source)
    # Skip if already downloaded directly to the data dir (curl | bash mode)
    if ! $_FILES_COPIED; then
        info "Copying project files to $SONGDL_DATA_DIR ..."
        cp "$PROJECT_DIR/main.py" "$SONGDL_DATA_DIR/"
        cp -r "$PROJECT_DIR/songdl" "$SONGDL_DATA_DIR/"
        _FILES_COPIED=true
        ok "Project files copied."
    fi

    # Install requirements with spinner
    subheader "Installing Python packages (yt-dlp, mutagen)"

    if [[ ! -f "$PROJECT_DIR/requirements.txt" ]]; then
        die "requirements.txt not found at $PROJECT_DIR/requirements.txt"
    fi

    # Check internet connectivity (lightweight check)
    if ! _check_internet; then
        warn "No internet connection detected."
        warn "pip install may fail if packages are not cached."
    fi

    printf "  %s  Installing yt-dlp and mutagen ..." "$_DIM"
    if "$VENV_DIR/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt" \
        &>/tmp/songdl_pip_install.log; then
        printf "\r"
        ok "Python packages installed."
    else
        printf "\r"
        error "pip install failed. Check /tmp/songdl_pip_install.log for details."
        die "Aborting installation due to pip failure."
    fi
}

# ----- Internet check helper -------------------------------------------------
_check_internet() {
    if command -v curl &>/dev/null; then
        curl -s --connect-timeout 3 https://pypi.org >/dev/null 2>&1 && return 0
    fi
    if command -v wget &>/dev/null; then
        wget -q --timeout=3 --spider https://pypi.org >/dev/null 2>&1 && return 0
    fi
    if command -v ping &>/dev/null; then
        ping -c 1 -W 2 pypi.org >/dev/null 2>&1 && return 0
    fi
    return 1
}

# =============================================================================
#  SETUP LAUNCHER
# =============================================================================
setup_launcher() {
    subheader "Installing command launcher"

    mkdir -p "$XDG_BIN_HOME"

    cat > "$LAUNCHER_PATH" <<- LAUNCHER_EOF
	#!/usr/bin/env bash
	# song-dl launcher — generated by install.sh
	exec "$VENV_DIR/bin/python" "$SONGDL_DATA_DIR/main.py" "\$@"
	LAUNCHER_EOF

    chmod +x "$LAUNCHER_PATH"
    _LAUNCHER_CREATED=true
    ok "Launcher created at $LAUNCHER_PATH"

    # Check PATH
    if [[ ":$PATH:" != *":$XDG_BIN_HOME:"* ]]; then
        printf "\n"
        warn "$XDG_BIN_HOME is not in your PATH."
        printf "\n"
        printf "  %s╔══════════════════════════════════════════════════════════════╗%s\n" "$_YELLOW" "$_RESET"
        printf "  %s║%s  Add it to your shell configuration:                       %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s║%s                                                        %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s║%s    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc  %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s║%s    source ~/.bashrc                                     %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s║%s                                                        %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s║%s  Or for bash, simply run:                                %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s║%s    source <(grep 'export PATH.*local/bin' ~/.bashrc 2>/dev/null) || true  %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s╚══════════════════════════════════════════════════════════════╝%s\n" "$_YELLOW" "$_RESET"
        printf "\n"
    fi
}

# =============================================================================
#  FFMPEG NOT FOUND GUIDE
# =============================================================================
show_ffmpeg_guide() {
    if ! command -v ffmpeg &>/dev/null; then
        printf "\n"
        printf "  %s╔══════════════════════════════════════════════════╗%s\n" "$_YELLOW" "$_RESET"
        printf "  %s║%s        ffmpeg is still missing                   %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s╠══════════════════════════════════════════════════╣%s\n" "$_YELLOW" "$_RESET"
        printf "  %s║%s                                                  %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s║%s  song-dl needs ffmpeg to process audio.         %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s║%s  Install it manually via your package manager:   %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        case "$PKG_MANAGER" in
            apt)   printf "  %s║%s    sudo apt install ffmpeg                           %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET" ;;
            dnf)   printf "  %s║%s    sudo dnf install ffmpeg                           %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET" ;;
            pacman) printf "  %s║%s    sudo pacman -S ffmpeg                             %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET" ;;
            zypper) printf "  %s║%s    sudo zypper install ffmpeg                        %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET" ;;
            apk)   printf "  %s║%s    apk add ffmpeg                                    %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET" ;;
            brew)  printf "  %s║%s    brew install ffmpeg                                %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET" ;;
            winget) printf "  %s║%s    winget install FFmpeg                             %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET" ;;
            choco) printf "  %s║%s    choco install ffmpeg                               %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET" ;;
            *)     printf "  %s║%s    Install ffmpeg using your system package manager. %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET" ;;
        esac
        printf "  %s║%s                                                  %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s║%s  Then re-run this installer to complete setup.    %s║%s\n" "$_YELLOW" "$_RESET" "$_YELLOW" "$_RESET"
        printf "  %s╚══════════════════════════════════════════════════╝%s\n" "$_YELLOW" "$_RESET"
        printf "\n"
    fi
}

# =============================================================================
#  SHOW SUCCESS
# =============================================================================
show_success() {
    printf "\n"
    printf "  %s╔══════════════════════════════════════════════════╗%s\n" "$_GREEN" "$_RESET"
    printf "  %s║%s        %s✓  Installation Complete!%s              %s║%s\n" "$_GREEN" "$_RESET" "$_BOLD" "$_RESET" "$_GREEN" "$_RESET"
    printf "  %s╠══════════════════════════════════════════════════╣%s\n" "$_GREEN" "$_RESET"
    printf "  %s║%s                                                  %s║%s\n" "$_GREEN" "$_RESET" "$_GREEN" "$_RESET"
    printf "  %s║%s    Run:  %ssong-dl%s                                %s║%s\n" "$_GREEN" "$_RESET" "$_BOLD$_WHITE" "$_RESET" "$_GREEN" "$_RESET"
    printf "  %s║%s                                                  %s║%s\n" "$_GREEN" "$_RESET" "$_GREEN" "$_RESET"

    if command -v ffmpeg &>/dev/null; then
        printf "  %s║%s    %sPro tip:%s Configure defaults via the app menu     %s║%s\n" "$_GREEN" "$_RESET" "$_DIM" "$_RESET" "$_GREEN" "$_RESET"
        printf "  %s║%s    or edit %s~/.config/song-dl/%s          %s║%s\n" "$_GREEN" "$_RESET" "$_DIM" "$_RESET" "$_GREEN" "$_RESET"
    else
        printf "  %s║%s    %sNote:%s ffmpeg was not installed. song-dl will    %s║%s\n" "$_GREEN" "$_RESET" "$_YELLOW" "$_RESET" "$_GREEN" "$_RESET"
        printf "  %s║%s    not be able to process audio without it.          %s║%s\n" "$_GREEN" "$_RESET" "$_GREEN" "$_RESET"
        printf "  %s║%s    Run the installer again after installing ffmpeg.  %s║%s\n" "$_GREEN" "$_RESET" "$_GREEN" "$_RESET"
    fi
    printf "  %s║%s                                                  %s║%s\n" "$_GREEN" "$_RESET" "$_GREEN" "$_RESET"
    printf "  %s╚══════════════════════════════════════════════════╝%s\n" "$_GREEN" "$_RESET"
    printf "\n"
}

# =============================================================================
#  UNINSTALL
# =============================================================================
uninstall() {
    printf "\n"
    section "Uninstall song-dl"

    local remove_venv=false
    local remove_config=false
    local remove_launcher=false

    # Check what exists
    local has_venv=false
    local has_config=false
    local has_launcher=false

    [[ -d "$VENV_DIR" ]] && has_venv=true
    [[ -d "$XDG_CONFIG_HOME/song-dl" ]] && has_config=true
    [[ -f "$LAUNCHER_PATH" ]] && has_launcher=true

    if ! $has_venv && ! $has_config && ! $has_launcher; then
        info "No song-dl installation found."
        exit 0
    fi

    if $has_venv; then
        read -r -p "  $(printf "%s" "Remove virtual environment? [Y/n] > ")" REPLY || true
        REPLY="${REPLY:-Y}"
        [[ "${REPLY:0:1}" =~ [Yy] ]] && remove_venv=true
    fi

    if $has_config; then
        read -r -p "  $(printf "%s" "Remove configuration files? [y/N] > ")" REPLY || true
        REPLY="${REPLY:-N}"
        [[ "${REPLY:0:1}" =~ [Yy] ]] && remove_config=true
    fi

    if $has_launcher; then
        read -r -p "  $(printf "%s" "Remove launcher? [Y/n] > ")" REPLY || true
        REPLY="${REPLY:-Y}"
        [[ "${REPLY:0:1}" =~ [Yy] ]] && remove_launcher=true
    fi

    printf "\n"

    if $remove_venv; then
        printf "  %s  Removing venv ..." "$_DIM"
        rm -rf "$SONGDL_DATA_DIR" 2>/dev/null || true
        printf "\r"
        ok "Removed $SONGDL_DATA_DIR"
    fi

    if $remove_config; then
        printf "  %s  Removing config ..." "$_DIM"
        rm -rf "$XDG_CONFIG_HOME/song-dl" 2>/dev/null || true
        printf "\r"
        ok "Removed $XDG_CONFIG_HOME/song-dl"
    fi

    if $remove_launcher; then
        printf "  %s  Removing launcher ..." "$_DIM"
        rm -f "$LAUNCHER_PATH" 2>/dev/null || true
        printf "\r"
        ok "Removed $LAUNCHER_PATH"
    fi

    printf "\n"
    ok "Uninstall complete."
}

# =============================================================================
#  MAIN
# =============================================================================
main() {
    # Handle uninstall flag
    if [[ $# -gt 0 && "$1" == "--uninstall" ]]; then
        detect_os
        uninstall
        exit 0
    fi

    print_banner

    # ----- Pre-flight checks -------------------------------------------------
    if [[ $EUID -eq 0 ]]; then
        die "Do not run this script as root. Run it as a normal user."
    fi

    # Ensure project files exist
    if [[ ! -f "$PROJECT_DIR/main.py" ]]; then
        die "main.py not found in $PROJECT_DIR. Make sure install.sh is in the song-dl project root."
    fi
    if [[ ! -d "$PROJECT_DIR/songdl" ]]; then
        die "songdl/ directory not found in $PROJECT_DIR. Make sure install.sh is in the song-dl project root."
    fi
    if [[ ! -f "$PROJECT_DIR/requirements.txt" ]]; then
        die "requirements.txt not found in $PROJECT_DIR."
    fi

    # ----- Detect OS ---------------------------------------------------------
    section "Detecting Operating System"
    detect_os
    ok "Detected: $OS_NAME"
    info "Package manager: ${PKG_MANAGER:-none}"
    if [[ -n "$SUDO_CMD" ]]; then
        info "Privilege escalation: $SUDO_CMD"
    else
        info "Running with root privileges (or sudo not available)."
    fi

    # ----- Check dependencies ------------------------------------------------
    section "Checking Dependencies"
    check_deps

    # ----- Handle Python < 3.8 -----------------------------------------------
    if [[ -z "$PYTHON_CMD" ]]; then
        printf "\n"
        error "Python 3.8+ is required but not found."
        case "$PKG_MANAGER" in
            apt)   info "Install it: sudo apt install python3" ;;
            dnf)   info "Install it: sudo dnf install python3" ;;
            pacman) info "Install it: sudo pacman -S python" ;;
            zypper) info "Install it: sudo zypper install python3" ;;
            apk)   info "Install it: apk add python3" ;;
            brew)  info "Install it: brew install python@3" ;;
            winget) info "Install it: winget install Python.Python.3" ;;
            choco) info "Install it: choco install python" ;;
        esac
        die "Python 3.8+ is required."
    fi

    # Verify version again for the detailed error
    local py_ver
    py_ver="$("$PYTHON_CMD" --version 2>/dev/null | awk '{print $2}')" || true
    if [[ -n "$py_ver" ]]; then
        local pymajor pyminor
        pymajor="${py_ver%%.*}"
        pyminor="${py_ver#*.}"
        pyminor="${pyminor%%.*}"
        pyminor="${pyminor%%[!0-9]*}"
        if [[ "$pymajor" -lt "$PYTHON_REQUIRED_MAJOR" ]] || \
           [[ "$pymajor" -eq "$PYTHON_REQUIRED_MAJOR" && "$pyminor" -lt "$PYTHON_REQUIRED_MINOR" ]]; then
            printf "\n"
            error "Python $py_ver is too old. Python $PYTHON_REQUIRED_MAJOR.$PYTHON_REQUIRED_MINOR+ is required."
            die "Please install a newer version of Python 3."
        fi
    fi

    # ----- JS Runtime (Deno/Node) --------------------------------------------
    if [[ "$_JS_RUNTIME" == "deno" ]]; then
        ok "Deno found. yt-dlp will use it for YouTube extraction."
    elif [[ "$_JS_RUNTIME" == "node" ]]; then
        info "Node.js found. yt-dlp will use it for YouTube extraction."
    else
        printf "\n"
        warn "No JavaScript runtime found (Deno or Node.js)."
        warn "yt-dlp requires a JS runtime for YouTube extraction, otherwise"
        warn "it may fall back to the Android API which YouTube blocks (403 error)."
        printf "\n"
        read -r -p "  Install Deno? (lightweight, ~40 MB, recommended) [Y/n] > " REPLY
        REPLY="${REPLY:-Y}"
        if [[ "${REPLY:0:1}" =~ [Yy] ]]; then
            info "Installing Deno ..."
            if command -v curl &>/dev/null; then
                curl -fsSL https://deno.land/install.sh | sh
            elif command -v wget &>/dev/null; then
                wget -qO- https://deno.land/install.sh | sh
            else
                warn "Neither curl nor wget found. Cannot install Deno automatically."
            fi
            # Re-check if Deno is now available
            if command -v deno &>/dev/null; then
                ok "Deno installed successfully."
                _JS_RUNTIME="deno"
            else
                warn "Deno may have been installed but is not in your PATH."
                warn "If installed, add ~/.deno/bin to your PATH or log out and back in."
            fi
        else
            info "Skipping Deno installation. yt-dlp may get 403 errors on YouTube."
        fi
        printf "\n"
    fi

    # ----- Confirmation ------------------------------------------------------
    confirm_installation

    _INSTALL_STARTED=true

    # ----- Install missing system packages -----------------------------------
    if $NEED_PIP || $NEED_VENV || $NEED_FFMPEG; then
        section "Installing System Dependencies"

        if $NEED_PIP; then
            install_system_pkg "pip" "python3-pip"
        fi
        if $NEED_VENV; then
            install_system_pkg "venv" "python3-venv"
        fi
        if $NEED_FFMPEG; then
            install_system_pkg "ffmpeg" "ffmpeg"
        fi
    fi

    # Re-check pip/venv availability after system installs
    if [[ -n "$PYTHON_CMD" ]]; then
        if ! "$PYTHON_CMD" -m pip --version &>/dev/null; then
            # Try to install pip via ensurepip if available
            "$PYTHON_CMD" -m ensurepip --upgrade 2>/dev/null || true
            if ! "$PYTHON_CMD" -m pip --version &>/dev/null; then
                die "pip is still not available after install attempt."
            fi
        fi
    fi

    # ----- Install Python deps -----------------------------------------------
    printf "\n"
    install_python_deps

    # ----- Setup launcher ----------------------------------------------------
    printf "\n"
    setup_launcher

    # ----- Show ffmpeg guide if still missing --------------------------------
    show_ffmpeg_guide

    # ----- Success -----------------------------------------------------------
    show_success
}

main "$@"
