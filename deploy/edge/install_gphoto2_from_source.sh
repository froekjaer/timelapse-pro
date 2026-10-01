#!/usr/bin/env bash
# Build and install pinned, signature-verified libgphoto2 + gphoto2 from source
# into /usr/local on an Ubuntu 22.04 (Jammy) Edge or in the Edge image build.
#
# Why (Peter, 2026-10-01): Jammy ships libgphoto2 2.5.27, which does not know
# the Nikon Z30 (added in 2.5.30) and falls back to "USB PTP Class Camera".
# 2.5.34 also fixes CVE-2026-40333/40334/40335 in the PTP parser.
#
#   sudo install_gphoto2_from_source.sh                      # install / repair
#   sudo install_gphoto2_from_source.sh --remove-build-deps  # image build: drop -dev pkgs afterwards
#   install_gphoto2_from_source.sh --check                   # read-only verification
#   sudo install_gphoto2_from_source.sh --build-artifact OUT.tar.gz   # Headend build host (arm64 Jammy container)
#   sudo install_gphoto2_from_source.sh --install-artifact FILE SHA256  # Edge: no apt, no internet
#
# Edges never install software from the internet (inject_edge_image.py): on a
# field Edge use --install-artifact with a tarball built on the Headend; the
# download/build modes are for the image build and the Headend build host.
#
# Tarballs are pinned by SHA256. Those hashes were taken from tarballs whose
# detached GPG signatures verified against the gphoto maintainer key
# 7C4A FD61 D8AA E757 0796  A517 2209 D690 2F96 9C95 (Marcus Meißner) on
# 2026-10-01; see Dokumentation/HANDOVER_LOG.md.
set -euo pipefail

LIBGPHOTO2_VERSION="2.5.34"
LIBGPHOTO2_SHA256="51993f5d9bfb6b4e5925cbbe5883085791bff6f81bcacb8ffe1b783ce76d586a"
GPHOTO2_VERSION="2.5.32"
GPHOTO2_SHA256="be08a449bbed9613bc9db105997c4ba71410d41870496420359a99b37502c406"
PREFIX="/usr/local"
SRC_BASE="${GPHOTO2_SRC_BASE:-https://github.com/gphoto}"

BUILD_DEPS="gcc make pkg-config libc6-dev libusb-1.0-0-dev libexif-dev libltdl-dev libpopt-dev libjpeg-dev libreadline-dev"
RUNTIME_LIBS="libusb-1.0-0 libexif12 libltdl7 libpopt0 libjpeg8 libreadline8"

log() { printf '[gphoto2-src] %s\n' "$*"; }
die() { printf '[gphoto2-src] FEJL: %s\n' "$*" >&2; exit 1; }

check() {
    local rc=0 bin ver
    bin="$(command -v gphoto2 || true)"
    [[ "$bin" == "${PREFIX}/bin/gphoto2" ]] && log "gphoto2 i PATH: ${bin} ✓" || { log "gphoto2 i PATH er '${bin}', forventet ${PREFIX}/bin/gphoto2"; rc=1; }
    ver="$("${PREFIX}/bin/gphoto2" --version 2>/dev/null | awk '$1=="libgphoto2"{print $2; exit}')"
    [[ "$ver" == "$LIBGPHOTO2_VERSION" ]] && log "libgphoto2 ${ver} ✓" || { log "libgphoto2 er '${ver}', forventet ${LIBGPHOTO2_VERSION}"; rc=1; }
    "${PREFIX}/bin/gphoto2" --version 2>/dev/null | head -1 | grep -q "gphoto2 ${GPHOTO2_VERSION}" && log "gphoto2 ${GPHOTO2_VERSION} ✓" || { log "gphoto2-version afviger"; rc=1; }
    ldd "${PREFIX}/bin/gphoto2" 2>/dev/null | grep -q "${PREFIX}/lib/libgphoto2.so" && log "linker mod ${PREFIX}/lib/libgphoto2 ✓" || { log "gphoto2 linker IKKE mod ${PREFIX}/lib/libgphoto2"; rc=1; }
    # Capture first: `cmd | grep -q` under pipefail fails when grep exits early (SIGPIPE).
    local cams; cams="$("${PREFIX}/bin/gphoto2" --list-cameras 2>/dev/null || true)"
    grep -q '"Nikon Z30"' <<<"$cams" && log "kender Nikon Z30 ✓" || { log "kender IKKE Nikon Z30"; rc=1; }
    return $rc
}

