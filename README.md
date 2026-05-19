# weewx-reservoir

A [WeeWX](https://weewx.com) extension that augments weather archive records with lake level and precipitation data from the [USGS Water Services Instantaneous Values API](https://waterservices.usgs.gov/).

On each archive interval, the extension fetches the latest readings from a configured USGS monitoring site and adds them to the WeeWX record, making them available to skins, reports, and the database like any other observation.

## Observation Types Added

| Field | WeeWX unit group | Description |
|---|---|---|
| `lakeSurfaceLevel` | `group_altitude` | Lake/reservoir surface elevation |
| `lakePrecipitation` | `group_rain` | Precipitation recorded at the USGS gauge |

## Requirements

- WeeWX 4.x or later
- Python `requests` library (`pip install requests`)

## Installation

1. Download or clone this repository.

2. Run the WeeWX extension installer from the repository root:

    ```sh
    wee_extension --install .
    ```

3. Restart WeeWX:

    ```sh
    sudo systemctl restart weewx
    # or, for sysV init:
    sudo /etc/init.d/weewx restart
    ```

The installer adds a `[Reservoir]` section to `weewx.conf` with defaults pre-filled and registers the service under `[Engine] > [[Services]] > data_services`.

## Configuration

After installation, edit `weewx.conf` and locate the `[Reservoir]` section:

```ini
[Reservoir]
    # USGS site ID — find yours at https://waterdata.usgs.gov/nwis/rt
    site = 08063010

    # Unit system the USGS values are reported in.
    # Choices: US, METRIC, or METRICWX
    unit_system = US

    # Set to false to disable without uninstalling
    enable = true
```

### Finding Your USGS Site ID

1. Go to https://waterdata.usgs.gov/nwis/rt
2. Select your state and the parameter types you want (e.g. "Lake/Res. Elevation" and "Precipitation").
3. The site ID is the numeric code shown in the URL or results table (e.g. `08063010`).

## Displaying Data in Skins

Once the extension is running, `lakeSurfaceLevel` and `lakePrecipitation` are available as standard WeeWX observations. Example Cheetah template tags:

```
Current lake level: $current.lakeSurfaceLevel
Today's gauge precipitation: $day.lakePrecipitation.sum
```

## Development & Testing

The test suite runs without a WeeWX installation. All WeeWX modules are stubbed at import time, so only `pytest` and `requests` are needed.

### Setup

```sh
python3 -m venv .venv
.venv/bin/pip install pytest requests
```

### Running the tests

```sh
.venv/bin/pytest tests/ -v
```

Tests are organised into three classes in [tests/test_reservoir.py](tests/test_reservoir.py):

| Class | What it covers |
|---|---|
| `TestParseUsgsRdb` | RDB response parsing: correct values, float casting, non-numeric sentinels (`Ice`, `Eqp`), missing columns, malformed responses |
| `TestReservoirInit` | Service initialisation: config key reading, missing site, invalid unit system, enable/disable |
| `TestReservoirNewArchiveRecord` | Live fetch path: URL contains site ID, record updated, non-200 responses, network errors, timeout argument |

## Uninstall

```sh
wee_extension --uninstall reservoir
sudo systemctl restart weewx
```

## Version History

| Version | Notes |
|---|---|
| 1.0.1 | Current release |
| 1.0.0 | Initial release |

## License

See [LICENSE.txt](LICENSE.txt).
