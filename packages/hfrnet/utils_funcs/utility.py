"""Contains functions needed for processing"""

import os
from datetime import datetime, timedelta, timezone, date, time
import calendar
import logging
import json
import re
from pathlib import Path
import textwrap
import numpy as np
from scipy.io import loadmat
import netCDF4 as nc4
from dateutil import parser
import h5py
import boto3
from botocore.config import Config
import hashlib

from hfrnet.utils_funcs.lib_rtv import RtvProcess, Grid
from hfrnet.utils_funcs import constsHFR
from hfrnet.run_rtv.saveNetcdf import loadNetcdf

_log = logging.getLogger()

def Set_s3_output_bucket(mconfigureVals):
    '''
    Set the intermedite files s3 bucket based on the running env id
    Dev/Sandbox: s3://arn:aws:s3:us-east-1:560271376700:accesspoint/nccf-dev-pg-results-ao
    UAT: s3://arn:aws:s3:us-east-1:656149346314:accesspoint/nccf-uat-pg-results-ao
    Prod: s3://arn:aws:s3:us-east-1:844319835141:accesspoint/nccf-prod-pg-results-ao
    '''
    
    _log.info('----------------------')
    _log.info('Set the intermediate files s3 bucket based on the running env id')

    my_config = Config(
        retries = {
            'max_attempts' : 3,
            'mode' : 'adaptive'
        }
    )
    
    sts = boto3.client('sts', config=my_config)
    response = sts.get_caller_identity()
    acc_id = response.get('Account')

    _log.info(f'------Account {acc_id}')
    if acc_id == '560271376700': # Dev/Sandbox
        mconfigureVals.output_s3_loc = 's3://arn:aws:s3:us-east-1:560271376700:accesspoint/nccf-dev-pg-results-ao'
        mconfigureVals.output_intermed_s3_loc = 's3://arn:aws:s3:us-east-1:560271376700:accesspoint/nccf-dev-pg-results-ao' #'nccf-dev-pg-results-us-east-1-560271376700'
    elif acc_id == '656149346314': # UAT
        mconfigureVals.output_s3_loc = 'nccf-uat-pg-results-us-east-1-656149346314' #'s3://arn:aws:s3:us-east-1:656149346314:accesspoint/nccf-uat-pg-results-ao'
        mconfigureVals.output_intermed_s3_loc = 'nccf-uat-pg-intermediate-us-east-1-656149346314'
    elif acc_id == '844319835141': # Prod
        mconfigureVals.output_s3_loc = 'nccf-prod-pg-results-us-east-1-844319835141' #'s3://arn:aws:s3:us-east-1:844319835141:accesspoint/nccf-prod-pg-results-ao'
        mconfigureVals.output_intermed_s3_loc = 'nccf-prod-pg-intermediate-us-east-1-844319835141'
    else:
        _log.error(f"Account id {acc_id} not recognized, so cannot set output S3 bucket.")
        
    _log.info(f"--The output_s3_loc = {mconfigureVals.output_s3_loc}")
    _log.info('----------------------')
    
def convert_time(time_str):
    # Remove the last digit to match the format
    time_str = time_str[:-1]

    # Convert the time string to datetime object
    time_obj = datetime.strptime(time_str, '%Y%m%d%H%M%S')

    # Format the datetime object to the desired format
    formatted_time = time_obj.strftime(constsHFR.DATETIME_FORMAT)

    return formatted_time


def get_file_stime(filen):
    # Check if '_c' is in the string
    if '_s' in filen:
        # Find the position of '_s'
        pos = filen.find('_s')
        # Get the 15 characters after '_s'
        result = filen[pos+2:pos+17]
        return convert_time(result)
    else:
        return current_time()
    
class _dict(dict):
    """dict like object that exposes keys as attributes"""
    def __getattr__(self, key):
        if key not in self or key.startswith("__"):
            raise AttributeError()
        ret = self.get(key, None)
        return ret
    def __setattr__(self, key, value):
        self[key] = value
    def __getstate__(self):
        return self
    def __setstate__(self, d):
        self.update(d)
    def update(self, d=None, **kwargs):
        """update and return self -- the missing dict feature in python"""
        if d:
            super().update(d)
        if kwargs:
            super().update(kwargs)
        return self

    def copy(self):
        return _dict(dict(self).copy())

