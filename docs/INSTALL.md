# Installing the OKGF validator

The reference validator ships as a small Python package named `okgf`. Installing it gives you an
`okgf` command for validating OKGF pages and bundles. The validator depends only on PyYAML;
cryptographic signature verification is an optional extra.

## One-line install (recommended)

No system Python required - this uses [uv](https://docs.astral.sh/uv/) to manage an isolated Python
for the tool:

```sh
curl -fsSL https://raw.githubusercontent.com/OneHillAI/okgf/main/install.sh | sh
```

To also enable Ed25519 signature verification, set `OKGF_VERIFY=1`:

```sh
curl -fsSL https://raw.githubusercontent.com/OneHillAI/okgf/main/install.sh | OKGF_VERIFY=1 sh
```

Prefer to read before you run? The script is short: [`install.sh`](../install.sh). It falls back to
`pipx`, and installs `uv` only if neither `uv` nor `pipx` is present.

## Homebrew (macOS / Linux)

```sh
brew install OneHillAI/tap/okgf
```

## With pip, pipx, or uv

If you already manage Python environments, install from PyPI directly:

```sh
pipx install okgf           # isolated, recommended for a CLI
uv tool install okgf        # same idea, via uv
python -m pip install okgf  # into the current environment
```

Add signature verification with the `verify` extra:

```sh
pipx install "okgf[verify]"
```

## Verify the install

```sh
okgf --version
okgf --strict path/to/bundle
okgf --strict --pubkey path/to/ORG_PUBKEY.pem path/to/bundle   # verify signatures
```

`python -m okgf ...` works identically to the `okgf` command.

## Optional: signature verification

Signature checks need the [`cryptography`](https://cryptography.io/) package, pulled in by the
`verify` extra (`OKGF_VERIFY=1` for the one-line installer, or `pip install 'okgf[verify]'`). Without
it, a page that carries an `x-okgf-signature` is still format-checked, but reported as unverified
rather than trusted - the validator never claims a signature is valid when it cannot check it.

## From a source checkout

Working on the validator itself, or want to run it without installing?

```sh
git clone https://github.com/OneHillAI/okgf.git
cd okgf
python -m pip install -e ".[dev]"   # editable install with test + verify extras
okgf --strict examples/minimal
python -m pytest tests/ -q
```

The historical entry point `python tools/okgf_validate.py ...` still works from a checkout: it is a
thin shim that re-exports the package, kept so older scripts and docs do not break.
