<!-- Thanks for contributing to OKGF. Keep PRs focused on one change. -->

## What and why

<!-- What does this change, and what problem does it solve? Link the issue if there is one. -->

## Checklist

- [ ] The change keeps OKGF a strict superset of OKF (governance stays in `x-okgf-*`; bundles remain
      valid OKF).
- [ ] `python -m pytest tests/ -q` passes.
- [ ] The example bundles still validate (`--strict`), and any new example passes the validator.
- [ ] New or changed behaviour has a test.
- [ ] No em/en dashes in Markdown or Python (CI rejects them).
- [ ] Commits are signed off (`git commit -s`), per [CONTRIBUTING.md](../CONTRIBUTING.md) (DCO).
