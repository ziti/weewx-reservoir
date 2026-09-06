# weewx-reservoir

[![CI](https://github.com/ziti/weewx-reservoir/actions/workflows/ci.yml/badge.svg)](https://github.com/ziti/weewx-reservoir/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/ziti/weewx-reservoir?sort=semver)](https://github.com/ziti/weewx-reservoir/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

A [WeeWX](https://weewx.com) extension that augments weather archive records with lake level and precipitation data from the [USGS Water Services Instantaneous Values API](https://waterservices.usgs.gov/).

On each archive interval the extension supplies the latest reading from a configured USGS monitoring site and adds it to the WeeWX record, making it available to skins, reports, and the database like any other observation. The USGS feed is only fetched every `min_fetch_interval` seconds (the gauge itself updates every 15–60 minutes); in between, the last reading is reused.

## Observation Types Added

| Field | WeeWX unit group | USGS parameter | Description |
|---|---|---|---|
| `lakeSurfaceLevel` | `group_altitude` | `62614` | Lake/reservoir water surface elevation |
| `lakePrecipitation` | `group_rain` | `00045` | Precipitation recorded at the USGS gauge |

> **Note on `lakePrecipitation`:** USGS parameter `00045` is labelled "Precipitation, total" and its meaning varies by site — it may be an interval total or a running daily total that resets at midnight. `group_rain` in WeeWX expects a per-interval amount. Check what your site actually reports before relying on aggregates like `$day.lakePrecipitation.sum`.

## Requirements

- WeeWX 5.x (uses `weewx.engine`; `weectl`)
- Python `requests` library (`pip install requests`)

## Installation

Install the latest release with `weectl`:

```sh
weectl extension install https://github.com/ziti/weewx-reservoir/releases/latest/download/weewx-reservoir.zip
```

Restart WeeWX:

```sh
sudo systemctl restart weewx
```

Add the observation columns to your WeeWX database:

```sh
weectl database add-column lakeSurfaceLevel --type REAL -y
weectl database add-column lakePrecipitation --type REAL -y
```

The installer adds a `[Reservoir]` section to `weewx.conf` and registers the extension as a WeeWX data service.

## Configuration

After installation, edit `weewx.conf` and locate the `[Reservoir]` section:

```ini
[Reservoir]
    # USGS site ID — find yours at https://waterdata.usgs.gov/nwis/rt
    site = 08063010

    # Unit system the USGS values are reported in: US, METRIC, or METRICWX
    unit_system = US

    # Set to false to disable without uninstalling
    enable = true

    # Seconds between USGS fetches; the reading is reused in between
    min_fetch_interval = 900

    # Skip a reading whose own timestamp is older than this (frozen feed)
    max_reading_age = 3600

    # HTTP request timeout, seconds
    timeout = 10
```

### Finding Your USGS Site ID

1. Go to https://waterdata.usgs.gov/nwis/rt
2. Select your state and the parameter types you want (e.g. "Lake/Res. Elevation" and "Precipitation").
3. The site ID is the numeric code shown in the URL or results table (e.g. `08063010`).

## Displaying Data in Skins

`lakeSurfaceLevel` and `lakePrecipitation` are available as standard WeeWX observations. Example Cheetah template tags:

```
Current lake level: $current.lakeSurfaceLevel
```

For `$day.*` / `$week.*` aggregates the observation also needs a daily-summary table:

```sh
weectl database rebuild-daily --date=YYYY-mm-dd   # or a range; slow on a large DB
```

## Development & Testing

The test suite runs without a WeeWX installation — all WeeWX modules are stubbed at import time.

```sh
python3 -m venv .venv
.venv/bin/pip install pytest requests
.venv/bin/pytest tests/ -v
# or, with no extra deps:
python3 -m unittest discover -s tests
```

| Class | Covers |
|---|---|
| `TestParseUsgsRdb` | RDB parsing: values by parameter-code column, newest data row, reading timestamp, float casting, non-numeric sentinels (`Ice`, `Eqp`), missing columns, malformed responses |
| `TestReservoirInit` | Config reading (incl. the `enabled` alias and overridable intervals), missing site, invalid unit system, enable/disable |
| `TestReservoirNewArchiveRecord` | Fetch path: request targets the configured site with a timeout, record update, HTTP/network errors, response caching, cache fallback on error, stale-reading skip |

## Uninstall

```sh
weectl extension uninstall reservoir
sudo systemctl restart weewx
```

## Version History

See [CHANGELOG.md](CHANGELOG.md) for the full history. Recent releases:

| Version | Notes |
|---|---|
| 1.1.0 | Response caching (`min_fetch_interval`), stale-feed guard (`max_reading_age`), configurable `timeout`; use newest RDB data row and parse its timestamp; `weewx.engine` import; narrower exception handling with tracebacks for unexpected errors; accept the `enabled` config alias; `params=` request building; `shutDown()` closes the HTTP session |
| 1.0.3 | Performance: HTTP session reuse, precomputed request URL, faster RDB parsing, conversion bypass when units already match |
| 1.0.2 | Adds unit tests and documentation |
| 1.0.1 | Bug fixes |
| 1.0.0 | Initial release |

## Contributing

Bug reports and pull requests are welcome. Please read
[CONTRIBUTING.md](CONTRIBUTING.md) first — it covers the coding standard,
commit-message convention, and what a good PR looks like. All participation is
governed by the [Code of Conduct](CODE_OF_CONDUCT.md).

Security issues: see [SECURITY.md](SECURITY.md).

## License

Distributed under the terms of the **GNU General Public License v3.0**. See
[LICENSE](LICENSE).
