#!/usr/bin/env python

from datetime import datetime, timezone, timedelta

"""
   Project level constants
"""

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
NCCF_FORMAT = "%Y%m%d%H%M%S%f"
CONFIGS_DICT = {"25hr": "25 hour", "month":"monthly", "year":"annual"}
MODES = ["25 hour", "monthly", "annual"]
HOURS_IN_DAY = 24
florida_lat = [25, 26.75]
florida_lon = [-80.75, -78.75]
NUM_DEGREES = 360
RIGHT_ANGLE = 90
rds_CERTIFICATE_URL = 'https://truststore.pki.rds.amazonaws.com/us-east-1/us-east-1-bundle.pem'
docker_CERTIFICATE_PATH = '/tmp/us-east-1-bundle.pem'
PRODUCT_SHORT_NAMES = {"rtv": "HFRNet_Hourly",
                       "rtv-intermed": "HFRNet_Hourly_Intermediate",
                       "stc": "HFRNet_25Hour",
                       "stc-intermed": "HFRNet_25Hour_Intermediate",
                       "monthly": "HFRNet_Monthly",
                       "monthly-intermed": "HFRNet_Monthly_Intermediate",
                       "annual": "HFRNet_Annual"
                       }

#minimum dates for when to do the averages
YEAR_AVG_MIN_DATE = datetime(datetime.now(timezone.utc).year, 1, 20, 0, 0, tzinfo=timezone.utc)
MONTH_AVG_MIN_DAY = 13
#--------
# Waiting time for locking a process
process_time = timedelta(hours=4)
