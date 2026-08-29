"""Unit tests for weewx-reservoir.

Can be run without a WeeWX installation:

    python -m pytest tests/
    # or
    python tests/test_reservoir.py
"""
import logging
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import requests

# The service logs on its error paths; keep that out of the test output.
logging.disable(logging.CRITICAL)


# ---------------------------------------------------------------------------
# Stub WeeWX modules so tests run without WeeWX installed
# ---------------------------------------------------------------------------

def _make_weewx_stubs():
    weewx_mod = types.ModuleType('weewx')
    weewx_mod.NEW_ARCHIVE_RECORD = 'NEW_ARCHIVE_RECORD'

    units_mod = types.ModuleType('weewx.units')
    units_mod.obs_group_dict = {}
    units_mod.unit_constants = {'US': 1, 'METRIC': 16, 'METRICWX': 17}
    # Return the record unchanged so tests can inspect values directly
    units_mod.to_std_system = MagicMock(side_effect=lambda record, _target: dict(record))
    weewx_mod.units = units_mod

    engine_mod = types.ModuleType('weewx.engine')

    class StdService:
        def __init__(self, engine, config_dict):
            self._bindings = {}

        def bind(self, event, handler):
            self._bindings[event] = handler

    engine_mod.StdService = StdService
    weewx_mod.engine = engine_mod

    weeutil_mod = types.ModuleType('weeutil')
    weeutil_util = types.ModuleType('weeutil.weeutil')
    weeutil_util.to_bool = lambda v: str(v).strip().lower() not in ('false', '0', 'no')
    weeutil_util.to_int = lambda v: int(v)
    weeutil_mod.weeutil = weeutil_util

    sys.modules['weewx'] = weewx_mod
    sys.modules['weewx.units'] = units_mod
    sys.modules['weewx.engine'] = engine_mod
    sys.modules['weeutil'] = weeutil_mod
    sys.modules['weeutil.weeutil'] = weeutil_util


_make_weewx_stubs()

# Place bin/ on the path so `user.reservoir` is importable
sys.path.insert(0, 'bin')
from user.reservoir import Reservoir, parse_usgs_rdb  # noqa: E402


# ---------------------------------------------------------------------------
# Sample USGS RDB responses
# ---------------------------------------------------------------------------

# Realistic response with both surface level (62614) and precipitation (00045).
# Column order is deliberately not the order we read them in.
SAMPLE_RDB = (
    "# Comment line\n"
    "# Another comment\n"
    "agency_cd\tsite_no\tdatetime\ttz_cd\t00060\t00060_cd\t140082_00045\t140082_00045_cd\tcol_x\tcol_x_cd\tcol_y\tcol_y_cd\t140080_62614\t140080_62614_cd\n"
    "5s\t15s\t20d\t6s\t14n\t10s\t14n\t10s\t14n\t10s\t14n\t10s\t14n\t10s\n"
    "USGS\t08063010\t2024-01-15 10:30\tCST\t500\tA\t0.12\tA\t0\tA\t0\tA\t423.45\tA\n"
)

# The reading time encoded in SAMPLE_RDB, as epoch seconds.
SAMPLE_OBSERVED = datetime(
    2024, 1, 15, 10, 30, tzinfo=timezone(timedelta(hours=-6))
).timestamp()

# USGS non-numeric sentinel values (ice, equipment fault, etc.)
SAMPLE_RDB_NON_NUMERIC = (
    "# Comment\n"
    "agency_cd\tsite_no\tdatetime\ttz_cd\t140082_00045\t140082_00045_cd\t140080_62614\t140080_62614_cd\n"
    "5s\t15s\t20d\t6s\t14n\t10s\t14n\t10s\n"
    "USGS\t08063010\t2024-01-15 10:30\tCST\tIce\tIce\tEqp\tEqp\n"
)

# Columns don't include the parameters we care about
SAMPLE_RDB_NO_PARAMS = (
    "# Comment\n"
    "agency_cd\tsite_no\tdatetime\ttz_cd\t00060\t00060_cd\n"
    "5s\t15s\t20d\t6s\t14n\t10s\n"
    "USGS\t08063010\t2024-01-15 10:30\tCST\t500\tA\n"
)

