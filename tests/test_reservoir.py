"""Unit tests for weewx-reservoir.

Can be run without a WeeWX installation:

    python -m pytest tests/
    # or
    python tests/test_reservoir.py
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


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

    wxengine_mod = types.ModuleType('weewx.wxengine')

    class StdService:
        def __init__(self, engine, config_dict):
            self._bindings = {}

        def bind(self, event, handler):
            self._bindings[event] = handler

    wxengine_mod.StdService = StdService
    weewx_mod.wxengine = wxengine_mod

    weeutil_mod = types.ModuleType('weeutil')
    weeutil_util = types.ModuleType('weeutil.weeutil')
    weeutil_util.to_bool = lambda v: str(v).strip().lower() not in ('false', '0', 'no')
    weeutil_mod.weeutil = weeutil_util

    sys.modules['weewx'] = weewx_mod
    sys.modules['weewx.units'] = units_mod
    sys.modules['weewx.wxengine'] = wxengine_mod
    sys.modules['weeutil'] = weeutil_mod
    sys.modules['weeutil.weeutil'] = weeutil_util


_make_weewx_stubs()

# Place bin/ on the path so `user.reservoir` is importable
sys.path.insert(0, 'bin')
from user.reservoir import Reservoir, parse_usgs_rdb  # noqa: E402


# ---------------------------------------------------------------------------
# Sample USGS RDB responses
# ---------------------------------------------------------------------------

# Realistic response with both surface level (62614) and precipitation (00045)
SAMPLE_RDB = (
    "# Comment line\n"
    "# Another comment\n"
    "agency_cd\tsite_no\tdatetime\ttz_cd\t00060\t00060_cd\t140082_00045\t140082_00045_cd\tcol_x\tcol_x_cd\tcol_y\tcol_y_cd\t140080_62614\t140080_62614_cd\n"
    "5s\t15s\t20d\t6s\t14n\t10s\t14n\t10s\t14n\t10s\t14n\t10s\t14n\t10s\n"
    "USGS\t08063010\t2024-01-15 10:30\tCST\t500\tA\t0.12\tA\t0\tA\t0\tA\t423.45\tA\n"
)

# Response where USGS reports non-numeric sentinel values (ice, equipment fault, etc.)
SAMPLE_RDB_NON_NUMERIC = (
    "# Comment\n"
    "agency_cd\tsite_no\tdatetime\ttz_cd\t140082_00045\t140082_00045_cd\t140080_62614\t140080_62614_cd\n"
    "5s\t15s\t20d\t6s\t14n\t10s\t14n\t10s\n"
    "USGS\t08063010\t2024-01-15 10:30\tCST\tIce\tIce\tEqp\tEqp\n"
)

# Response whose columns don't include the parameters we care about
SAMPLE_RDB_NO_PARAMS = (
    "# Comment\n"
    "agency_cd\tsite_no\tdatetime\ttz_cd\t00060\t00060_cd\n"
    "5s\t15s\t20d\t6s\t14n\t10s\n"
    "USGS\t08063010\t2024-01-15 10:30\tCST\t500\tA\n"
)

# Response with only surface level (some sites don't report precipitation)
SAMPLE_RDB_LEVEL_ONLY = (
    "# Comment\n"
    "agency_cd\tsite_no\tdatetime\ttz_cd\t140080_62614\t140080_62614_cd\n"
    "5s\t15s\t20d\t6s\t14n\t10s\n"
    "USGS\t08063010\t2024-01-15 10:30\tCST\t523.10\tA\n"
)


# ---------------------------------------------------------------------------
# Tests for parse_usgs_rdb()
# ---------------------------------------------------------------------------

class TestParseUsgsRdb(unittest.TestCase):

    def test_parses_surface_level(self):
        result = parse_usgs_rdb(SAMPLE_RDB)
        self.assertAlmostEqual(result['lakeSurfaceLevel'], 423.45)

    def test_parses_precipitation(self):
        result = parse_usgs_rdb(SAMPLE_RDB)
        self.assertAlmostEqual(result['lakePrecipitation'], 0.12)

    def test_values_are_floats(self):
        result = parse_usgs_rdb(SAMPLE_RDB)
        self.assertIsInstance(result['lakeSurfaceLevel'], float)
        self.assertIsInstance(result['lakePrecipitation'], float)

    def test_non_numeric_values_omitted(self):
        """Sentinel strings like 'Ice' or 'Eqp' must be silently skipped."""
        result = parse_usgs_rdb(SAMPLE_RDB_NON_NUMERIC)
        self.assertNotIn('lakeSurfaceLevel', result)
        self.assertNotIn('lakePrecipitation', result)

    def test_missing_param_columns_omitted(self):
        """Sites that don't report expected parameters return an empty dict."""
        result = parse_usgs_rdb(SAMPLE_RDB_NO_PARAMS)
        self.assertNotIn('lakeSurfaceLevel', result)
        self.assertNotIn('lakePrecipitation', result)

    def test_partial_params_returned(self):
        """Only available parameters are included; missing ones are not added."""
        result = parse_usgs_rdb(SAMPLE_RDB_LEVEL_ONLY)
        self.assertAlmostEqual(result['lakeSurfaceLevel'], 523.10)
        self.assertNotIn('lakePrecipitation', result)

    def test_too_few_lines_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_usgs_rdb("# comment\nheader_only\n")

    def test_empty_response_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_usgs_rdb("")

    def test_all_comment_lines_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_usgs_rdb("# line1\n# line2\n# line3\n")

    def test_column_found_by_suffix_not_position(self):
        """Column lookup must use the param code suffix, not a hardcoded index."""
        # Swap the column order relative to SAMPLE_RDB
        rdb = (
            "# Comment\n"
            "agency_cd\tsite_no\tdatetime\ttz_cd\t140080_62614\t140080_62614_cd\t140082_00045\t140082_00045_cd\n"
            "5s\t15s\t20d\t6s\t14n\t10s\t14n\t10s\n"
            "USGS\t08063010\t2024-01-15 10:30\tCST\t999.99\tA\t1.23\tA\n"
        )
        result = parse_usgs_rdb(rdb)
        self.assertAlmostEqual(result['lakeSurfaceLevel'], 999.99)
        self.assertAlmostEqual(result['lakePrecipitation'], 1.23)


