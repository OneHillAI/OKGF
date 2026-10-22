#!/bin/sh
# OKGF validator installer.
#
# Installs the `okgf` command. No system Python required: this prefers uv, which manages an isolated
# Python for the tool. Usage:
#
#   curl -fsSL https://raw.githubusercontent.com/OneHillAI/okgf/main/install.sh | sh
#
# Options (environment variables):
#   OKGF_VERIFY=1   also install the `verify` extra (Ed25519 signature verification via cryptography)
#
# This is a thin convenience wrapper around a normal PyPI install. If you already manage Python
# environments, `pip install okgf` (or `pipx install okgf`, or `uv tool install okgf`) does the same.
set -eu

PKG="okgf"
if [ "${OKGF_VERIFY:-0}" = "1" ]; then
    PKG="okgf[verify]"
fi

info() { printf 'okgf-install: %s\n' "$1" >&2; }

install_with_uv() {
    info "installing $PKG with uv"
    uv tool install --force "$PKG"
}

if command -v uv >/dev/null 2>&1; then
    install_with_uv
elif command -v pipx >/dev/null 2>&1; then
    info "uv not found; installing $PKG with pipx"
    pipx install --force "$PKG"
else
    info "installing uv (https://astral.sh/uv) to manage the install"
    curl -fsSL https://astral.sh/uv/install.sh | sh
    # Make uv available on PATH for the rest of this script.
    if [ -r "${XDG_CONFIG_HOME:-$HOME/.config}/uv/env" ]; then
        # shellcheck disable=SC1091
        . "${XDG_CONFIG_HOME:-$HOME/.config}/uv/env"
    fi
    PATH="$HOME/.local/bin:$PATH"
    export PATH
    install_with_uv
fi

if command -v okgf >/dev/null 2>&1; then
    info "installed: $(okgf --version)"
    info "try: okgf --strict path/to/bundle"
else
    info "installed, but 'okgf' is not on your PATH yet."
    info "add your tool bin directory to PATH (uv uses ~/.local/bin) and reopen your shell."
fi