def process_record(d):
    """gets info of processes"""

    if hasattr(d, 'keys'):
        keys = [k for k in d.keys() if not k.startswith('__')]
        data = _dict()
        for k in keys:
            data[k] = process_record(d[k])
        return data

    if not hasattr(d, 'dtype'):
        return d

    if d.dtype.names is None:
        if len(d) == 1 and d.dtype.name == 'object':
            return process_record(d[0])
        if hasattr(d, 'shape'):
            if len(d.shape) <= 1 or sorted(d.shape)[-2] == 1:
                d = np.array(d).flatten()
        return d
    data = _dict()
    for name in d.dtype.names:
        data[name] = process_record(d[name])

    return data

def read_total_file(filename):
    """read total radial file"""
    data = {'info': {}, 'data': {}}
    raw = None
    try:
        try:
            raw = loadmat(filename)
            data['info']['version'] = raw.get('__version__', '')
            data['info']['header'] = raw.get('__header__', '')
            data['info']['globals'] = raw.get('__globals__', '')
            data['data'] = process_record(raw)
        except Exception:
            _log.info("Loading netCDF4 file")
            data = loadNetcdf(filename)

    except Exception as e:
        msg = f"Could not load {filename}: {e}"
        _log.error(msg)

    return data

#------------------------------------------------
#------------------------------------------------
#------------------------------------------------
def generate_time_spans(stime, etime):
    """

    :param stime: start time
    :param etime: end time
    :return: numpy array of times
    # Function to generate numpy array of 1 hr time spans

    """
    # Convert the input strings to datetime objects
    start_date = datetime.strptime(stime, '%Y%m%d%H%M%S%f')
    start_date = start_date.replace(tzinfo=timezone.utc)
    end_date = datetime.strptime(etime, '%Y%m%d%H%M%S%f')
    end_date = end_date.replace(tzinfo=timezone.utc)

    # Generate the time spans
    time_spans = []
    current_time = start_date
    while current_time <= end_date:
        time_spans.append(current_time)
        current_time += timedelta(hours=1)

    # Convert the list to a numpy array
    time_spans_array = np.array(time_spans)

    return time_spans_array
#------------------------------------------------
#------------------------------------------------
#------------------------------------------------
# Define a function to convert strings to floats and integers

def convert_numbers(dictobj):
    """

    :param dictobj: is the class of a single region with parameters:
    region, polygon, length in string format
    :return: dictobj with all strs converted into numbers
    """

    #-- convert str to floats
    for i in range(len(dictobj['region'])):
        dictobj['region'][i] = float(dictobj['region'][i])

    for i in range(len(dictobj['polygon'])):
        dictobj['polygon'][i] = float(dictobj['polygon'][i])
    dictobj['length'] = int(dictobj['length'])

    #-- convert into numpy arrays
    dictobj['polygon'] = (np.array(dictobj['polygon']).reshape(dictobj['length'], 2,
                                                               order='F'))
    dictobj['region'] = np.array(dictobj['region'])
    return dictobj


def load_land(mfile, domain):
    """
    Read the land json file given the domain and put it in an array of dictionary
    """
    dicts = []
    # Read JSON data from a file
    with open(f"{mfile}/{domain}.json", 'r') as file:
        dicts = json.load(file, object_hook=convert_numbers)

    return dicts

