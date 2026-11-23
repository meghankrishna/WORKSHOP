#!/usr/bin/env bash
#
# Android Analysis Environment Setup / Lifecycle Framework
#
# Preserved user-specific configuration:
#   API_LEVEL, BUILD_TOOLS_VERSION, CMDLINE_TOOLS_VERSION,
#   default AVD naming, rootAVD repository, and the explicit Magisk
#   UI tap coordinates/text used by the existing rootAVD flow.
#
# Supported hosts:
#   - macOS
#   - Linux
#
# Main commands:
#   ./task1.sh setup
#   ./task1.sh start
#   ./task1.sh stop
#   ./task1.sh restart
#   ./task1.sh snapshot-save [name]
#   ./task1.sh snapshot-load [name]
#   ./task1.sh install-apk /path/to/app.apk
#   ./task1.sh frida-start
#   ./task1.sh frida-stop
#   ./task1.sh frida-status
#   ./task1.sh verify
#
# Optional environment variables retained from the original script:
#   API_LEVEL=29
#   ARCH=x86_64 (auto-selected on non-Apple-Silicon hosts)
#   AVD_NAME=pixel-${API_LEVEL}
#   BUILD_TOOLS_VERSION=29.0.0
#   CMDLINE_TOOLS_VERSION=15859902
#   FRIDA_VERSION=""
#
# Additional controls:
#   FRESH_AVD=1              # Preserve original default. Set 0 to reuse AVD/snapshots.
#   SNAPSHOT_NAME=analysis-clean
#   APK_PATH=/path/to/file.apk
#   VENV_DIR=$PWD/venv
#   PYTHON_REQUIREMENTS=requirements.txt
#   FRIDA_PORT=27042
#   ROOTAVD_REPO=https://github.com/heet-1011/rootAVD-forked.git
#   SKIP_ROOT=0
#   SKIP_FRIDA_SERVER=0
#

set -euo pipefail
IFS=$'\n\t'

# ============================================================
# Configuration (existing constants intentionally preserved)
# ============================================================

API_LEVEL="${API_LEVEL:-29}"
AVD_NAME="${AVD_NAME:-pixel-${API_LEVEL}}"
BUILD_TOOLS_VERSION="${BUILD_TOOLS_VERSION:-29.0.0}"
CMDLINE_TOOLS_VERSION="${CMDLINE_TOOLS_VERSION:-15859902}"

ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}"
ANDROID_HOME="${ANDROID_HOME:-$ANDROID_SDK_ROOT}"

CMDLINE_TOOLS_DIR="$ANDROID_SDK_ROOT/cmdline-tools/latest"
PLATFORM_TOOLS_DIR="$ANDROID_SDK_ROOT/platform-tools"
EMULATOR_DIR="$ANDROID_SDK_ROOT/emulator"

FRESH_AVD="${FRESH_AVD:-1}"
AVD_DIR="$HOME/.android/avd"

FRIDA_VERSION="${FRIDA_VERSION:-}"
FRIDA_PORT="${FRIDA_PORT:-27042}"
ROOTAVD_DIR="${ROOTAVD_DIR:-$HOME/rootAVD-forked}"
ROOTAVD_REPO="${ROOTAVD_REPO:-https://github.com/heet-1011/rootAVD-forked.git}"
SKIP_ROOT="${SKIP_ROOT:-0}"
SKIP_FRIDA_SERVER="${SKIP_FRIDA_SERVER:-0}"

SNAPSHOT_NAME="${SNAPSHOT_NAME:-analysis-clean}"
APK_PATH="${APK_PATH:-}"
ADB_SERIAL="${ADB_SERIAL:-}"
VENV_DIR="${VENV_DIR:-$(pwd)/venv}"
PYTHON_REQUIREMENTS="${PYTHON_REQUIREMENTS:-requirements.txt}"

RUNTIME_LOG="$HOME/${AVD_NAME}.log"
RUNTIME_PID_FILE="$HOME/${AVD_NAME}.pid"
ROOT_RUNTIME_PID_FILE="$HOME/${AVD_NAME}.root.pid"
ROOTAVD_MARKER=""
SYSTEM_IMAGE=""
HOST_PLATFORM=""
# keep a caller-supplied ARCH (e.g. ARCH=x86_64 ./task1.sh setup); detect_os
# only auto-selects when this is empty
ARCH="${ARCH:-}"
EMULATOR_SERIAL=""

# ============================================================
# Logging / errors
# ============================================================

log() {
    echo
    echo "[setup] $*"
}

warn() {
    echo "[setup][WARN] $*" >&2
}

die() {
    echo "[setup][ERROR] $*" >&2
    exit 1
}

is_command_available() {
    command -v "$1" >/dev/null 2>&1
}

require_command() {
    is_command_available "$1" || die "Required command not found: $1"
}

