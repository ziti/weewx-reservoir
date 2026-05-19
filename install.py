#
#    Copyright (c) 2024 Zach Taffet
#
#    See the file LICENSE.txt for your full rights.
#
"""Installer for Reservoir"""
from io import StringIO

import configobj
from weecfg.extension import ExtensionInstaller

VERSION = '1.0.3'

reservoir_config = """
    [Reservoir]
        # https://waterservices.usgs.gov/nwis/iv/?sites=08063010&siteStatus=all&format=rdb
        # Site ID from the USGS website:
        site = 08063010
        # What unit system they will be in.
        # Choices are 'US', 'METRIC', or 'METRICWX'
        unit_system = US
        # Set to false to disable the extension without uninstalling it
        enable = true
"""

reservoir_dict = configobj.ConfigObj(StringIO(reservoir_config))

def loader():
    return ReservoirInstaller()

class ReservoirInstaller(ExtensionInstaller):
    def __init__(self):
        super(ReservoirInstaller, self).__init__(
            version=VERSION,
            name='reservoir',
            description='Augment WeeWX records with data from USGS Water Services API',
            author="Zach Taffet",
            author_email="152570+ziti@users.noreply.github.com",
            data_services='user.reservoir.Reservoir',
            config=reservoir_dict,
            files=[('bin/user', ['bin/user/reservoir.py'])]
            )