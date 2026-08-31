# Contributing to weewx-reservoir

Thanks for taking the time to contribute! This is a small project, so the
process is light — but a few things keep it maintainable.

By participating you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Before you open an issue

Please do the basic troubleshooting first:

1. Confirm you are on **WeeWX 5.x** and the latest release of this extension.
2. Check the reading directly at
   `https://waterservices.usgs.gov/nwis/iv/?sites=<your-site>&siteStatus=all&format=rdb`
   to rule out the site, the parameter codes, or a frozen feed.
3. Run an archive cycle with `debug = 1` set in `weewx.conf` and read the
   WeeWX log for the `weewx-reservoir` lines.
4. Search [existing issues](https://github.com/ziti/weewx-reservoir/issues).

When you open a bug report, the issue form will ask for your WeeWX version,
extension version, OS, your USGS site ID, your `[Reservoir]` config, and the
relevant log lines. Please fill it in — issues without this information usually
can't be acted on. USGS site IDs and the Water Services API are public, so
there is nothing to redact here.

---

## Development setup

```bash
git clone https://github.com/ziti/weewx-reservoir.git
cd weewx-reservoir
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the checks that CI runs:

```bash
ruff check .                              # lint
python -m compileall -q bin install.py
pytest -q                                # unit tests
```

The unit tests stub WeeWX at import time, so they run anywhere. CI
additionally imports the module against a real WeeWX install.

---

## Coding standard

Python code follows **[PEP 8](https://peps.python.org/pep-0008/)**, enforced by
[`ruff`](https://docs.astral.sh/ruff/) using the configuration in
`pyproject.toml` (line length 100; `E`, `F`, `W`, `I`, `B`, `UP`, `SIM`
rule sets). `ruff check .` must pass with no warnings.

Additionally:

- **Configuration over constants.** Anything a user might reasonably want to
  change belongs in `[Reservoir]` in `weewx.conf`, read via `config_dict`,
  with a sensible default. Don't hard-code site IDs, intervals, or timeouts.
- **Never crash the engine.** `new_archive_record` must not let an exception
  escape — a bad response or a network error logs and returns, leaving the
  record untouched. WeeWX would stop archiving if an unhandled exception got
  out.
- **Keep runtime dependencies minimal.** Standard library, WeeWX, and
  `requests` only. If you think you need another third-party package, open an
  issue to discuss first.
- Keep functions small and prefer pure helpers (like `parse_usgs_rdb`) that
  are easy to test.
- Add or update docstrings for anything non-obvious.

### Secure coding

- The USGS Water Services API needs no credentials; don't add auth, and don't
  put anything secret in `[Reservoir]`.
- Build requests with `params=` — never interpolate values into a URL or a
  shell.
- Treat the RDB response as untrusted input: locate columns by their
  parameter-code suffix, cast defensively, and skip non-numeric sentinels
  (`Ice`, `Eqp`, …) rather than raising.

---

## Tests

Every behavioural change needs unit tests:

- New config options: cover the default, an override, and a bad value.
- New failure modes: assert the record is left unchanged and that nothing
  propagates out of `new_archive_record`.
- Bug fixes: add a test that fails before your fix and passes after.

---

## Commit messages

This project uses **[Conventional Commits](https://www.conventionalcommits.org/)**.
Describe the *change in behaviour*, not the files touched.

```
feat: add configurable USGS parameter -> observation mapping
fix: reuse cached reading when the feed returns an empty data set
docs: document max_reading_age and the frozen-feed guard
test: cover the 'enabled' config alias
ci: run the test matrix on Python 3.13
refactor: extract reading-time parsing into _parse_observed()
chore: bump ruff to 0.7
```

- Good: `fix: use the newest RDB data row, not the first`
- Avoid: `update reservoir.py` / `fixes` / `misc changes`

Breaking changes get a `!` and a `BREAKING CHANGE:` footer.

---

## Pull requests

Open PRs against `main`. The PR description (there is a template) should cover:

1. **Why** the change is needed — the problem, not just the diff.
2. **Linked issue** — write `Closes #123` so the issue closes on merge.
3. **Config changes** — list any new/renamed/removed options, their defaults,
   and confirm `README.md` and `CHANGELOG.md` are updated.
4. **Tests** — what you added and that `ruff` + `pytest` pass locally.
5. **Compatibility** — note anything that affects existing `weewx.conf`
   setups, the database schema, or requires a WeeWX version bump.

Keep PRs focused on one thing. Unrelated cleanups belong in their own PR.

### Releases (maintainers)

1. Update `VERSION` in `bin/user/reservoir.py`, `VERSION` in `install.py`,
   and add a dated section to `CHANGELOG.md`.
2. Commit (`chore(release): 1.2.0`), then tag `v1.2.0` and push the tag.
3. The release workflow checks the versions agree, builds
   `weewx-reservoir-1.2.0.zip`, and creates the GitHub Release with notes
   taken from the changelog.