# ============================================================
# OS / architecture detection
# ============================================================

detect_os() {
    local os host_arch
    os="$(uname -s)"
    host_arch="$(uname -m)"

    case "$os" in
        Darwin) HOST_PLATFORM="darwin" ;;
        Linux)  HOST_PLATFORM="linux" ;;
        *) die "Unsupported host OS: $os (supported: macOS and Linux)" ;;
    esac

    # Preserve the existing behaviour: Apple Silicon defaults to arm64-v8a;
    # all other hosts default to x86_64 unless ARCH is explicitly supplied.
    if [[ -n "${ARCH:-}" ]]; then
        : # caller explicitly selected ARCH
    elif [[ "$HOST_PLATFORM" == "darwin" && "$host_arch" == "arm64" ]]; then
        ARCH="arm64-v8a"
    else
        ARCH="x86_64"
    fi

    SYSTEM_IMAGE="system-images;android-${API_LEVEL};google_apis;${ARCH}"
    ROOTAVD_MARKER="$AVD_DIR/.rootavd-configured-${API_LEVEL}-${ARCH}"

    log "Host platform: $HOST_PLATFORM ($host_arch)"
    log "Android API:   $API_LEVEL"
    log "Image ABI:     $ARCH"
    log "System image:  $SYSTEM_IMAGE"
    log "AVD:            $AVD_NAME"
}

# ============================================================
# Process / emulator lifecycle helpers
# ============================================================

recorded_pid_is_emulator() {
    local pid="$1"
    local command_line
    kill -0 "$pid" 2>/dev/null || return 1
    command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    [[ "$command_line" == *"@${AVD_NAME}"* ]]
}

stop_previous_emulator() {
    local pid_file="$1"
    local old_pid
    [[ -f "$pid_file" ]] || return 0
    old_pid="$(<"$pid_file")"
    if [[ ! "$old_pid" =~ ^[0-9]+$ ]] || ! recorded_pid_is_emulator "$old_pid"; then
        rm -f "$pid_file"
        return 0
    fi

    log "Stopping recorded emulator (PID $old_pid)"
    kill "$old_pid" 2>/dev/null || true
    for _ in {1..20}; do
        kill -0 "$old_pid" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$old_pid" 2>/dev/null; then
        kill -9 "$old_pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
}

find_emulator_serial() {
    local serial avd_from_device
    if [[ -n "$ADB_SERIAL" ]]; then
        serial="$ADB_SERIAL"
        adb -s "$serial" get-state >/dev/null 2>&1 || return 1
        avd_from_device="$(adb -s "$serial" emu avd name 2>/dev/null | head -n1 | tr -d '\r')"
        if [[ -z "$avd_from_device" ]]; then
            avd_from_device="$(adb -s "$serial" shell getprop ro.boot.qemu.avd_name 2>/dev/null | tr -d '\r')"
        fi
        [[ "$avd_from_device" == "$AVD_NAME" ]] || return 1
        EMULATOR_SERIAL="$serial"
        return 0
    fi

    while read -r serial; do
        [[ -n "$serial" ]] || continue
        avd_from_device="$(adb -s "$serial" emu avd name 2>/dev/null | head -n1 | tr -d '\r')"
        if [[ -z "$avd_from_device" ]]; then
            avd_from_device="$(adb -s "$serial" shell getprop ro.boot.qemu.avd_name 2>/dev/null | tr -d '\r')"
        fi
        if [[ "$avd_from_device" == "$AVD_NAME" ]]; then
            EMULATOR_SERIAL="$serial"
            return 0
        fi
    done < <(adb devices | awk '$1 ~ /^emulator-[0-9]+$/ && $2 == "device" {print $1}')

    EMULATOR_SERIAL=""
    return 1
}

adb_target() {
    [[ -n "$EMULATOR_SERIAL" ]] || find_emulator_serial || die "No emulator is connected to ADB."
    adb -s "$EMULATOR_SERIAL" "$@"
}

cleanup_stale_runtime_files() {
    stop_previous_emulator "$RUNTIME_PID_FILE"
    stop_previous_emulator "$ROOT_RUNTIME_PID_FILE"
    rm -f /tmp/window_dump.xml
    # IMPORTANT: do not delete snapshots here. Snapshot lifecycle is an
    # assignment requirement and must survive ordinary stop/start operations.
    find "$AVD_DIR/${AVD_NAME}.avd" -maxdepth 1 -type f -name '*.lock' -delete 2>/dev/null || true
}

# ============================================================
# Host prerequisites
# ============================================================

