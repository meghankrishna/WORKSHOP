#!/usr/bin/env bash
#
# check_packages.sh -- verify the system packages the bootcamp needs.
#
# Meant for machines where students have NO sudo access: it only READS the
# package database (dpkg), never installs anything and never calls sudo or
# apt-get. If a required package is missing it prints what is missing and
# exits with status 1, so a calling script stops.
#
# Target: Ubuntu 24.04 LTS on amd64.
#
# Usage:
#   ./check_packages.sh              # check and report
#   ./check_packages.sh && ./task1.sh setup      # run the next step only if OK
#   source ./check_packages.sh || exit 1         # as a guard at the top of a script
#
# Exit status: 0 = every required package is present, 1 = something required
# is missing (or the machine is not amd64 Ubuntu).

# Collect everything first, then decide, so students see the full list at once.
# (No `set -e`: this file may be sourced, and must not kill the caller's shell.)

REQUIRED_ARCH="amd64"
REQUIRED_OS_ID="ubuntu"
REQUIRED_OS_VERSION="24.04"

# Required: the same packages task1.sh installs on Linux, plus what the labs use.
REQUIRED_PACKAGES=(
    openjdk-17-jdk      # sdkmanager / avdmanager / Gradle
    wget
    curl
    unzip
    xz-utils            # frida-server is shipped as .xz
    git
    python3
    python3-venv        # task1.sh builds a virtual environment
    python3-pip
    libc6-i386          # 32-bit support used by the Android tools on amd64
    libstdc++6:i386
    zlib1g:i386
)

# Recommended: the emulator window needs these. Missing ones only warn.
RECOMMENDED_PACKAGES=(
    libpulse0
    libnss3
    libgl1
    libx11-6
    libxcomposite1
    libxcursor1
    libxi6
    libxtst6
    libasound2t64
)

# Test hooks (let the script be tested on a machine without dpkg/Ubuntu).
OS_RELEASE_FILE="${OS_RELEASE_FILE:-/etc/os-release}"

_cp_missing=()
_cp_warn=()
_cp_problems=0

_cp_ok()   { printf '  [ OK ]  %s\n' "$*"; }
_cp_bad()  { printf '  [FAIL]  %s\n' "$*"; }
_cp_note() { printf '  [WARN]  %s\n' "$*"; }

# Is the package fully installed? Works for "name" and "name:arch".
_cp_installed() {
    local status
    status="$(dpkg-query -W -f='${db:Status-Abbrev}' "$1" 2>/dev/null)" || return 1
    [[ "$status" == ii* ]]
}

_cp_main() {
    echo "== Bootcamp package check (no sudo needed) =="

    # --- is dpkg even here? -------------------------------------------------
    if ! command -v dpkg-query >/dev/null 2>&1 || ! command -v dpkg >/dev/null 2>&1; then
        _cp_bad "dpkg not found: this check is for Ubuntu/Debian machines."
        return 1
    fi

    # --- operating system ---------------------------------------------------
    echo
    echo "-- System --"
    local os_id="" os_version="" os_pretty=""
    if [[ -r "$OS_RELEASE_FILE" ]]; then
        os_id="$(. "$OS_RELEASE_FILE" 2>/dev/null; echo "${ID:-}")"
        os_version="$(. "$OS_RELEASE_FILE" 2>/dev/null; echo "${VERSION_ID:-}")"
        os_pretty="$(. "$OS_RELEASE_FILE" 2>/dev/null; echo "${PRETTY_NAME:-}")"
    fi
    if [[ "$os_id" == "$REQUIRED_OS_ID" && "$os_version" == "$REQUIRED_OS_VERSION" ]]; then
        _cp_ok "Operating system: ${os_pretty}"
    elif [[ "$os_id" == "$REQUIRED_OS_ID" ]]; then
        _cp_note "Operating system is ${os_pretty:-unknown}; this bootcamp is tested on Ubuntu ${REQUIRED_OS_VERSION}."
    else
        _cp_note "Operating system is ${os_pretty:-unknown}; this bootcamp is tested on Ubuntu ${REQUIRED_OS_VERSION}."
    fi

    local arch
    arch="$(dpkg --print-architecture 2>/dev/null)"
    if [[ "$arch" == "$REQUIRED_ARCH" ]]; then
        _cp_ok "CPU architecture: ${arch}"
    else
        _cp_bad "CPU architecture is '${arch:-unknown}', but ${REQUIRED_ARCH} is required."
        _cp_problems=$((_cp_problems + 1))
    fi

    # --- 32-bit (i386) package support must be switched on ------------------
    # Only an administrator can enable it; students can only check for it.
    if dpkg --print-foreign-architectures 2>/dev/null | grep -qx "i386"; then
        _cp_ok "i386 architecture enabled"
    else
        _cp_bad "i386 architecture is not enabled (an administrator must run: dpkg --add-architecture i386)"
        _cp_problems=$((_cp_problems + 1))
    fi

    # --- required packages --------------------------------------------------
    echo
    echo "-- Required packages --"
    local pkg
    for pkg in "${REQUIRED_PACKAGES[@]}"; do
        if _cp_installed "$pkg"; then
            _cp_ok "$pkg"
        else
            _cp_bad "$pkg  (not installed)"
            _cp_missing+=("$pkg")
        fi
    done

    # --- recommended packages -----------------------------------------------
    echo
    echo "-- Recommended packages (emulator window) --"
    for pkg in "${RECOMMENDED_PACKAGES[@]}"; do
        if _cp_installed "$pkg"; then
            _cp_ok "$pkg"
        else
            _cp_note "$pkg  (not installed; the emulator window may not start)"
            _cp_warn+=("$pkg")
        fi
    done

    # --- hardware acceleration (warning only) -------------------------------
    echo
    echo "-- Emulator acceleration --"
    if [[ -e /dev/kvm ]]; then
        if [[ -r /dev/kvm && -w /dev/kvm ]]; then
            _cp_ok "/dev/kvm is available to you"
        else
            _cp_note "/dev/kvm exists but you cannot use it (an administrator must add you to the 'kvm' group); the emulator will be very slow."
        fi
    else
        _cp_note "/dev/kvm not found (virtualization off?); the emulator will be very slow."
    fi

    # --- verdict ------------------------------------------------------------
    echo
    if (( ${#_cp_missing[@]} > 0 || _cp_problems > 0 )); then
        echo "RESULT: NOT READY. Stopping."
        if (( ${#_cp_missing[@]} > 0 )); then
            echo
            echo "Missing required packages:"
            printf '  - %s\n' "${_cp_missing[@]}"
            echo
            echo "You cannot install these yourself (no sudo). Send this list to your"
            echo "administrator, who can install them with:"
            echo "  sudo apt-get install -y ${_cp_missing[*]}"
        fi
        return 1
    fi

    if (( ${#_cp_warn[@]} > 0 )); then
        echo "RESULT: READY, with ${#_cp_warn[@]} warning(s) above."
    else
        echo "RESULT: READY. All packages are installed."
    fi
    return 0
}

_cp_main
_cp_status=$?

# When executed, exit with the status. When sourced, return it instead, so the
# caller's shell survives and can do `source check_packages.sh || exit 1`.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    exit "$_cp_status"
fi
return "$_cp_status"