#------------------------------------------------
#------------------------------------------------
def load_grid(mfile, domain, res, rtvInfoObj):
    """
    Read the grid netcdf file given the domain and res and put it in an array of
    dictionary
    """
    scircle_xfield = ""
    scircle_yfield = ""
    if rtvInfoObj.grid_search_radius == np.floor(rtvInfoObj.grid_search_radius):
        scircle_xfield = f"ocean_x_scircle{rtvInfoObj.grid_search_radius:.0f}km"
        scircle_yfield = f"ocean_y_scircle{rtvInfoObj.grid_search_radius:.0f}km"

    elif rtvInfoObj.grid_search_radius * 1000 == np.floor(
            rtvInfoObj.grid_search_radius * 1000):
        scircle_xfield = f"ocean_x_scircle{rtvInfoObj.grid_search_radius * 1000:.0f}m"
        scircle_yfield = f"ocean_y_scircle{rtvInfoObj.grid_search_radius * 1000:.0f}m"

    else:
        msg = (f"Invalid grid search radius of {rtvInfoObj.grid_search_radius}"
               "km. Value must be a whole number when represented in meters")
        _log.fatal(msg)
        raise ValueError(msg)

    grid = Grid()
    with nc4.Dataset(f"{mfile}/{domain}{res}.nc", 'r') as ds:

        grid.x_range = np.array(ds.variables["x_range"][:])
        grid.y_range = np.array(ds.variables["y_range"][:])

        dd = np.array(ds.variables["dd"][:])
        grid.dx = dd[0]
        grid.dy = dd[1]
        grid.size = np.array(ds.variables["size"][:])
        grid.ocean_indices = np.array(ds.variables["ocean_indices"][:])
        grid.ocean_xy = np.array(ds.variables["ocean_xy"][:,:])
        setattr(grid, scircle_xfield,
                np.array(ds.variables[f"{scircle_xfield}"][:, :]))
        setattr(grid, scircle_yfield,
                np.array(ds.variables[f"{scircle_yfield}"][:, :]))

        grid.resolution_km  = ds.getncattr('resolution_km')
        grid.projection  = ds.getncattr('projection')
        return grid

def current_time():
    """Return the current time in str format for database"""
    return datetime.now(timezone.utc).strftime(constsHFR.DATETIME_FORMAT)

def current_datetime():
    """Return the datetime of current time"""
    return datetime.now(timezone.utc)

def now_hour(inTime = None):
    """ Returns datetime at top of current hour"""
    if inTime:
        t = inTime
    else:
        t = current_datetime()
    return t.replace(second=0, microsecond=0, minute=0, hour=t.hour)

def eomday(t):
    """Gets end of month"""
    days_in_month = calendar.monthrange(t.year, t.month)[1]
    return datetime(t.year, t.month, days_in_month)

def now_second(inTime = None):
    """ Returns current datetime to nearest second, no microsecond"""
    if inTime:
        t = inTime
    else:
        t = current_datetime()
    return t.replace(second=t.second, microsecond=0, minute=t.minute,
                     hour=t.hour)

def hour_range(start, end, step=1):
    """ranges of hours"""
    cur = start
    while cur < end:
        yield cur
        cur += timedelta(hours=step)

def next_month_start(t):
    """return the start day of the next month"""
    return (datetime(year=t.year, month=t.month, day=1) +
            timedelta(days=32)).replace(day=1)

def next_month(t):
    """return the next month"""
    try:
        nextmonthdate = t.replace(month=t.month+1)
    except ValueError:
        if t.month == 12:
            nextmonthdate = t.replace(year=t.year+1, month=1)
        else:
            # next month is too short to have "same date"
            nextmonthdate = eomday(t.replace(month=t.month+1, day=1))
    return nextmonthdate

def prev_month_start(t):
    """return the start day of the prev month"""
    return (datetime(year=t.year, month=t.month, day=1) + timedelta(days=-1)).replace(day=1)

def prev_month(t):
    """return the previous month's date"""
    try:
        prevmonthdate = t.replace(month=t.month-1)
    except ValueError:
        if t.month == 1:
            prevmonthdate = t.replace(year=t.year-1, month=12)
        else:
            # prev month is too short to have "same date"
            prevmonthdate = eomday(t.replace(month=t.month-1, day=1))
    return prevmonthdate

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S.%f"
DATETIME_FORMAT = DATE_FORMAT + " " + TIME_FORMAT
def get_datetime(datetime_str=None):
    """get datetime in different instances"""
    if not datetime_str:
        return current_datetime()

    if isinstance(datetime_str, (datetime, timedelta)):
        return datetime_str

    if isinstance(datetime_str, (list, tuple)):
        return datetime(datetime_str)

    if isinstance(datetime_str, date):
        return datetime.combine(datetime_str, time())

    # dateutil parser does not agree with dates like 0000-00-00
    if not datetime_str or (datetime_str or "").startswith("0000-00-00"):
        return None

    try:
        return datetime.strptime(datetime_str, DATETIME_FORMAT)
    except ValueError:
        return parser.parse(datetime_str)