install_prerequisites() {

    log "Checking host prerequisites"

    if [[ "$HOST_PLATFORM" == "darwin" ]]; then

        if ! command -v brew >/dev/null 2>&1; then
            die "Homebrew is required on macOS. Install it first."
        fi

        log "Checking Java, wget and unzip using Homebrew"

        local brew_packages=()
        is_command_available java || brew_packages+=(openjdk@17)
        is_command_available wget || brew_packages+=(wget)
        is_command_available unzip || brew_packages+=(unzip)
        is_command_available xz || brew_packages+=(xz)   # frida-server is shipped as .xz
        if (( ${#brew_packages[@]} > 0 )); then
            brew install "${brew_packages[@]}"
        fi

        if [[ -d "/opt/homebrew/opt/openjdk@17" ]]; then
            export JAVA_HOME="/opt/homebrew/opt/openjdk@17"
        elif [[ -d "/usr/local/opt/openjdk@17" ]]; then
            export JAVA_HOME="/usr/local/opt/openjdk@17"
        fi

        if [[ -n "${JAVA_HOME:-}" ]]; then
            export PATH="$JAVA_HOME/bin:$PATH"
        fi

        else

        if ! command -v apt-get >/dev/null 2>&1; then
            die "This Linux distribution does not provide apt-get."
        fi

        log "Checking Linux prerequisites"

        local apt_packages=()

        is_command_available java || apt_packages+=(openjdk-17-jdk)
        is_command_available wget || apt_packages+=(wget)
        is_command_available unzip || apt_packages+=(unzip)
        is_command_available xz || apt_packages+=(xz-utils)   # frida-server is shipped as .xz
        is_command_available curl || apt_packages+=(curl)
        is_command_available git || apt_packages+=(git)

        # 32-bit x86 libraries are only needed on amd64 Linux.
        local host_arch
        host_arch="$(dpkg --print-architecture)"

        if [[ "$host_arch" == "amd64" ]]; then

            if ! dpkg --print-foreign-architectures | grep -qx "i386"; then
                log "Enabling i386 architecture"
                dpkg --add-architecture i386
                apt-get update
            fi

            apt_packages+=(
                libc6-i386
                libstdc++6:i386
                zlib1g:i386
            )

        elif [[ "$host_arch" == "arm64" ]]; then

            log "Host architecture is arm64; skipping x86/i386 libraries"

            # Remove stale i386 configuration from an earlier run.
            if dpkg --print-foreign-architectures | grep -qx "i386"; then
                log "Removing stale i386 architecture from ARM64 host"
                dpkg --remove-architecture i386 || true
            fi

        else
            log "Host architecture is $host_arch; skipping x86 i386 libraries"
        fi

        if (( ${#apt_packages[@]} > 0 )); then
            apt-get update
            apt-get install -y "${apt_packages[@]}"
        fi

        export JAVA_HOME="${JAVA_HOME:-$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")}"

    fi

    if ! command -v java >/dev/null 2>&1; then
        die "Java installation failed."
    fi

    log "Java version:"
    java -version
}

# ============================================================
# SDK configuration / installation
# ============================================================

configure_sdk_directories() {
    log "Configuring Android SDK paths"
    mkdir -p "$ANDROID_SDK_ROOT" "$ANDROID_SDK_ROOT/cmdline-tools" "$AVD_DIR"
    export ANDROID_HOME="$ANDROID_SDK_ROOT"
    export ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT"
    export PATH="$CMDLINE_TOOLS_DIR/bin:$PLATFORM_TOOLS_DIR:$EMULATOR_DIR:$ANDROID_SDK_ROOT/platform-tools:$PATH"
    log "ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT"
}

install_cmdline_tools() {
    log "Installing Android command-line tools $CMDLINE_TOOLS_VERSION"
    if [[ -x "$CMDLINE_TOOLS_DIR/bin/sdkmanager" ]]; then
        log "Command-line tools already installed"
        return
    fi

    local url zip_file temp_dir host_arch
    host_arch="$(uname -m)"
    temp_dir="$(mktemp -d)"
    zip_file="/tmp/android-cmdline-tools-${CMDLINE_TOOLS_VERSION}.zip"

    case "$HOST_PLATFORM:$host_arch" in
        darwin:arm64)
            url="https://dl.google.com/android/repository/commandlinetools-mac_arm64-${CMDLINE_TOOLS_VERSION}_latest.zip" ;;
        darwin:x86_64)
            url="https://dl.google.com/android/repository/commandlinetools-mac_x86_64-${CMDLINE_TOOLS_VERSION}_latest.zip" ;;
        linux:*)
            url="https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_VERSION}_latest.zip" ;;
    esac

    log "Downloading: $url"
    curl -fL --retry 3 -o "$zip_file" "$url"
    unzip -q "$zip_file" -d "$temp_dir"
    rm -rf "$CMDLINE_TOOLS_DIR"
    mkdir -p "$CMDLINE_TOOLS_DIR"
    cp -a "$temp_dir/cmdline-tools/." "$CMDLINE_TOOLS_DIR/"
    rm -rf "$temp_dir" "$zip_file"

    [[ -x "$CMDLINE_TOOLS_DIR/bin/sdkmanager" ]] || die "sdkmanager installation failed"
}

accept_licenses() {
    log "Accepting Android SDK licenses"
    yes | sdkmanager --sdk_root="$ANDROID_SDK_ROOT" --licenses >/dev/null || true
}

sdk_is_installed() {
    local package_name="$1"
    sdkmanager --sdk_root="$ANDROID_SDK_ROOT" --list_installed 2>/dev/null | grep -Fq "  ${package_name}"
}

sdk_install() {
    log "Installing required Android SDK packages"

    if [[ "$HOST_PLATFORM" == "linux" && "$(uname -m)" != "x86_64" ]]; then
        die "The Android Emulator SDK package is not published for Linux $(uname -m). Google does not ship an emulator binary for Linux aarch64 hosts. Use Linux x86_64/amd64, macOS, or run this inside a Docker container started with --platform linux/amd64."
    fi

    local packages=(
        "platform-tools"
        "emulator"
        "build-tools;${BUILD_TOOLS_VERSION}"
        "platforms;android-${API_LEVEL}"
        "${SYSTEM_IMAGE}"
    )

    local package
    for package in "${packages[@]}"; do
        if sdk_is_installed "$package"; then
            log "Already installed: $package"
        else
            log "Installing: $package"
            sdkmanager --sdk_root="$ANDROID_SDK_ROOT" "$package"
        fi
    done

    local image_dir="$ANDROID_SDK_ROOT/system-images/android-${API_LEVEL}/google_apis/${ARCH}"
    [[ -d "$image_dir" ]] || die "System image directory does not exist: $image_dir"
    [[ -f "$image_dir/package.xml" ]] || die "System image is incomplete: $image_dir/package.xml missing"
}

# ============================================================
# AVD creation / configuration
# ============================================================

avd_exists() {
    avdmanager list avd 2>/dev/null | grep -q "Name: ${AVD_NAME}"
}

delete_existing_avd() {
    stop_previous_emulator "$RUNTIME_PID_FILE"
    stop_previous_emulator "$ROOT_RUNTIME_PID_FILE"
    if avd_exists; then
        log "Deleting existing AVD: $AVD_NAME"
        avdmanager delete avd --name "$AVD_NAME" 2>/dev/null || true
    fi
    rm -rf "${AVD_DIR:?}/${AVD_NAME}.avd"
    rm -f "$AVD_DIR/${AVD_NAME}.ini"
    rm -f "$ROOTAVD_MARKER"
}

create_avd() {
    local config="$AVD_DIR/${AVD_NAME}.avd/config.ini"
    local image_dir="$ANDROID_SDK_ROOT/system-images/android-${API_LEVEL}/google_apis/${ARCH}"

    [[ -d "$image_dir" && -f "$image_dir/package.xml" ]] || die "Required system image is not usable: $image_dir"

    if [[ "$FRESH_AVD" == "1" ]]; then
        log "FRESH_AVD=1: creating a clean AVD"
        delete_existing_avd
    elif avd_exists && [[ -f "$config" ]]; then
        log "Reusing existing AVD: $AVD_NAME"
        return
    fi

    log "Creating AVD $AVD_NAME from $SYSTEM_IMAGE"
    printf 'no\n' | avdmanager create avd \
        --name "$AVD_NAME" \
        --package "$SYSTEM_IMAGE" \
        --device "pixel" \
        --force

    [[ -f "$config" ]] || die "AVD creation failed: $config was not created"
}

configure_avd() {
    local config="$AVD_DIR/${AVD_NAME}.avd/config.ini"
    [[ -f "$config" ]] || die "AVD config missing: $config"

    log "Applying existing AVD configuration"
    # Keep the configuration values from the submitted script unchanged.
    sed -i.bak \
        -e '/^hw.keyboard=/d' \
        -e '/^hw.gpu.enabled=/d' \
        -e '/^showDeviceFrame=/d' \
        -e '/^fastboot.forceColdBoot=/d' \
        -e '/^snapshot.present=/d' \
        -e '/^disk.dataPartition.size=/d' \
        "$config"

    cat >> "$config" <<EOF

# Android analysis configuration
avd.ini.displayname=${AVD_NAME}
disk.dataPartition.size=2G
hw.keyboard=yes
hw.gpu.enabled=yes
showDeviceFrame=no
fastboot.forceColdBoot=no
snapshot.present=false
EOF
    rm -f "${config}.bak"
}

# ============================================================
# RootAVD (existing explicit taps preserved)
# ============================================================

install_rootavd() {
    [[ "$SKIP_ROOT" == "1" ]] && { log "SKIP_ROOT=1: skipping rootAVD installation"; return; }
    log "Checking rootAVD"
    if [[ ! -d "$ROOTAVD_DIR" ]]; then
        git clone "$ROOTAVD_REPO" "$ROOTAVD_DIR"
    fi
    [[ -f "$ROOTAVD_DIR/rootAVD.sh" ]] || die "rootAVD.sh was not found in $ROOTAVD_DIR"
    chmod +x "$ROOTAVD_DIR/rootAVD.sh"
    log "Available rootAVD targets"
    (cd "$ROOTAVD_DIR" && ./rootAVD.sh ListAllAVDs || true)
}

tap_on_text() {
    # Existing UI automation helper intentionally retained.
    local target="$1"
    adb_target shell uiautomator dump /sdcard/window_dump.xml >/dev/null
    adb_target pull /sdcard/window_dump.xml /tmp/window_dump.xml >/dev/null

    local bounds
    bounds=$(grep -o "text=\"$target\"[^>]*bounds=\"[^\"]*\"" /tmp/window_dump.xml \
        | grep -o 'bounds="[^"]*"' | head -1 | sed 's/bounds="//;s/"//')
    [[ -n "$bounds" ]] || { echo "no element with text '$target' found"; return 1; }

    local x1 y1 x2 y2 cx cy
    x1=$(echo "$bounds" | sed -E 's/\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]/\1/')
    y1=$(echo "$bounds" | sed -E 's/\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]/\2/')
    x2=$(echo "$bounds" | sed -E 's/\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]/\3/')
    y2=$(echo "$bounds" | sed -E 's/\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]/\4/')
    cx=$(( (x1 + x2) / 2 ))
    cy=$(( (y1 + y2) / 2 ))

    adb_target shell input tap "$cx" "$cy"
}

wait_for_adb() {
    log "Waiting for emulator ADB connectivity"
    local deadline=$((SECONDS + 180))
    while (( SECONDS < deadline )); do
        if find_emulator_serial; then
            local state
            state="$(adb_target get-state 2>/dev/null || true)"
            if [[ "$state" == "device" ]]; then
                log "ADB connected: $EMULATOR_SERIAL"
                return 0
            fi
        fi
        sleep 2
    done
    adb devices -l || true
    tail -n 100 "$RUNTIME_LOG" 2>/dev/null || true
    die "Emulator did not become available through ADB"
}

wait_for_boot() {

    log "Waiting for Android to finish booting"

    local attempts=0
    local max_attempts=180

    while true; do

        boot_completed="$(adb_target shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')"

        if [[ "$boot_completed" == "1" ]]; then
            break
        fi

        attempts=$((attempts + 1))

        if (( attempts >= max_attempts )); then
            log "Emulator log:"
            tail -n 50 "$HOME/${AVD_NAME}.log" || true
            die "Android failed to boot within the expected time."
        fi

        echo "[setup] Waiting for Android boot... ($attempts/$max_attempts)"
        sleep 2
    done

    # Wait until package manager is ready as well.
    while [[ "$(adb_target shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" != "1" ]]; do
        sleep 2
    done

    log "Android boot completed"
}


check_root_access() {
    adb_target shell su -c id 2>/dev/null | grep -q 'uid=0'
}

launch_magisk() {
    log "Launching Magisk"

    local package_path=""
    local deadline=$((SECONDS + 60))

    while (( SECONDS < deadline )); do
        package_path="$(adb_target shell pm path com.topjohnwu.magisk 2>/dev/null | tr -d '\r' || true)"
        if [[ -n "$package_path" ]] && adb_target shell monkey \
            -p com.topjohnwu.magisk \
            -c android.intent.category.LAUNCHER \
            1 >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done

    if [[ -z "$package_path" ]]; then
        die "Magisk is not installed in the patched emulator image."
    fi
    die "Magisk activity service did not become available after 60 seconds."
}

start_root_emulator() {
    stop_previous_emulator "$ROOT_RUNTIME_PID_FILE"
    log "Starting temporary rootAVD/Magisk emulator"
    nohup emulator \
        "@${AVD_NAME}" \
        -no-boot-anim \
        -no-snapshot-load \
        -writable-system \
        >"$RUNTIME_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$ROOT_RUNTIME_PID_FILE"
}

configure_rootavd() {
    [[ "$SKIP_ROOT" == "1" ]] && return 0

    # If the marker exists, verify root rather than trusting a stale marker.
    if [[ -f "$ROOTAVD_MARKER" ]]; then
        if start_emulator; then
            if check_root_access; then
                log "Existing rootAVD configuration verified"
                return 0
            fi
            stop_emulator
        fi
        warn "Root marker exists but root verification failed; rerunning rootAVD"
    fi

    log "Patching AVD image using rootAVD"
    # subshell: rootAVD needs to run from the SDK root, but the rest of setup
    # must stay in the original directory (relative PYTHON_REQUIREMENTS etc.)
    (
        cd "$ANDROID_SDK_ROOT"
        "$ROOTAVD_DIR/rootAVD.sh" \
            "system-images/android-${API_LEVEL}/google_apis/${ARCH}/ramdisk.img"
    )

    # Existing rootAVD/Magisk flow retained, but fixed sleeps are replaced by
    # event/property-based waits whenever a device state can be observed.
    stop_emulator
    start_emulator
    wait_for_adb
    wait_for_boot
    launch_magisk

    echo "Opening Magisk app..."
    tap_on_text "OK" || warn "Magisk did not display an OK prompt; continuing"
    sleep 10
    wait_for_adb
    wait_for_boot
    launch_magisk
    sleep 4
    echo "Opening Magisk app and granting root permission..."
    adb_target shell su -c id &>/dev/null &
    sleep 2
    adb_target shell input tap "725" "1245.9" ||
    warn "Magisk permission tap could not be delivered; continuing"
    tap_on_text "CANCEL" ||
    warn "Magisk did not display a CANCEL prompt; continuing"
    # adb shell input tap "934.9" "327.8"

    # Verify the resulting root state instead of assuming that a delay means success.
    local deadline=$((SECONDS + 60))
    while (( SECONDS < deadline )); do
        if check_root_access; then
            touch "$ROOTAVD_MARKER"
            return 0
        fi
        sleep 2
    done

    warn "rootAVD completed but root could not be verified automatically. Magisk may require an interactive approval on this emulator."
}

# ============================================================
# Emulator start/stop/restart
# ============================================================

start_emulator() {
    if find_emulator_serial; then
        wait_for_boot
        return 0
    fi

    # rootAVD may have shut the previous emulator down while adb still
    # advertises its old serial. Remove that stale process before launching a
    # new instance for the same AVD.
    stop_previous_emulator "$RUNTIME_PID_FILE"
    stop_previous_emulator "$ROOT_RUNTIME_PID_FILE"

    log "Starting emulator: $AVD_NAME"
    rm -f "$RUNTIME_LOG"
    nohup emulator \
        "@${AVD_NAME}" \
        -no-boot-anim \
        -no-snapshot-load \
        -no-snapshot-save \
        -writable-system \
        >"$RUNTIME_LOG" 2>&1 &

    local pid=$!
    echo "$pid" > "$RUNTIME_PID_FILE"
    log "Emulator PID: $pid"
    wait_for_adb
    wait_for_boot
}

stop_emulator() {
    if find_emulator_serial 2>/dev/null; then
        log "Stopping emulator $EMULATOR_SERIAL"
        adb_target emu kill >/dev/null 2>&1 || true
        local deadline=$((SECONDS + 30))
        while (( SECONDS < deadline )); do
            find_emulator_serial || break
            sleep 1
        done
    fi
    stop_previous_emulator "$RUNTIME_PID_FILE"
    stop_previous_emulator "$ROOT_RUNTIME_PID_FILE"
    EMULATOR_SERIAL=""
}

restart_emulator() {
    stop_emulator
    start_emulator
}

# ============================================================
# Snapshot management
# ============================================================

snapshot_save() {
    local name="${1:-$SNAPSHOT_NAME}"
    start_emulator
    log "Saving emulator snapshot: $name"
    adb_target emu avd snapshot save "$name"
    log "Snapshot saved: $name"
}

snapshot_load() {
    local name="${1:-$SNAPSHOT_NAME}"
    stop_emulator
    log "Booting emulator from snapshot: $name"
    rm -f "$RUNTIME_LOG"
    nohup emulator \
        "@${AVD_NAME}" \
        -snapshot "$name" \
        -no-boot-anim \
        -no-snapshot-save \
        -writable-system \
        >"$RUNTIME_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$RUNTIME_PID_FILE"
    wait_for_adb
    wait_for_boot
}

snapshot_list() {
    start_emulator
    adb_target emu avd snapshot list || true
}

# ============================================================
# Python packages / Frida host tooling
# ============================================================

install_python_packages() {
    log "Preparing Python virtual environment: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/python3" -m pip install --upgrade pip wheel setuptools

    if [[ -f "$PYTHON_REQUIREMENTS" ]]; then
        log "Installing Python requirements from $PYTHON_REQUIREMENTS"
        "$VENV_DIR/bin/python3" -m pip install -r "$PYTHON_REQUIREMENTS"
    else
        # Core packages for this framework plus APK/static analysis support.
        "$VENV_DIR/bin/python3" -m pip install frida frida-tools androguard
    fi

    "$VENV_DIR/bin/python3" -c 'import frida,sys; print("Python:",sys.version.split()[0]); print("Frida Python:",frida.__version__)'
    "$VENV_DIR/bin/frida" --version
}

host_frida_version() {
    if [[ -n "$FRIDA_VERSION" ]]; then
        printf '%s\n' "$FRIDA_VERSION"
    else
        "$VENV_DIR/bin/python3" -c 'import frida; print(frida.__version__)'
    fi
}

frida_server_asset_arch() {
    case "$ARCH" in
        arm64-v8a|arm64) printf '%s\n' "arm64" ;;
        x86_64) printf '%s\n' "x86_64" ;;
        x86) printf '%s\n' "x86" ;;
        armeabi-v7a|arm) printf '%s\n' "arm" ;;
        *) die "Unsupported Android ABI for Frida server: $ARCH" ;;
    esac
}