# Only surface level (some sites don't report precipitation)
SAMPLE_RDB_LEVEL_ONLY = (
    "# Comment\n"
    "agency_cd\tsite_no\tdatetime\ttz_cd\t140080_62614\t140080_62614_cd\n"
    "5s\t15s\t20d\t6s\t14n\t10s\n"
    "USGS\t08063010\t2024-01-15 10:30\tCST\t523.10\tA\n"
)

# Multiple data rows, oldest first -- the newest must win
SAMPLE_RDB_MULTIROW = (
    "# Comment\n"
    "agency_cd\tsite_no\tdatetime\ttz_cd\t140080_62614\t140080_62614_cd\n"
    "5s\t15s\t20d\t6s\t14n\t10s\n"
    "USGS\t08063010\t2024-01-15 10:00\tCST\t100.00\tP\n"
    "USGS\t08063010\t2024-01-15 10:15\tCST\t200.00\tP\n"
    "USGS\t08063010\t2024-01-15 10:30\tCST\t316.97\tP\n"
)


# ---------------------------------------------------------------------------
# parse_usgs_rdb()
# ---------------------------------------------------------------------------

class TestParseUsgsRdb(unittest.TestCase):

    def test_parses_surface_level(self):
        self.assertAlmostEqual(parse_usgs_rdb(SAMPLE_RDB).values['lakeSurfaceLevel'], 423.45)

    def test_parses_precipitation(self):
        self.assertAlmostEqual(parse_usgs_rdb(SAMPLE_RDB).values['lakePrecipitation'], 0.12)

    def test_values_are_floats(self):
        values = parse_usgs_rdb(SAMPLE_RDB).values
        self.assertIsInstance(values['lakeSurfaceLevel'], float)
        self.assertIsInstance(values['lakePrecipitation'], float)

    def test_non_numeric_values_omitted(self):
        """Sentinel strings like 'Ice' or 'Eqp' must be silently skipped."""
        values = parse_usgs_rdb(SAMPLE_RDB_NON_NUMERIC).values
        self.assertNotIn('lakeSurfaceLevel', values)
        self.assertNotIn('lakePrecipitation', values)

    def test_missing_param_columns_omitted(self):
        values = parse_usgs_rdb(SAMPLE_RDB_NO_PARAMS).values
        self.assertNotIn('lakeSurfaceLevel', values)
        self.assertNotIn('lakePrecipitation', values)

    def test_partial_params_returned(self):
        values = parse_usgs_rdb(SAMPLE_RDB_LEVEL_ONLY).values
        self.assertAlmostEqual(values['lakeSurfaceLevel'], 523.10)
        self.assertNotIn('lakePrecipitation', values)

    def test_column_found_by_suffix_not_position(self):
        rdb = (
            "# Comment\n"
            "agency_cd\tsite_no\tdatetime\ttz_cd\t140080_62614\t140080_62614_cd\t140082_00045\t140082_00045_cd\n"
            "5s\t15s\t20d\t6s\t14n\t10s\t14n\t10s\n"
            "USGS\t08063010\t2024-01-15 10:30\tCST\t999.99\tA\t1.23\tA\n"
        )
        values = parse_usgs_rdb(rdb).values
        self.assertAlmostEqual(values['lakeSurfaceLevel'], 999.99)
        self.assertAlmostEqual(values['lakePrecipitation'], 1.23)

    def test_uses_newest_data_row(self):
        self.assertAlmostEqual(
            parse_usgs_rdb(SAMPLE_RDB_MULTIROW).values['lakeSurfaceLevel'], 316.97)

    def test_reading_time_parsed(self):
        self.assertEqual(parse_usgs_rdb(SAMPLE_RDB).observed, SAMPLE_OBSERVED)

    def test_reading_time_none_for_unknown_tz(self):
        self.assertIsNone(parse_usgs_rdb(SAMPLE_RDB.replace("\tCST\t", "\tXYZ\t")).observed)

    def test_too_few_lines_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_usgs_rdb("# comment\nheader_only\n")

    def test_empty_response_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_usgs_rdb("")

    def test_all_comment_lines_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_usgs_rdb("# line1\n# line2\n# line3\n")


# ---------------------------------------------------------------------------
# Reservoir.__init__()
# ---------------------------------------------------------------------------