def set_history(A, msg):
    """ Append to NetCDF history"""
    if not hasattr(A, 'history'):
        A.history = []
    h = _dict()
    h.timestamp = current_datetime().strftime('%Y-%m-%dT%H:%M:%SZ')
    h.program = os.path.basename(__file__)
    h.user = os.getenv('USER') or 'unknown user'
    h.message = msg
    A.history.append(h)
    
def get_processes():
    """
       Get a list of processes based on the input time
    """
    process_list = []
    stdRtvProcess = RtvProcess()
    stdRtvProcess.name = "rtv"
    stdRtvProcess.method = "uwls"
    stdRtvProcess.methoddesc = "Unweighted Least Squares"
    stdRtvProcess.saveas = "ascii,netcdf"
    process_list.append(stdRtvProcess)

    stdRtvProcess2 = RtvProcess()
    stdRtvProcess2.name = "stc"
    stdRtvProcess2.method = "uwls"
    stdRtvProcess2.methoddesc = "Unweighted Least Squares"
    stdRtvProcess2.saveas = "ascii,netcdf"
    process_list.append(stdRtvProcess2)


def load_mat(filename):
    """load matlab or netcdf file"""

    data = {'info': {}, 'data': {}}
    try:
        try:
            raw = loadmat(filename)
        except:
            raw = h5py.File(filename,'r')

        data['info']['version'] = raw.get('__version__', '')
        data['info']['header'] = raw.get('__header__', '')
        data['info']['globals'] = raw.get('__globals__', '')

        data['data'] = process_record(raw)
    except:
        _log.info("Could not load file")

    return data

#########################################################################
def create_CCAP_filename_s_e(ctime, stime, etime, alg_ver, unit_name, ext):
    """
    :param config_dict: contains the yaml config file
    :return: the ccap file name
    """
    # example file name
    # unit_v01r1_GPM_s202105191345190_e202105191258000_c202208092344126.log

    # ctime = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-5]
    # ctime = current_time('%Y%m%d%H%M%S%f')

    file_name = f'{unit_name}_{alg_ver}_none_s{stime}_e{etime}_c{ctime}{ext}'
    return file_name

#########################################################################
#########################################################################
#########################################################################

def setup_log_filename(my_pkgint, added_name=""):
    """
    :param my_pkgint: contains the interface of the unit object
    It sets up the logfile for the entire unit logging object
    :param added_name: any optional string added to the unit name
    """
    # --------------------- create the log file
    log_dir = Path(my_pkgint.config['directory.log'])
    c_datetime = current_datetime()
    ctime = c_datetime.strftime('%Y%m%d%H%M%S%f')[:-5]
    if my_pkgint.config['processing.batch_processing']:
        stime = f"{my_pkgint.config['time.start_date']}"
        etime = f"{my_pkgint.config['time.end_date']}"
    else:
        # Remove minutes and seconds by setting them to 0
        stimeobj = c_datetime.replace(minute=0, second=0, microsecond=0)
        stime = stimeobj.strftime('%Y%m%d%H%M%S%f')[:-5]
        # Set minutes to 59 and seconds to 59.9
        etimeobj = c_datetime.replace(minute=59, second=59, microsecond=900000)
        etime = etimeobj.strftime('%Y%m%d%H%M%S%f')[:-5]


    algo_ver = f"{my_pkgint.config['production.version']}"

    run_logfile = create_CCAP_filename_s_e(ctime, stime, etime,
                                            algo_ver, f"{added_name}", ".log")
    handler = logging.FileHandler(f"{log_dir}/{run_logfile}")
    date_format = '%Y-%m-%d %H:%M:%S'
    full_format = '%(asctime)s - %(levelname)s - (%(name)s:%(funcName)s) - %(message)s'

    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(fmt=full_format, datefmt=date_format))

    my_log = logging.getLogger()
    my_log.addHandler(handler)

    return handler