install_frida_server() {
    [[ "$SKIP_FRIDA_SERVER" == "1" ]] && { log "SKIP_FRIDA_SERVER=1"; return 0; }
    start_emulator

    local version asset asset_arch cache_dir xz_file server_file actual_abi
    version="$(host_frida_version)"
    asset_arch="$(frida_server_asset_arch)"
    asset="frida-server-${version}-android-${asset_arch}.xz"
    cache_dir="$HOME/.cache/android-analysis/frida/${version}"
    xz_file="$cache_dir/$asset"
    server_file="$cache_dir/${asset%.xz}"
    mkdir -p "$cache_dir"

    log "Frida host version: $version"
    log "Frida server target: $asset"

    if [[ ! -f "$server_file" ]]; then
        curl -fL --retry 3 \
            -o "$xz_file" \
            "https://github.com/frida/frida/releases/download/${version}/${asset}"
        xz -d -f "$xz_file"
        chmod 755 "$server_file"
    fi

    actual_abi="$(adb_target shell getprop ro.product.cpu.abi | tr -d '\r')"
    log "Android ABI reported by emulator: $actual_abi"

    adb_target shell su -c 'rm -f /data/local/tmp/frida-server' 2>/dev/null || true
    adb_target push "$server_file" /data/local/tmp/frida-server >/dev/null
    adb_target shell su -c 'chmod 755 /data/local/tmp/frida-server'
    adb_target shell su -c 'pkill -f /data/local/tmp/frida-server' 2>/dev/null || true
    adb_target shell su -c "/data/local/tmp/frida-server -l 127.0.0.1:${FRIDA_PORT} >/dev/null 2>&1 &"

    local deadline=$((SECONDS + 30))
    while (( SECONDS < deadline )); do
        if adb_target shell su -c 'pgrep -f /data/local/tmp/frida-server' >/dev/null 2>&1; then
            adb_target forward tcp:"$FRIDA_PORT" tcp:"$FRIDA_PORT" >/dev/null
            if "$VENV_DIR/bin/frida-ps" -H "127.0.0.1:${FRIDA_PORT}" >/dev/null 2>&1; then
                log "Frida server ${version} is running and reachable"
                return 0
            fi
        fi
        sleep 2
    done

    adb_target shell su -c 'ps -A | grep frida-server' || true
    die "Frida server failed to start or host connectivity check failed"
}