class TestReservoirInit(unittest.TestCase):

    def _config(self, **overrides):
        cfg = {'Reservoir': {'site': '08063010', 'unit_system': 'US', 'enable': 'true'}}
        cfg['Reservoir'].update(overrides)
        return cfg

    def test_site_id_set_from_config(self):
        self.assertEqual(Reservoir(None, self._config()).site_id, '08063010')

    def test_missing_site_raises_value_error(self):
        with self.assertRaises(ValueError):
            Reservoir(None, {'Reservoir': {'unit_system': 'US'}})

    def test_invalid_unit_system_raises_value_error(self):
        with self.assertRaises(ValueError):
            Reservoir(None, self._config(unit_system='IMPERIAL'))

    def test_disabled_does_not_bind_event(self):
        svc = Reservoir(None, self._config(enable='false'))
        self.assertNotIn('NEW_ARCHIVE_RECORD', svc._bindings)

    def test_enabled_binds_archive_record(self):
        svc = Reservoir(None, self._config())
        self.assertIn('NEW_ARCHIVE_RECORD', svc._bindings)

    def test_enabled_key_alias_accepted(self):
        """Older configs use 'enabled' rather than 'enable'."""
        cfg = {'Reservoir': {'site': '1', 'unit_system': 'US', 'enabled': 'false'}}
        self.assertNotIn('NEW_ARCHIVE_RECORD', Reservoir(None, cfg)._bindings)

    def test_config_overrides_defaults(self):
        svc = Reservoir(None, self._config(min_fetch_interval='120',
                                          max_reading_age='600', timeout='4'))
        self.assertEqual(svc.min_fetch_interval, 120)
        self.assertEqual(svc.max_reading_age, 600)
        self.assertEqual(svc.timeout, 4)

    def test_empty_reservoir_section_missing_site_raises(self):
        with self.assertRaises(ValueError):
            Reservoir(None, {'Reservoir': {}})


# ---------------------------------------------------------------------------
# Reservoir.new_archive_record()
# ---------------------------------------------------------------------------

