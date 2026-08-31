# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-08-31

### Added
- Response caching: the USGS feed is fetched at most once per
  `min_fetch_interval` seconds (default 900) and the reading is reused in
  between.
- Stale-feed guard: a reading whose own timestamp is older than
  `max_reading_age` seconds (default 3600) is skipped rather than pinned into
  the archive.
- Configurable HTTP `timeout` (default 10s).
- Accepts the older `enabled` config key as an alias for `enable`.
- Repo scaffolding: GPLv3 license, community-health files, `ruff` + `pytest`
  config, GitHub Actions CI, and a tag-driven release workflow.

### Changed
- RDB parsing uses the newest data row and parses its reading timestamp.
- Import `StdService` from `weewx.engine`.
- Build the request with `params=` instead of a hand-assembled query string.
- Narrower exception handling, with tracebacks logged for unexpected errors.
- `shutDown()` closes the HTTP session.

## [1.0.3] - 2026-05-19

### Changed
- Performance: reuse a single `requests` session, precompute the request URL,
  faster RDB parsing, and skip unit conversion when the systems already match.

## [1.0.2] - 2024-07-24

### Added
- Unit test suite and expanded documentation.

## [1.0.1] - 2024-07-24

### Fixed
- Assorted bug fixes.

## [1.0.0] - 2024-07-24

### Added
- Initial release. A `Reservoir` WeeWX data service that, on each archive
  interval, fetches the latest reading from the USGS Water Services
  instantaneous-values API for a configured site and merges
  `lakeSurfaceLevel` (`group_altitude`, USGS `62614`) and `lakePrecipitation`
  (`group_rain`, USGS `00045`) into the record.

[Unreleased]: https://github.com/ziti/weewx-reservoir/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/ziti/weewx-reservoir/releases/tag/v1.1.0
[1.0.3]: https://github.com/ziti/weewx-reservoir/releases/tag/v1.0.3
[1.0.2]: https://github.com/ziti/weewx-reservoir/releases/tag/v1.0.2
[1.0.1]: https://github.com/ziti/weewx-reservoir/releases/tag/v1.0.1
[1.0.0]: https://github.com/ziti/weewx-reservoir/releases/tag/v1.0.0
