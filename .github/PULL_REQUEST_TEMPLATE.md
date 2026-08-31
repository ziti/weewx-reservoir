<!--
Conventional Commit title, e.g.:
  feat: add configurable USGS parameter -> observation mapping
  fix: use the newest RDB data row, not the first
Describe the change in behaviour, not the files touched.
-->

## Why

<!-- The problem this solves. What was wrong or missing? -->

## What changed

<!-- A short summary of the approach. -->

## Related issues

<!-- "Closes #123" so the issue closes on merge. Use "Refs #123" if it only relates. -->
Closes #

## Configuration changes

<!-- Delete if none. Otherwise list each option: name, default, and confirm
     README.md + CHANGELOG.md are updated. -->
- [ ] No config changes
- [ ] New/changed options documented in `README.md`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`

## Checklist

- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] `ruff check .` passes
- [ ] `pytest -q` passes; new behaviour has unit tests (default, override, bad value)
- [ ] No hard-coded site IDs / intervals / timeouts — new knobs read from `[Reservoir]` with defaults
- [ ] `new_archive_record` still can't raise; a bad or hostile USGS response leaves the record unchanged
- [ ] Backwards compatible with existing `weewx.conf` setups and the DB schema (or the break is called out below)

## Compatibility notes

<!-- Anything users must change when upgrading, a required WeeWX version bump,
     or new columns to add with `weectl database add-column`. -->