frida_start() {
    install_frida_server
}

frida_stop() {
    start_emulator
    adb_target shell su -c 'pkill -f /data/local/tmp/frida-server' 2>/dev/null || true
    adb_target forward --remove tcp:"$FRIDA_PORT" >/dev/null 2>&1 || true
    log "Frida server stopped"
}

frida_status() {
    start_emulator
    local hv
    hv="$(host_frida_version)"
    echo "Host Frida version: $hv"
    echo "Android ABI: $(adb_target shell getprop ro.product.cpu.abi | tr -d '\r')"
    if adb_target shell su -c 'pgrep -f /data/local/tmp/frida-server' >/dev/null 2>&1; then
        echo "Server: running"
        adb_target shell su -c '/data/local/tmp/frida-server --version' 2>/dev/null || true
    else
        echo "Server: not running"
    fi
}

# ============================================================
# APK installation / verification
# ============================================================

install_apk() {
    local apk="${1:-$APK_PATH}"
    [[ -n "$apk" ]] || die "Usage: $0 install-apk /path/to/app.apk (or set APK_PATH)"
    [[ -f "$apk" ]] || die "APK not found: $apk"
    [[ "$apk" == *.apk ]] || die "Input is not an APK: $apk"

    start_emulator
    log "Installing APK only to emulator $EMULATOR_SERIAL"
    adb_target install -r -d "$apk"
    log "Installed APK successfully"
}