def resolution_spaced(resolution):
    """
    Need to put a space in the <resolution> for metadata
    """
    res_spaced = ""
    if "km" in resolution:
        res_spaced = resolution.replace("km", " km")
    else:
        res_spaced = resolution.replace("m", " m")

    return res_spaced

def rtvNcid(metadataObj, configObj, rtvProcessObj, currTime):
    """
    %    Generates NetCDF ACDD ID attribute value
    %
    %    id = rtvNcid(metadataObj, configObj, rtvProcessObj, time) returns
    %    an id string for the NetCDF Attribute Convention for Data
    %    Discovery (ACDD) metadata standard.
    %
    %    The id is comprised of the data timestamp (t) and metadata contained
    %    in the configuration structures including the institution acronym,
    %    process method, process name, subprocess (if defined), domain and
    %    resolution.
    %
    %    Used in RTVSAVENETCDF, STCSAVENETCDF, LTASAVENETCDF
    %
    %    HF-Radar Network
    %    Scripps Institution of Oceanography
    %    Coastal Observing Research and Development Center
    """

    if rtvProcessObj.subprocess and rtvProcessObj.subprocess_name:

        ncid = (f"{currTime.strftime('%Y%m%d%H%M')}{metadataObj.institution_acronym.lower()}"
                f"hfr{rtvProcessObj.method}{rtvProcessObj.name}{rtvProcessObj.subprocess_name}"
                f"{configObj.domain}{configObj.resolution}")
    else:

        ncid = (f"{currTime.strftime('%Y%m%d%H%M')}{metadataObj.institution_acronym.lower()}"
                f"hfr{rtvProcessObj.method}{rtvProcessObj.name}"
                f"{configObj.domain}{configObj.resolution}")

    return ncid



def ltaRunConfig(rtvTime, configObj, rtvProcessObj):
    """Determine if need to do monthly/yearly average"""

    reprocessing = configObj.reprocess
    doMonthly = False
    doYearly = False
    timeNow = current_datetime()
    timeMonthly = rtvTime
    timeYearly = rtvTime

    if reprocessing:

        monthDiff = timeNow.month - rtvTime.month
        yearDiff = timeNow.year - rtvTime.year

        #if timeNow is a month more than the reprocess date, then do monthly avg
        if monthDiff >= 1 or yearDiff >= 1:
            doMonthly = True

        #if reprocess date if previous year, then do yearly avg
        if yearDiff >= 1:
            doYearly = True

    else:#NRT

        from hfrnet.db_tools.db_tables import get_state_time
        
        #have to get state from database to see if it's already been done
        state_time = get_state_time(configObj, rtvProcessObj.name.lower())

        msg = f"State time for {rtvProcessObj.name.lower()} is {state_time}"
        _log.info(msg)
        
        if state_time is None:
            state_time = datetime.fromisoformat('1970-01-01')
            msg = (f"No lta state defined. Using base date 1970-01-01")
            _log.warning(msg)
            
        if rtvTime.day >= constsHFR.MONTH_AVG_MIN_DAY:
            doMonthly = True

            month_diff = timeNow.month - state_time.month
            year_diff = timeNow.year - state_time.year
            
            if month_diff < 0 and year_diff > 0:
                month_diff = month_diff + year_diff*12
                
            # Average has already been done this month
            if month_diff == 0:
                doMonthly = False
            elif month_diff == 1:
                doMonthly = True
            else:
                doMonthly = True
                msg = ("Warning: time difference in month between db state time"
                       f"and current time is {month_diff}.  "
                       "Should be just 1 month difference during proper running")
                _log.warning(msg)

            if doMonthly:
                #replace the month in the datetime to do previous month's average
                timeMonthly = rtvTime.replace(day=1) - timedelta(days=7)

        if rtvTime > constsHFR.YEAR_AVG_MIN_DATE:
            doYearly = True

            #check if average has been done
            if state_time.year == timeNow.year:
                doYearly = False

            if doYearly:
                #replace year to do previous year's average
                timeYearly = rtvTime.replace(year=rtvTime.year -1)

    return (doMonthly, doYearly, timeMonthly, timeYearly)


