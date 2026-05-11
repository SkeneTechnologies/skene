#!/usr/bin/env bash
set -euo pipefail

REPO="SkeneTechnologies/skene"
BINARY="skene"
# Only releases whose tag starts with this prefix are considered TUI releases.
TAG_PREFIX="tui-v"
# Set by resolve_install_dir(); override with SKENE_INSTALL_DIR.
INSTALL_DIR=""
# Set by mktemp; cleaned up via trap.
TMPDIR_INSTALL=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWarn:\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || err "'$1' is required but not installed."
}

cleanup() {
  [ -n "$TMPDIR_INSTALL" ] && [ -d "$TMPDIR_INSTALL" ] && rm -rf "$TMPDIR_INSTALL"
}
trap cleanup EXIT INT TERM

# Hardened curl: enforce HTTPS, minimum TLS, fail on HTTP errors, follow redirects.
curl_get() {
  curl --proto '=https' --tlsv1.2 -fsSL "$@"
}

# ---------------------------------------------------------------------------
# Install location (no sudo when possible)
# ---------------------------------------------------------------------------
#
# Priority:
#   1. SKENE_INSTALL_DIR — explicit destination directory for the binary
#   2. /usr/local/bin — if writable by this user (no sudo)
#   3. $HOME/.local/bin — user-local, mkdir -p, no sudo

resolve_install_dir() {
  if [ -n "${SKENE_INSTALL_DIR:-}" ]; then
    INSTALL_DIR="$SKENE_INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    return
  fi

  local system_bin="/usr/local/bin"
  if [ -d "$system_bin" ] && [ -w "$system_bin" ]; then
    INSTALL_DIR="$system_bin"
    return
  fi

  [ -n "${HOME:-}" ] || err "HOME is not set; set SKENE_INSTALL_DIR or export HOME."
  INSTALL_DIR="${HOME}/.local/bin"
  mkdir -p "$INSTALL_DIR"
}

# ---------------------------------------------------------------------------
# Detect OS / Arch
# ---------------------------------------------------------------------------

detect_platform() {
  OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
  ARCH="$(uname -m)"

  case "$OS" in
    linux)  OS=linux ;;
    darwin) OS=darwin ;;
    *)      err "Unsupported OS: $OS" ;;
  esac

  case "$ARCH" in
    x86_64|amd64)  ARCH=amd64 ;;
    arm64|aarch64) ARCH=arm64 ;;
    *)             err "Unsupported architecture: $ARCH" ;;
  esac
}

# ---------------------------------------------------------------------------
# Resolve TUI release tag
# ---------------------------------------------------------------------------
#
# This repo publishes three tag families (v*, tui-v*, skills-v*). We only
# care about tui-v*. Selection order:
#   1. SKENE_VERSION env (full tag, e.g. tui-v0.4.0 — "tui-v" prefix is added
#      if a bare version like "0.4.0" or "v0.4.0" is given)
#   2. VERSION env (deprecated alias for SKENE_VERSION)
#   3. Latest non-prerelease tui-v* release from the GitHub API

normalize_tag() {
  local v="$1"
  case "$v" in
    "${TAG_PREFIX}"*) printf '%s' "$v" ;;
    v*)               printf '%s%s' "${TAG_PREFIX%v}" "$v" ;;
    *)                printf '%s%s' "$TAG_PREFIX" "$v" ;;
  esac
}