# ============================================================
# Verification / diagnostics
# ============================================================

verify_adb() {
    start_emulator
    log "ADB verification"
    adb_target shell echo 'Connected to adb shell'
    echo "Serial:      $EMULATOR_SERIAL"
    echo "Android:     $(adb_target shell getprop ro.build.version.release | tr -d '\r')"
    echo "API level:   $(adb_target shell getprop ro.build.version.sdk | tr -d '\r')"
    echo "Model:       $(adb_target shell getprop ro.product.model | tr -d '\r')"
    echo "ABI:         $(adb_target shell getprop ro.product.cpu.abi | tr -d '\r')"
    if check_root_access; then echo "Root:        available"; else echo "Root:        NOT available"; fi
}

verify_installation() {
    detect_os
    configure_sdk_directories
    require_command sdkmanager
    require_command avdmanager
    require_command adb
    require_command emulator
    require_command python3

    log "SDK version: $(sdkmanager --version)"
    log "ADB version: $(adb version | head -n 1)"
    log "Emulator:    $(emulator -version 2>&1 | head -n 1)"
    log "AVDs:"
    avdmanager list avd || true
    log "Required packages:"
    sdkmanager --sdk_root="$ANDROID_SDK_ROOT" --list_installed 2>/dev/null | grep -E \
        "platform-tools|emulator|platforms;android-${API_LEVEL}|build-tools;${BUILD_TOOLS_VERSION}|system-images;android-${API_LEVEL}" || true

    if [[ -x "$VENV_DIR/bin/python3" ]]; then
        log "Python/Frida:"
        "$VENV_DIR/bin/python3" -c 'import frida; print(frida.__version__)' || true
        "$VENV_DIR/bin/frida" --version || true
    fi

    if avd_exists; then
        local config="$AVD_DIR/${AVD_NAME}.avd/config.ini"
        log "AVD configuration ($config):"
        grep -E 'avd.ini.displayname|disk.dataPartition.size|hw.keyboard|hw.gpu.enabled|showDeviceFrame|fastboot.forceColdBoot|snapshot.present' "$config" || true
    fi
}