def prev_radial_data(fileName, last):
    """ Get the array of info from previous radials.
        Still kept the Matlab file in case needed.
    """
    last_radial = None
    last_network = None
    last_site = None
    last_time = None
    last_patterntype = None
    if fileName.suffix == '.mat':
        last_radial = last['data']['r']
        # Loop over each site defined in the config
        last_network = np.array(list(last_radial.network))
        last_site = np.array(list(last_radial.site))
        last_patterntype = np.array(list(last_radial.patterntype))
        last_time = [datetime(2024, 12, 25, tzinfo=timezone.utc) for rr in last_radial.network]
        last_time = np.array(last_time)
    if fileName.suffix == '.nc':
        last_radial = last['r']
        # Loop over each site defined in the config
        last_network = np.array([rr['network'] for rr in last_radial])
        last_site = np.array([rr['site'] for rr in last_radial])
        last_patterntype = np.array([rr['patterntype'] for rr in last_radial])
        last_time = np.array([rr['time'] for rr in last_radial])

    return last_network, last_site, last_patterntype, last_time

def get_timestamp_from_filename(filename):
    """
    Get the start/end timestamp from the filename (output netCDF file) if available
    """
    start = re.search(r'_s(?P<start>\d*)_', filename)
    if start is not None:
        start = start.group(1)
        start = f"{start[:4]}-{start[4:6]}-{start[6:8]}T{start[8:10]}:{start[10:12]}:{start[12:14]}Z"
    else:
        start = ""
    end = re.search(r'_e(?P<end>\d*)_', filename)
    if end is not None:
        end = end.group(1)
        end = f"{end[:4]}-{end[4:6]}-{end[6:8]}T{end[8:10]}:{end[10:12]}:{end[12:14]}Z"
    else:
        end = ""
    return start, end


def wrap_text(text, width=None):
    """wrap the text to certain line width"""
    if width is None:
        return text

    return textwrap.fill(text, width)

def copy_file_from_s3(s3_url, file_name, dir_dest):
    """
    # s3handle.download_file('nccf-dev-ingest-trust-us-east-1-560271376700', 
    #                     'HFRNet/AOOS/WAIN/Radials/RDLm_WAIN_2025_03_21_1200.ruv', 
    #                     '/home/ec2-user/environment/HFR/hfrnet/packages/test.ruv')
    #  dfile:::['RDLm_PYFC_2025_04_02_1900.ruv']
    #  dir:::['s3://arn:aws:s3:us-east-1:560271376700:accesspoint/nccf-dev-ingest-trust-ssbox/HFRNet/CariCOOS/PYFC']
    # arn:aws:s3:us-east-1:560271376700:accesspoint/nccf-dev-pg-results-ao
    """
    #'s3://arn:aws:s3:us-east-1:560271376700:accesspoint/nccf-dev-ingest-trust-ssbox/HFRNet/CariCOOS/PYFC/Radials/RDLm_WAIN_2025_03_21_1200.ruv'
    _log.info(f">>> s3_url={s3_url}")

    my_config = Config(
        retries = {
            'max_attempts' : 3,
            'mode' : 'adaptive'
        }
    )
    
    s3handle = boto3.client('s3', config=my_config)

    if 's3://' in s3_url:
        s3_url = s3_url.replace('s3://', '')
    
    #'arn:aws:s3:us-east-1:560271376700:accesspoint/nccf-dev-ingest-trust-ssbox/HFRNet/CariCOOS/PYFC/Radials/RDLm_WAIN_2025_03_21_1200.ruv'
    # Split the URL into parts
    parts = s3_url.split('/')
    
    # Extract bucket name and file key
    # bucket_name = 'nccf-dev-ingest-trust-us-east-1-560271376700'
    bucket_name = parts[0]
    if 'accesspoint' in s3_url:
        bucket_name += f"/{parts[1]}"
        
    # file_key = 'HFRNet/CariCOOS/PYFC/Radials/'
    file_key = s3_url.split(f"{bucket_name}/")[1]
    
    newfpath = f"{dir_dest}/{file_name}"
    _log.info(f"--> s3handle.download_file({bucket_name}, {file_key}/{file_name}, {newfpath})")
    try:
        s3handle.download_file(bucket_name, f"{file_key}/{file_name}", newfpath)
        _log.info(f"\n Finished download_file from s3 {file_name} \n")
    except Exception as exc:
        msg = f"ERROR: Could not download file from s3: {file_key}/{file_name}; {exc}"
        _log.error(msg)
        
    return newfpath
    
