import weewx
import weewx.units
from weewx.wxengine import StdService
from weeutil.weeutil import to_bool

import requests

import logging

log = logging.getLogger(__name__)

def logdbg(msg):
    log.debug(msg)

def loginf(msg):
    log.info(msg)

def logerr(msg):
    log.error(msg)

weewx.units.obs_group_dict['lakeSurfaceLevel'] = 'group_altitude'
weewx.units.obs_group_dict['lakePrecipitation'] = 'group_rain'

VERSION = "1.0.1"
loginf("version %s" % VERSION)


def parse_usgs_rdb(text):
    """Parse a USGS RDB-format response and return lake observation values.

    Locates columns by their USGS parameter code suffix so the result is
    correct regardless of column order or which site is queried:
      62614 - lake/reservoir surface elevation
      00045 - precipitation

    Returns a dict containing float values for any recognised parameters found.
    Raises ValueError if the response does not contain enough rows to parse.
    """
    lines = [line for line in text.splitlines() if not line.startswith('#') and line.strip()]
    if len(lines) < 3:
        raise ValueError("USGS response does not contain enough data rows")

    headers = lines[0].split('\t')
    # lines[1] is the RDB format row (column widths/types); lines[2] is the first data row
    data_parts = lines[2].split('\t')

    def find_column(param_code):
        for i, h in enumerate(headers):
            if h.endswith('_' + param_code):
                return i
        return None

    result = {}

    level_idx = find_column('62614')
    if level_idx is not None and level_idx < len(data_parts):
        try:
            result['lakeSurfaceLevel'] = float(data_parts[level_idx])
        except (ValueError, TypeError):
            logdbg("Non-numeric lake surface level value: %s" % data_parts[level_idx])

    precip_idx = find_column('00045')
    if precip_idx is not None and precip_idx < len(data_parts):
        try:
            result['lakePrecipitation'] = float(data_parts[precip_idx])
        except (ValueError, TypeError):
            logdbg("Non-numeric lake precipitation value: %s" % data_parts[precip_idx])

    return result


class Reservoir(StdService):

    def __init__(self, engine, config_dict):
        super(Reservoir, self).__init__(engine, config_dict)
        reservoir_dict = config_dict.get('Reservoir', {})

        self.enable = to_bool(reservoir_dict.get('enable', True))
        if not self.enable:
            loginf("Not enabled, exiting.")
            return

        self.site_id = reservoir_dict.get('site')
        if not self.site_id:
            raise ValueError("Reservoir: 'site' is required in [Reservoir] config")

        unit_system_name = reservoir_dict.get('unit_system', 'US').strip().upper()
        if unit_system_name not in weewx.units.unit_constants:
            raise ValueError("Reservoir: Unknown unit system: %s" % unit_system_name)
        self.unit_system = weewx.units.unit_constants[unit_system_name]

        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_archive_record(self, event):
        try:
            url = "https://waterservices.usgs.gov/nwis/iv/?sites=%s&siteStatus=all&format=rdb" % self.site_id
            loginf("Retrieving USGS water data for site %s" % self.site_id)
            logdbg("GET %s" % url)
            response = requests.get(url, timeout=10)
            logdbg("Response %s" % response.status_code)

            if response.status_code == 200:
                new_record_data = parse_usgs_rdb(response.text)
                if not new_record_data:
                    logerr("No recognised parameters found in USGS response for site %s" % self.site_id)
                    return
                new_record_data['usUnits'] = self.unit_system
                target_data = weewx.units.to_std_system(new_record_data, event.record['usUnits'])
                event.record.update(target_data)
            else:
                logerr("USGS request failed with HTTP %s for site %s" % (response.status_code, self.site_id))

        except ValueError as e:
            logerr("Failed to parse USGS response: %s" % e)
        except Exception as e:
            logerr("Failed to retrieve USGS data for site %s: %s" % (self.site_id, e))

