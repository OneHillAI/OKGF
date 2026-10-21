# Security Policy

OKGF is a specification plus a small reference validator. The security surface is limited, but two areas
matter and we take reports on both.

## Scope

- **The reference validator** (the [`okgf/`](okgf/) package, run as the `okgf` command) - parsing
  untrusted bundles (YAML, tar-free but file I/O), and signature verification. A bug that lets a malformed
  bundle crash, hang, or mislead the validator is in scope.
- **The trust model in the spec** - the `x-okgf-signature` scheme and the conformance rules. If you
  find a way a page could be treated as trusted when it should not be (or vice versa), that is a spec-level
  security issue and we want to hear it.

Out of scope: vulnerabilities in tools that *implement* OKGF (report those to the implementation's own
project).

## Reporting

Email **dev@onehill.org** with a description and, if possible, a minimal reproducing bundle. Please do
not open a public issue for a security report.

You can also use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository.

We aim to acknowledge a report within a few business days and will keep you updated as we assess and fix.
