"""weewx-reservoir: add USGS lake/reservoir data to WeeWX archive records.

On each archive interval the service returns the latest reading from the USGS
Water Services instantaneous-values API for a configured monitoring site and
merges these observations into the record:

    lakeSurfaceLevel  (group_altitude)  - USGS parameter 62614, surface elevation
    lakePrecipitation (group_rain)      - USGS parameter 00045, gauge precipitation

The USGS feed is only fetched every ``min_fetch_interval`` seconds (the gauge
itself updates every 15-60 minutes); in between, the last reading is reused. A
reading whose own timestamp is older than ``max_reading_age`` is treated as a
frozen feed and skipped rather than pinned into the archive.
"""

import logging
import time
from collections import namedtuple
from datetime import datetime, timedelta, timezone

import requests

import weewx
import weewx.units
from weewx.engine import StdService
from weeutil.weeutil import to_bool, to_int

log = logging.getLogger(__name__)

VERSION = "1.1.0"

BASE_URL = "https://waterservices.usgs.gov/nwis/iv/"

# USGS parameter code -> WeeWX observation name
WANTED_PARAMS = {
    "62614": "lakeSurfaceLevel",
    "00045": "lakePrecipitation",
}

# USGS RDB reports the reading time in the site's local zone as an abbreviation.
# Python can't reliably parse tz abbreviations, so map the US ones we may see.
# An unknown abbreviation just disables the staleness check for that reading.
_TZ_OFFSETS = {
    "UTC": 0, "GMT": 0,
    "EST": -5, "EDT": -4,
    "CST": -6, "CDT": -5,
    "MST": -7, "MDT": -6,
    "PST": -8, "PDT": -7,
    "AKST": -9, "AKDT": -8,
    "HST": -10, "HDT": -9,
}

# Register the custom observation types' unit groups. This must happen at import.
weewx.units.obs_group_dict["lakeSurfaceLevel"] = "group_altitude"
weewx.units.obs_group_dict["lakePrecipitation"] = "group_rain"

# values:   {obs_name: float}
# observed: epoch seconds of the reading, or None if it could not be determined
UsgsReading = namedtuple("UsgsReading", ["values", "observed"])


def _parse_observed(headers, data_parts):
    """Return the reading's time as epoch seconds, or None if unavailable."""
    try:
        dt_idx = headers.index("datetime")
        tz_idx = headers.index("tz_cd")
    except ValueError:
        return None
    if dt_idx >= len(data_parts) or tz_idx >= len(data_parts):
        return None

    offset = _TZ_OFFSETS.get(data_parts[tz_idx].strip().upper())
    if offset is None:
        return None

    raw = data_parts[dt_idx].strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            naive = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        return naive.replace(tzinfo=timezone(timedelta(hours=offset))).timestamp()
    return None


def parse_usgs_rdb(text):
    """Parse a USGS RDB response into a :class:`UsgsReading`.

    Columns are located by their parameter-code suffix (``<ts_id>_<code>``), so
    the result is correct regardless of column order or which site is queried.
    The newest data row is used. Raises ``ValueError`` if the response has no
    data row.
    """
    lines = [ln.strip() for ln in text.splitlines()
             if ln.strip() and not ln.startswith("#")]
    # RDB layout: [0] header, [1] format spec ("5s 15s 20d ..."), [2:] data rows
    # ordered oldest -> newest.
    if len(lines) < 3:
        raise ValueError("USGS response does not contain a data row")

    headers = lines[0].split("\t")
    data_parts = lines[-1].split("\t")

    param_col = {}
    for i, header in enumerate(headers):
        if "_" not in header or header.endswith("_cd"):
            continue
        param_col[header.rsplit("_", 1)[-1]] = i

    values = {}
    for code, field in WANTED_PARAMS.items():
        idx = param_col.get(code)
        if idx is None or idx >= len(data_parts):
            continue
        raw = data_parts[idx].strip()
        try:
            values[field] = float(raw)
        except (ValueError, TypeError):
            # USGS sentinels: Ice, Eqp, Ssn, Bkw, Dis, Rat, Dry, ***, ...
            log.debug("Non-numeric %s (USGS %s): %r", field, code, raw)

    return UsgsReading(values=values, observed=_parse_observed(headers, data_parts))


class Reservoir(StdService):

    def __init__(self, engine, config_dict):
        super().__init__(engine, config_dict)
        self.http = None
        self._cache = None  # (fetched_epoch, UsgsReading)

        cfg = config_dict.get("Reservoir", {})
        log.info("weewx-reservoir version %s", VERSION)

        # Accept either key; the installer writes "enable".
        if not to_bool(cfg.get("enable", cfg.get("enabled", True))):
            log.info("Not enabled, exiting.")
            return

        self.site_id = cfg.get("site")
        if not self.site_id:
            raise ValueError("Reservoir: 'site' is required in [Reservoir]")

        unit_name = cfg.get("unit_system", "US").strip().upper()
        if unit_name not in weewx.units.unit_constants:
            raise ValueError("Reservoir: unknown unit_system: %s" % unit_name)
        self.unit_system = weewx.units.unit_constants[unit_name]

        self.timeout = to_int(cfg.get("timeout", 10))
        self.min_fetch_interval = to_int(cfg.get("min_fetch_interval", 900))
        self.max_reading_age = to_int(cfg.get("max_reading_age", 3600))

        self.params = {"sites": self.site_id, "siteStatus": "all", "format": "rdb"}
        self.http = requests.Session()

        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def shutDown(self):
        if self.http is not None:
            self.http.close()

    def _get_reading(self):
        """Return the current :class:`UsgsReading`, fetching only if the cached
        one is older than ``min_fetch_interval``. On error, fall back to the
        last good reading (its age is checked separately)."""
        now = time.time()
        if self._cache is not None and now - self._cache[0] < self.min_fetch_interval:
            return self._cache[1]

        try:
            response = self.http.get(BASE_URL, params=self.params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            log.error("USGS fetch failed for site %s: %s", self.site_id, e)
            return self._cache[1] if self._cache else None

        try:
            reading = parse_usgs_rdb(response.text)
        except ValueError as e:
            log.error("Could not parse USGS response for site %s: %s", self.site_id, e)
            return self._cache[1] if self._cache else None

        self._cache = (now, reading)
        return reading

    def new_archive_record(self, event):
        try:
            reading = self._get_reading()
            if reading is None or not reading.values:
                return

            if (reading.observed is not None
                    and time.time() - reading.observed > self.max_reading_age):
                log.warning("USGS reading for site %s is stale (%.0f min old); skipping",
                            self.site_id, (time.time() - reading.observed) / 60)
                return

            data = dict(reading.values)
            data["usUnits"] = self.unit_system
            if self.unit_system != event.record["usUnits"]:
                data = weewx.units.to_std_system(data, event.record["usUnits"])
            event.record.update(data)
        except Exception:
            log.exception("Unexpected error adding USGS data for site %s", self.site_id)
