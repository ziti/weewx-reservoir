import weewx
import weewx.units
from weewx.wxengine import StdService
from weeutil.weeutil import to_bool

weewx.units.obs_group_dict['lakeSurfaceLevel'] = 'group_altitude'
weewx.units.obs_group_dict['lakePrecipitation'] = 'group_rain'

VERSION = "0.1"

import weeutil.logger
import logging
import requests

log = logging.getLogger(__name__)

def logdbg(msg):
    log.debug(msg)

def loginf(msg):
    log.info(msg)

def logerr(msg):
    log.error(msg)

class Reservoir(StdService):

    def __init__(self, engine, config_dict):
      super(Reservoir, self).__init__(engine, config_dict)
      resevoir_dict = config_dict.get('Reservoir', {})

      self.enable = to_bool(resevoir_dict.get('enable', True))
      if not self.enable:
        loginf("Not enabled, exiting.")
        return

      self.siteId = resevoir_dict.get('Site', 000000)
      unit_system_name = resevoir_dict.get('unit_system', 'US').strip().upper()
      if unit_system_name not in weewx.units.unit_constants:
        raise ValueError("Reservoir: Unknown unit system: %s" % unit_system_name)
      self.unit_system = weewx.units.unit_constants[unit_system_name]

      self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_archive_record(self, event):

      new_record_data = {}
      try:
        new_record_data = {}
        url = "https://waterservices.usgs.gov/nwis/iv/?sites=08063010&siteStatus=all&format=rdb"
        response = requests.get(url)
        if response.status_code == 200:
          data_lines = response.text.splitlines()
          data_lines = [line for line in data_lines if not line.startswith("#")]

          if len(data_lines) >= 3:
            third_row = data_lines[2]
            parts = third_row.split("\t")
            new_record_data['lakeSurfaceLevel'] = parts[12] # 140080_62614
            new_record_data['lakePrecipitation'] = parts[9] # 140082_00045
            if 'usUnits' not in new_record_data:
              new_record_data['usUnits'] = self.unit_system

            target_data = weewx.units.to_std_system(new_record_data, event.record['usUnits'])
            event.record.update(target_data)
          else:
            print("Not enough data rows.")
        else:
          print("Error downloading the file.")           

      except IOError as e:
        logerr("Cannot open file. Reason: %s" % e)