# ============================================================
# Full setup
# ============================================================

full_setup() {
    detect_os
    cleanup_stale_runtime_files
    install_prerequisites
    configure_sdk_directories
    install_cmdline_tools
    export PATH="$CMDLINE_TOOLS_DIR/bin:$PLATFORM_TOOLS_DIR:$EMULATOR_DIR:$PATH"
    accept_licenses
    sdk_install
    create_avd
    configure_avd

    # rootAVD needs a live ADB-connected emulator to generate and install
    # Magisk. It shuts that temporary session down after patching; the
    # configure_rootavd flow then boots the patched image for verification.
    start_emulator
    install_rootavd
    configure_rootavd

    start_emulator
    verify_adb
    install_python_packages
    install_frida_server

    # Capture a known-good analysis baseline for later restore operations.
    snapshot_save "$SNAPSHOT_NAME"
    stop_emulator

    log "============================================================"
    log "Android analysis environment setup completed"
    log "AVD:       $AVD_NAME"
    log "Snapshot:  $SNAPSHOT_NAME"
    log "Python:    $VENV_DIR"
    log "============================================================"
}

usage() {
    cat <<USAGE
Usage:
  $0 setup
  $0 start
  $0 stop
  $0 restart
  $0 snapshot-save [name]
  $0 snapshot-load [name]
  $0 snapshot-list
  $0 install-apk /path/to/app.apk
  $0 frida-start
  $0 frida-stop
  $0 frida-status
  $0 verify

Recommended workflow:
  FRESH_AVD=1 $0 setup
  $0 start
  $0 install-apk sample.apk
  $0 frida-start
  $0 snapshot-save after-install
  $0 stop
  $0 snapshot-load after-install

To preserve the AVD and snapshots across separate task1.sh invocations:
  FRESH_AVD=0 $0 setup
USAGE
}