resolve_version() {
  if [ -n "${SKENE_VERSION:-}" ]; then
    TAG="$(normalize_tag "$SKENE_VERSION")"
    return
  fi
  if [ -n "${VERSION:-}" ]; then
    warn "VERSION is deprecated; use SKENE_VERSION instead."
    TAG="$(normalize_tag "$VERSION")"
    return
  fi

  need curl
  local api_url="https://api.github.com/repos/${REPO}/releases?per_page=30"
  local response
  response="$(curl_get -H 'Accept: application/vnd.github+json' "$api_url")" \
    || err "Failed to query GitHub releases API."

  TAG="$(
    printf '%s' "$response" \
      | grep -E '"(tag_name|prerelease)"' \
      | awk -F': ' '
          /"tag_name"/   { gsub(/[",]/,"",$2); tag=$2; next }
          /"prerelease"/ { gsub(/[",]/,"",$2); pre=$2;
                           if (tag ~ /^tui-v/ && pre == "false") { print tag; exit } }
        '
  )"

  [ -n "$TAG" ] || err "Could not determine latest tui-v* release. Set SKENE_VERSION=tui-vX.Y.Z manually."
}

# ---------------------------------------------------------------------------
# Download, verify, install
# ---------------------------------------------------------------------------

sha256_check() {
  local file="$1" expected="$2" actual
  if command -v sha256sum >/dev/null 2>&1; then
    actual="$(sha256sum "$file" | awk '{print $1}')"
  elif command -v shasum >/dev/null 2>&1; then
    actual="$(shasum -a 256 "$file" | awk '{print $1}')"
  else
    err "Neither sha256sum nor shasum is available; cannot verify download integrity."
  fi
  [ "$actual" = "$expected" ] \
    || err "Checksum mismatch for $(basename "$file"): expected $expected, got $actual."
}

install_binary() {
  need curl
  need tar

  local asset="${BINARY}-${OS}-${ARCH}"
  local archive="${asset}.tar.gz"
  local base="https://github.com/${REPO}/releases/download/${TAG}"
  local url="${base}/${archive}"
  local checksums_url="${base}/checksums.txt"

  TMPDIR_INSTALL="$(mktemp -d)"

  info "Downloading ${BINARY} ${TAG} for ${OS}/${ARCH}…"
  curl_get --progress-bar -o "${TMPDIR_INSTALL}/${archive}" "$url" \
    || err "Download failed. Check that release ${TAG} exists at https://github.com/${REPO}/releases"

  # Verify checksum if the release publishes one. Older releases (< checksums.txt)
  # fall back to a warning so the installer still works for historical tags.
  if curl_get -o "${TMPDIR_INSTALL}/checksums.txt" "$checksums_url" 2>/dev/null; then
    local expected
    expected="$(awk -v f="$archive" '$2 == f || $2 == "*"f {print $1; exit}' \
                  "${TMPDIR_INSTALL}/checksums.txt")"
    [ -n "$expected" ] || err "checksums.txt does not contain an entry for ${archive}."
    sha256_check "${TMPDIR_INSTALL}/${archive}" "$expected"
    info "Checksum verified."
  else
    warn "No checksums.txt published for ${TAG}; skipping integrity check."
  fi

  tar -xzf "${TMPDIR_INSTALL}/${archive}" -C "$TMPDIR_INSTALL"
  chmod +x "${TMPDIR_INSTALL}/${asset}"

  if [ "$OS" = "darwin" ]; then
    xattr -d com.apple.quarantine "${TMPDIR_INSTALL}/${asset}" 2>/dev/null || true
    # Ad-hoc sign only if not already signed (preserve real signatures/notarization).
    if ! codesign -dv "${TMPDIR_INSTALL}/${asset}" >/dev/null 2>&1; then
      codesign --force --sign - "${TMPDIR_INSTALL}/${asset}" 2>/dev/null || true
    fi
  fi

  info "Installing to ${INSTALL_DIR}/${BINARY} …"
  if [ -w "$INSTALL_DIR" ]; then
    mv "${TMPDIR_INSTALL}/${asset}" "${INSTALL_DIR}/${BINARY}"
  else
    sudo mkdir -p "$INSTALL_DIR"
    sudo mv "${TMPDIR_INSTALL}/${asset}" "${INSTALL_DIR}/${BINARY}"
  fi
}

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

verify() {
  local installed="${INSTALL_DIR}/${BINARY}"
  case ":${PATH:-}:" in
    *":${INSTALL_DIR}:"*) ;;
    *)
      info "Add this directory to your PATH (then open a new terminal or \`source\` your profile):"
      printf '    export PATH="%s:$PATH"\n' "$INSTALL_DIR"
      ;;
  esac

  hash -r 2>/dev/null || true
  if command -v "$BINARY" >/dev/null 2>&1; then
    local resolved
    resolved="$(command -v "$BINARY")"
    if [ "$resolved" = "$installed" ]; then
      info "Installed successfully! Type \`${BINARY}\` and hit enter to get started."
    else
      info "Installed to ${installed}."
      warn "A different \`${BINARY}\` is resolved on PATH: ${resolved}"
      info "Adjust PATH or run the new binary with: ${installed}"
    fi
  else
    info "Binary installed to ${installed}."
    info "Make sure ${INSTALL_DIR} is in your PATH, then run \`${BINARY}\`."
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  info "Skene Installer"
  detect_platform
  resolve_version
  resolve_install_dir
  install_binary
  verify
}

main