# Files that make up the installation (relative to /), used by the artifact modes.
ARTIFACT_PATHS="usr/local/bin/gphoto2 usr/local/lib/libgphoto2.so* usr/local/lib/libgphoto2_port.so* usr/local/lib/libgphoto2 usr/local/lib/libgphoto2_port usr/local/share/libgphoto2 usr/local/share/libgphoto2_port"

post_install() { # udev rules/hwdb from the new library + remove distro gphoto2 — shared by all modes
    ldconfig
    local pcl="${PREFIX}/lib/libgphoto2/print-camera-list"
    if [[ -x "$pcl" ]]; then
        mkdir -p /etc/udev/rules.d /etc/udev/hwdb.d   # absent in containers / image builds
        LD_LIBRARY_PATH="${PREFIX}/lib" "$pcl" udev-rules version 201 group plugdev mode 0664 \
            > /etc/udev/rules.d/60-libgphoto2-local.rules
        LD_LIBRARY_PATH="${PREFIX}/lib" "$pcl" hwdb > /etc/udev/hwdb.d/20-libgphoto2-local.hwdb
        grep -q "libgphoto2 *${LIBGPHOTO2_VERSION}" /etc/udev/rules.d/60-libgphoto2-local.rules \
            || die "udev-regler blev ikke genereret af libgphoto2 ${LIBGPHOTO2_VERSION}"
        if command -v systemd-hwdb >/dev/null; then systemd-hwdb update 2>/dev/null || true; fi
        if command -v udevadm >/dev/null; then udevadm control --reload-rules 2>/dev/null || true; fi
        log "udev-regler + hwdb skrevet fra libgphoto2 ${LIBGPHOTO2_VERSION}"
    fi
    if dpkg -s gphoto2 >/dev/null 2>&1; then
        dpkg --remove gphoto2 >/dev/null 2>&1 && log "distro-pakken gphoto2 (2.5.27-CLI) fjernet"
    fi
    if dpkg -s libgphoto2-6 >/dev/null 2>&1; then
        local would
        would="$(apt-get remove --simulate libgphoto2-6 libgphoto2-port12 2>/dev/null | awk '/^Remv /{print $2}' | grep -v -E '^libgphoto2' || true)"
        if [[ -z "$would" ]]; then
            dpkg --remove libgphoto2-6 libgphoto2-port12 libgphoto2-l10n >/dev/null 2>&1 || dpkg --remove libgphoto2-6 libgphoto2-port12 >/dev/null 2>&1 || true
            dpkg -s libgphoto2-6 >/dev/null 2>&1 || log "distro-biblioteket libgphoto2-6 (2.5.27) fjernet"
        else
            log "distro-libgphoto2-6 bevares (krævet af: $(echo $would | tr '\n' ' ')); gphoto2 bruger ${PREFIX} via rpath"
        fi
    fi
}

MODE="install"; REMOVE_BUILD_DEPS=0; ARTIFACT=""; ARTIFACT_SHA256=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --check) MODE="check" ;;
        --remove-build-deps) REMOVE_BUILD_DEPS=1 ;;
        --build-artifact) MODE="build-artifact"; ARTIFACT="${2:?sti til output .tar.gz}"; shift ;;
        --install-artifact) MODE="install-artifact"; ARTIFACT="${2:?sti til artefakt}"; ARTIFACT_SHA256="${3:?forventet SHA256}"; shift 2 ;;
        *) die "ukendt argument: $1" ;;
    esac
    shift
done
if [[ "$MODE" == check ]]; then check; exit $?; fi
[[ "$(id -u)" == 0 ]] || die "kør som root (sudo)"