# ---------------------------------------------------------------------------
# Tests for Reservoir.__init__()
# ---------------------------------------------------------------------------

class TestReservoirInit(unittest.TestCase):

    def _config(self, **overrides):
        cfg = {
            'Reservoir': {
                'site': '08063010',
                'unit_system': 'US',
                'enable': 'true',
            }
        }
        cfg['Reservoir'].update(overrides)
        return cfg

    def test_site_id_set_from_config(self):
        svc = Reservoir(None, self._config())
        self.assertEqual(svc.site_id, '08063010')

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

    def test_empty_reservoir_section_missing_site_raises(self):
        with self.assertRaises(ValueError):
            Reservoir(None, {'Reservoir': {}})


# ---------------------------------------------------------------------------
# Tests for Reservoir.new_archive_record()
# ---------------------------------------------------------------------------

class TestReservoirNewArchiveRecord(unittest.TestCase):

    def _make_service(self, site='08063010'):
        cfg = {'Reservoir': {'site': site, 'unit_system': 'US', 'enable': 'true'}}
        return Reservoir(None, cfg)

    def _make_event(self):
        event = MagicMock()
        event.record = {'usUnits': 1, 'dateTime': 1700000000}
        return event

    @patch('user.reservoir.requests.Session')
    def test_url_contains_configured_site_id(self, mock_session):
        mock_session.return_value.get.return_value = MagicMock(status_code=200, text=SAMPLE_RDB)
        svc = self._make_service(site='99887766')
        svc.new_archive_record(self._make_event())
        url_called = mock_session.return_value.get.call_args[0][0]
        self.assertIn('99887766', url_called)

    @patch('user.reservoir.requests.Session')
    def test_request_includes_timeout(self, mock_session):
        mock_session.return_value.get.return_value = MagicMock(status_code=200, text=SAMPLE_RDB)
        svc = self._make_service()
        svc.new_archive_record(self._make_event())
        _, kwargs = mock_session.return_value.get.call_args
        self.assertIn('timeout', kwargs)

    @patch('user.reservoir.requests.Session')
    def test_record_updated_with_surface_level_and_precipitation(self, mock_session):
        mock_session.return_value.get.return_value = MagicMock(status_code=200, text=SAMPLE_RDB)
        svc = self._make_service()
        event = self._make_event()
        svc.new_archive_record(event)
        self.assertAlmostEqual(event.record['lakeSurfaceLevel'], 423.45)
        self.assertAlmostEqual(event.record['lakePrecipitation'], 0.12)

    @patch('user.reservoir.requests.Session')
    def test_non_200_response_leaves_record_unchanged(self, mock_session):
        mock_session.return_value.get.return_value = MagicMock(status_code=503)
        svc = self._make_service()
        event = self._make_event()
        original = dict(event.record)
        svc.new_archive_record(event)
        self.assertEqual(event.record, original)

    @patch('user.reservoir.requests.Session')
    def test_network_error_does_not_propagate(self, mock_session):
        mock_session.return_value.get.side_effect = ConnectionError("connection refused")
        svc = self._make_service()
        # Must not raise — WeeWX would crash if an unhandled exception escaped
        svc.new_archive_record(self._make_event())

    @patch('user.reservoir.requests.Session')
    def test_no_recognised_params_leaves_record_unchanged(self, mock_session):
        mock_session.return_value.get.return_value = MagicMock(status_code=200, text=SAMPLE_RDB_NO_PARAMS)
        svc = self._make_service()
        event = self._make_event()
        original = dict(event.record)
        svc.new_archive_record(event)
        self.assertEqual(event.record, original)

    @patch('user.reservoir.requests.Session')
    def test_non_numeric_response_leaves_record_unchanged(self, mock_session):
        mock_session.return_value.get.return_value = MagicMock(status_code=200, text=SAMPLE_RDB_NON_NUMERIC)
        svc = self._make_service()
        event = self._make_event()
        original = dict(event.record)
        svc.new_archive_record(event)
        self.assertEqual(event.record, original)

    @patch('user.reservoir.requests.Session')
    def test_partial_update_when_only_level_present(self, mock_session):
        mock_session.return_value.get.return_value = MagicMock(status_code=200, text=SAMPLE_RDB_LEVEL_ONLY)
        svc = self._make_service()
        event = self._make_event()
        svc.new_archive_record(event)
        self.assertAlmostEqual(event.record['lakeSurfaceLevel'], 523.10)
        self.assertNotIn('lakePrecipitation', event.record)


if __name__ == '__main__':
    unittest.main()
