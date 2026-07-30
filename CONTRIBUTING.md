# Contributing to OKGF

Thanks for helping improve the Open Knowledge and Governance Format. OKGF is an open specification
stewarded by the OneHill Foundation. This repo holds the spec, the conformance definition, examples, and
the reference validator.

## What contributions look like

- **Spec clarifications or fixes** - wording, ambiguities, or errors in `SPEC.md` / `CONFORMANCE.md`.
- **New or improved examples** - sample bundles under `examples/` that show a real pattern.
- **Validator improvements** - bug fixes or checks in `tools/okgf_validate.py`, with tests.
- **Proposed field or lifecycle changes** - larger changes to the governance model. Open an issue first
  (see below) so we can discuss before you write it.

Because OKGF is a superset of [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog), a change
must not break OKF conformance.

## Proposing a change

1. **Open an issue** describing the problem or idea. For anything beyond a wording fix, agree on the
   direction in the issue before writing a PR.
2. **Branch and make the change.** Keep PRs focused on one thing.
3. **Run the checks locally:**
   ```sh
   pip install -r requirements-dev.txt
   python -m pytest tests/ -q
   python tools/okgf_validate.py --strict examples/minimal
   python tools/okgf_validate.py --strict --pubkey examples/governed/ORG_PUBKEY.pem examples/governed
   ```
   New or changed behaviour needs a test. New example bundles must pass the validator (CI enforces this).
4. **Open a pull request** against `main`. CI runs the validator and the test suite on every PR.

## Style

- Plain ASCII in Markdown and Python: no em dashes or en dashes (use `-`). CI rejects them.
- Match the surrounding tone: concise and direct.

## Sign your work (DCO)

Contributions are accepted under a **Developer Certificate of Origin (DCO)**: your contribution is
licensed to the project under its outbound license (**Apache-2.0**; see `LICENSE`). There is no separate
copyright assignment.

You certify the [DCO 1.1](https://developercertificate.org/) by adding a `Signed-off-by` line to each
commit, matching your real name and email:

```
Signed-off-by: Your Name <you@example.com>
```

`git commit -s` adds it automatically. By signing off you state that you wrote the contribution or
otherwise have the right to submit it under Apache-2.0.

## License of contributions

By contributing you agree that your contribution is licensed under **Apache-2.0**, the same license as the
rest of this repository. Software that *implements* OKGF is licensed separately by its own project; that is independent of this spec's license.