class TestReservoirNewArchiveRecord(unittest.TestCase):

    def _make_service(self, site='08063010', **overrides):
        cfg = {'Reservoir': {'site': site, 'unit_system': 'US', 'enable': 'true',
                             # keep the staleness check out of the way unless a
                             # test opts in
                             'max_reading_age': 10 ** 12}}
        cfg['Reservoir'].update(overrides)
        return Reservoir(None, cfg)

    def _make_event(self):
        event = MagicMock()
        event.record = {'usUnits': 1, 'dateTime': 1700000000}
        return event

    def _ok_response(self, text=SAMPLE_RDB):
        return MagicMock(status_code=200, text=text)

    @patch('user.reservoir.requests.Session')
    def test_request_targets_configured_site(self, mock_session):
        mock_get = mock_session.return_value.get
        mock_get.return_value = self._ok_response()
        svc = self._make_service(site='99887766')
        svc.new_archive_record(self._make_event())
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs['params']['sites'], '99887766')

    @patch('user.reservoir.requests.Session')
    def test_request_includes_timeout(self, mock_session):
        mock_get = mock_session.return_value.get
        mock_get.return_value = self._ok_response()
        svc = self._make_service()
        svc.new_archive_record(self._make_event())
        _, kwargs = mock_get.call_args
        self.assertIn('timeout', kwargs)

    @patch('user.reservoir.requests.Session')
    def test_record_updated_with_surface_level_and_precipitation(self, mock_session):
        mock_session.return_value.get.return_value = self._ok_response()
        event = self._make_event()
        self._make_service().new_archive_record(event)
        self.assertAlmostEqual(event.record['lakeSurfaceLevel'], 423.45)
        self.assertAlmostEqual(event.record['lakePrecipitation'], 0.12)

    @patch('user.reservoir.requests.Session')
    def test_http_error_leaves_record_unchanged(self, mock_session):
        resp = MagicMock(status_code=503)
        resp.raise_for_status.side_effect = requests.HTTPError("503 Server Error")
        mock_session.return_value.get.return_value = resp
        event = self._make_event()
        original = dict(event.record)
        self._make_service().new_archive_record(event)
        self.assertEqual(event.record, original)

    @patch('user.reservoir.requests.Session')
    def test_network_error_does_not_propagate(self, mock_session):
        mock_session.return_value.get.side_effect = requests.ConnectionError("refused")
        # Must not raise -- WeeWX would crash if an unhandled exception escaped
        self._make_service().new_archive_record(self._make_event())

    @patch('user.reservoir.requests.Session')
    def test_no_recognised_params_leaves_record_unchanged(self, mock_session):
        mock_session.return_value.get.return_value = self._ok_response(SAMPLE_RDB_NO_PARAMS)
        event = self._make_event()
        original = dict(event.record)
        self._make_service().new_archive_record(event)
        self.assertEqual(event.record, original)

    @patch('user.reservoir.requests.Session')
    def test_non_numeric_response_leaves_record_unchanged(self, mock_session):
        mock_session.return_value.get.return_value = self._ok_response(SAMPLE_RDB_NON_NUMERIC)
        event = self._make_event()
        original = dict(event.record)
        self._make_service().new_archive_record(event)
        self.assertEqual(event.record, original)

    @patch('user.reservoir.requests.Session')
    def test_partial_update_when_only_level_present(self, mock_session):
        mock_session.return_value.get.return_value = self._ok_response(SAMPLE_RDB_LEVEL_ONLY)
        event = self._make_event()
        self._make_service().new_archive_record(event)
        self.assertAlmostEqual(event.record['lakeSurfaceLevel'], 523.10)
        self.assertNotIn('lakePrecipitation', event.record)

    @patch('user.reservoir.requests.Session')
    def test_reading_cached_between_calls(self, mock_session):
        mock_get = mock_session.return_value.get
        mock_get.return_value = self._ok_response()
        svc = self._make_service()
        with patch('user.reservoir.time.time', return_value=5000):
            svc.new_archive_record(self._make_event())
            svc.new_archive_record(self._make_event())
        self.assertEqual(mock_get.call_count, 1)

    @patch('user.reservoir.requests.Session')
    def test_refetches_after_min_interval(self, mock_session):
        mock_get = mock_session.return_value.get
        mock_get.return_value = self._ok_response()
        svc = self._make_service()
        with patch('user.reservoir.time.time') as clock:
            clock.return_value = 5000
            svc.new_archive_record(self._make_event())
            clock.return_value = 5000 + svc.min_fetch_interval + 1
            svc.new_archive_record(self._make_event())
        self.assertEqual(mock_get.call_count, 2)

    @patch('user.reservoir.requests.Session')
    def test_uses_cached_reading_when_fetch_fails(self, mock_session):
        mock_get = mock_session.return_value.get
        mock_get.return_value = self._ok_response()
        svc = self._make_service()
        with patch('user.reservoir.time.time') as clock:
            clock.return_value = 1000
            first = self._make_event()
            svc.new_archive_record(first)
            self.assertIn('lakeSurfaceLevel', first.record)

            clock.return_value = 1000 + svc.min_fetch_interval + 1
            mock_get.side_effect = requests.ConnectionError("refused")
            second = self._make_event()
            svc.new_archive_record(second)
            self.assertAlmostEqual(second.record['lakeSurfaceLevel'], 423.45)

    @patch('user.reservoir.requests.Session')
    def test_stale_reading_not_applied(self, mock_session):
        mock_session.return_value.get.return_value = self._ok_response()
        svc = self._make_service(max_reading_age='3600')
        event = self._make_event()
        original = dict(event.record)
        with patch('user.reservoir.time.time', return_value=SAMPLE_OBSERVED + 7200):
            svc.new_archive_record(event)
        self.assertEqual(event.record, original)

    @patch('user.reservoir.requests.Session')
    def test_fresh_reading_applied_when_age_ok(self, mock_session):
        mock_session.return_value.get.return_value = self._ok_response()
        svc = self._make_service(max_reading_age='3600')
        event = self._make_event()
        with patch('user.reservoir.time.time', return_value=SAMPLE_OBSERVED + 600):
            svc.new_archive_record(event)
        self.assertAlmostEqual(event.record['lakeSurfaceLevel'], 423.45)


if __name__ == '__main__':
    unittest.main()