main() {
    local command="${1:-setup}"
    case "$command" in
        setup) full_setup ;;
        start)
            detect_os
            configure_sdk_directories
            start_emulator
            verify_adb
            ;;
        stop)
            detect_os
            configure_sdk_directories
            stop_emulator
            ;;
        restart)
            detect_os
            configure_sdk_directories
            restart_emulator
            verify_adb
            ;;
        snapshot-save)
            detect_os
            configure_sdk_directories
            snapshot_save "${2:-$SNAPSHOT_NAME}"
            ;;
        snapshot-load)
            detect_os
            configure_sdk_directories
            snapshot_load "${2:-$SNAPSHOT_NAME}"
            verify_adb
            ;;
        snapshot-list)
            detect_os
            configure_sdk_directories
            snapshot_list
            ;;
        install-apk)
            detect_os
            configure_sdk_directories
            install_apk "${2:-}"
            ;;
        frida-start)
            detect_os
            configure_sdk_directories
            frida_start
            ;;
        frida-stop)
            detect_os
            configure_sdk_directories
            frida_stop
            ;;
        frida-status)
            detect_os
            configure_sdk_directories
            frida_status
            ;;
        verify)
            verify_installation
            if find_emulator_serial 2>/dev/null; then verify_adb; fi
            ;;
        help|-h|--help) usage ;;
        *) usage; die "Unknown command: $command" ;;
    esac
}

main "$@"