if [[ "$MODE" == install-artifact ]]; then
    # Field Edge: no apt, no internet. Runtime libs come with Jammy's
    # libgphoto2-6/gphoto2 dependencies; refuse rather than half-install.
    echo "${ARTIFACT_SHA256}  ${ARTIFACT}" | sha256sum -c --quiet - || die "SHA256 matcher ikke for ${ARTIFACT}"
    missing=""
    for lib in libusb-1.0.so.0 libexif.so.12 libltdl.so.7 libpopt.so.0 libjpeg.so.8 libreadline.so.8; do
        ldconfig -p | grep -q "$lib" || missing="$missing $lib"
    done
    [[ -z "$missing" ]] || die "runtime-biblioteker mangler:${missing} — kan ikke installere uden apt"
    tar -C / -xzf "$ARTIFACT" --no-same-owner
    log "artefakt udpakket til ${PREFIX}"
    post_install
    check || die "verifikation fejlede"
    log "FÆRDIG: libgphoto2 ${LIBGPHOTO2_VERSION} + gphoto2 ${GPHOTO2_VERSION} i ${PREFIX} (artefakt)"
    exit 0
fi

export DEBIAN_FRONTEND=noninteractive
log "installerer build-afhængigheder og runtime-biblioteker…"
apt-get update -qq
# shellcheck disable=SC2086
apt-get install -y -qq --no-install-recommends ca-certificates curl xz-utils $BUILD_DEPS $RUNTIME_LIBS >/dev/null
# Keep runtime libs when -dev packages are removed later.
# shellcheck disable=SC2086
apt-mark manual $RUNTIME_LIBS >/dev/null

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
BUILD_LOG="${WORK}/build.log"
run_logged() { # run a build step, keep its output out of the terminal unless it fails
    if ! "$@" >>"$BUILD_LOG" 2>&1; then
        tail -40 "$BUILD_LOG" >&2; die "byggetrin fejlede: $*"
    fi
}
fetch() { # name version sha256
    local url="${SRC_BASE}/$1/releases/download/v$2/$1-$2.tar.xz"
    log "henter $1 $2"
    curl -fsSL --retry 3 -o "${WORK}/$1-$2.tar.xz" "$url"
    echo "$3  ${WORK}/$1-$2.tar.xz" | sha256sum -c --quiet - || die "SHA256 matcher ikke for $1-$2 — afbryder"
    tar -C "$WORK" -xJf "${WORK}/$1-$2.tar.xz"
}
fetch libgphoto2 "$LIBGPHOTO2_VERSION" "$LIBGPHOTO2_SHA256"
fetch gphoto2 "$GPHOTO2_VERSION" "$GPHOTO2_SHA256"

JOBS="$(nproc 2>/dev/null || echo 2)"
log "bygger libgphoto2 ${LIBGPHOTO2_VERSION} (-j${JOBS})…"
cd "${WORK}/libgphoto2-${LIBGPHOTO2_VERSION}"
run_logged ./configure --prefix="$PREFIX" --disable-static --with-camlibs=standard
run_logged make -j"$JOBS"
run_logged make install
cd /
ldconfig
log "bygger gphoto2 ${GPHOTO2_VERSION}…"
# rpath: the CLI must load /usr/local's libgphoto2 even if Jammy's
# libgphoto2-6 stays installed for other packages.
cd "${WORK}/gphoto2-${GPHOTO2_VERSION}"
run_logged env PKG_CONFIG_PATH="${PREFIX}/lib/pkgconfig" LDFLAGS="-Wl,-rpath,${PREFIX}/lib" ./configure --prefix="$PREFIX"
run_logged make -j"$JOBS"
run_logged make install
cd /
ldconfig

post_install

if [[ "$REMOVE_BUILD_DEPS" == 1 ]]; then
    # shellcheck disable=SC2086
    apt-get remove -y -qq $BUILD_DEPS >/dev/null || true
    rm -rf /var/lib/apt/lists/*
    log "build-afhængigheder fjernet"
fi

check || die "verifikation fejlede"
if [[ "$MODE" == build-artifact ]]; then
    # shellcheck disable=SC2086
    (cd / && tar -czf "$ARTIFACT" $ARTIFACT_PATHS)
    log "artefakt: ${ARTIFACT} sha256=$(sha256sum "$ARTIFACT" | awk '{print $1}')"
fi
log "FÆRDIG: libgphoto2 ${LIBGPHOTO2_VERSION} + gphoto2 ${GPHOTO2_VERSION} i ${PREFIX}"
