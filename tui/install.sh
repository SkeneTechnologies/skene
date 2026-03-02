#!/usr/bin/env bash
set -euo pipefail

REPO="Px8-fi/skene-cli"
BINARY="skene"
INSTALL_DIR="/usr/local/bin"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || err "'$1' is required but not installed."
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
    x86_64|amd64)   ARCH=amd64 ;;
    arm64|aarch64)   ARCH=arm64 ;;
    *)               err "Unsupported architecture: $ARCH" ;;
  esac
}

# ---------------------------------------------------------------------------
# Resolve latest version (or use VERSION env override)
# ---------------------------------------------------------------------------

resolve_version() {
  if [ -n "${VERSION:-}" ]; then
    TAG="$VERSION"
    return
  fi

  need curl
  TAG=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
        | grep '"tag_name"' | head -1 | sed -E 's/.*"([^"]+)".*/\1/')

  [ -n "$TAG" ] || err "Could not determine latest release. Set VERSION=vXXX manually."
}

# ---------------------------------------------------------------------------
# Download & install
# ---------------------------------------------------------------------------

install_binary() {
  local asset="${BINARY}-${OS}-${ARCH}"
  local url="https://github.com/${REPO}/releases/download/${TAG}/${asset}.tar.gz"
  local tmpdir
  tmpdir="$(mktemp -d)"

  info "Downloading ${BINARY} ${TAG} for ${OS}/${ARCH}…"
  curl -fSL --progress-bar -o "${tmpdir}/${asset}.tar.gz" "$url" \
    || err "Download failed. Check that release ${TAG} exists at https://github.com/${REPO}/releases"

  tar -xzf "${tmpdir}/${asset}.tar.gz" -C "$tmpdir"
  chmod +x "${tmpdir}/${asset}"

  # macOS Gatekeeper bypass
  if [ "$OS" = "darwin" ]; then
    xattr -d com.apple.quarantine "${tmpdir}/${asset}" 2>/dev/null || true
    # Ad-hoc code sign so Gatekeeper treats it as a known binary
    codesign --force --sign - "${tmpdir}/${asset}" 2>/dev/null || true
  fi

  info "Installing to ${INSTALL_DIR}/${BINARY} …"
  if [ -w "$INSTALL_DIR" ]; then
    mv "${tmpdir}/${asset}" "${INSTALL_DIR}/${BINARY}"
  else
    sudo mv "${tmpdir}/${asset}" "${INSTALL_DIR}/${BINARY}"
  fi

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

verify() {
  if command -v "$BINARY" >/dev/null 2>&1; then
    info "Installed successfully! Run \`${BINARY}\` to get started."
  else
    info "Binary installed to ${INSTALL_DIR}/${BINARY}."
    info "Make sure ${INSTALL_DIR} is in your PATH."
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  info "Skene CLI Installer"
  detect_platform
  resolve_version
  install_binary
  verify
}

main
