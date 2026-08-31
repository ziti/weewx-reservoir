#
#    Copyright (c) 2024 Zach Taffet
#
#    See the file LICENSE for your full rights (GNU GPL v3).
#
"""Installer for Reservoir"""
from io import StringIO

import configobj
from weecfg.extension import ExtensionInstaller

VERSION = '1.1.0'

reservoir_config = """
    [Reservoir]
        # USGS site ID -- find yours at https://waterdata.usgs.gov/nwis/rt
        site = 08063010
        # Unit system the USGS values are reported in: US, METRIC, or METRICWX
        unit_system = US
        # Set to false to disable the extension without uninstalling it
        enable = true
        # Seconds between USGS fetches; readings are reused in between
        min_fetch_interval = 900
        # Skip a reading whose own timestamp is older than this many seconds
        max_reading_age = 3600
        # HTTP request timeout, seconds
        timeout = 10
"""

reservoir_dict = configobj.ConfigObj(StringIO(reservoir_config))

def loader():
    return ReservoirInstaller()

class ReservoirInstaller(ExtensionInstaller):
    def __init__(self):
        super().__init__(
            version=VERSION,
            name='reservoir',
            description='Augment WeeWX records with data from USGS Water Services API',
            author="Zach Taffet",
            author_email="152570+ziti@users.noreply.github.com",
            data_services='user.reservoir.Reservoir',
            config=reservoir_dict,
            files=[('bin/user', ['bin/user/reservoir.py'])]
            )