def get_s3_directory_path(time, process, configObj):
    """
        Set the s3 output directory structure
    """
    year = time.year
    month = time.month
    day = time.day
    domain = configObj.domain
    res = configObj.resolution
    prod_short_name = constsHFR.PRODUCT_SHORT_NAMES[f'{process}']
    folder = ''
    if 'intermed' not in process:
        folder = 'HFRNet'
    else:
        folder = 'HFRNet-Intermediate'

    dir_path = f'{folder}/{domain}/{res}/{prod_short_name}/{year}/{month}/{day}'

    return dir_path
        
def copy_file_to_s3(s3_loc, file_name, configObj, time, metaDataObj, process):
    """    
    Copy the output file with metadata to S3 Results bucket
    """
    _log.info(f">>> s3_url={s3_loc}")

    s3_url = s3_loc.replace('s3://', '')
    
    my_config = Config(
        retries = {
            'max_attempts' : 3,
            'mode' : 'adaptive'
        }
    )
    
    s3handle = boto3.client('s3', config=my_config)

    #strip the start time and format it for CMR metadata 
    start_time_strip = str(file_name).split("_")[-3].replace('s','')
    start_time_format = datetime.strptime(start_time_strip, constsHFR.NCCF_FORMAT)
    start_time = datetime.strftime(start_time_format, "%Y-%m-%dT%H:%M:%S.%f")
    start_time = start_time[:-3] #remove the last zeros of milliseconds

    prod_short_name = constsHFR.PRODUCT_SHORT_NAMES[f'{process}']
    uuid = metaDataObj.uuid
    sha384_hash = hashlib.sha384(open(str(file_name), "rb").read()).hexdigest()
    sha256_hash = hashlib.sha256(open(str(file_name), "rb").read()).hexdigest()
    md5_hash = hashlib.md5(open(str(file_name), "rb").read()).hexdigest()

    ExtraArgs_dict={
        "Metadata":
        {
            "Region": f"{configObj.domain}",
            "Resolution": f"{configObj.resolution}",
            "Date": f"{time}",
            "ProductShortName": f"{prod_short_name}",
            "observationstarttime": f"{start_time}",
            "UUID": f"{uuid}",
            "SHA256": f"{sha256_hash}",
            "SHA384": f"{sha384_hash}",
            "MD5": f"{md5_hash}"
        }
    }
    
    dir_path = get_s3_directory_path(time, process, configObj)
    file_key = f"{dir_path}/{file_name.name}"

    _log.info(f"--> s3handle.upload_file(Filename= {file_name}, "
        f"Bucket={s3_url}, Key={file_key}, ExtraArgs={ExtraArgs_dict})")
    
    s3handle.upload_file(
        Filename= f"{file_name}",
        Bucket=f"{s3_url}",
        Key=file_key,
        ExtraArgs=ExtraArgs_dict
    )
    _log.info(f"\n Finished copying {file_name} to s3 \n\n")

#def check_time_len_db(check_time, configObj):
 #   """
 #      Update the timestamp for db_lock if it has been longer than the set time limit (constsHFR.process_time)
 #      Return updated timestamp if db has been updated, else the same time
#   """
#    time_diff = current_datetime() - check_time
#    if time_diff > constsHFR.process_time:
#        update_db_lock(configObj)
#        return current_datetime()
#else:
 #       return check_time
    
def check_lock(results):
    """
       Check if the database lock is valid
    """
    ct = current_datetime()
    process_lock = results['process_running'][0]
    ct_temp = results['exe_time'][0]
    process_stime = ct_temp.replace(tzinfo=timezone.utc)
    
    time_diff = ct - process_stime
    ret_val = False
    if process_lock:
        ret_val = True

        if time_diff > constsHFR.process_time:
            # The process lock is still true in the database, but the time since the setting is longer than the time set in the constsHFR.
            # This means the process ended before it could reset the database, so either crashed or some other problem.
            ret_val = False

    return ret_val
