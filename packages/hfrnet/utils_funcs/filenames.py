"""filenames.py"""

import logging
import calendar
from pathlib import Path
from copy import deepcopy
from hfrnet.utils_funcs.lib_rtv import FileLocations
from hfrnet.utils_funcs.utility import current_datetime, copy_file_from_s3
from hfrnet.utils_funcs import constsHFR
from hfrnet.db_tools.db_tables import get_files_list_intem_table

_log = logging.getLogger()

def filenames(configObj, rtvProcessObj, fileLocObj, time, process=None,
              subprocess=None):
    """
     FILENAMES Generate process paths & filenames

        filenames(configObj, rtvProcessObj, fileLocObj, time, process, 
                  subprocess)
        updates or adds fields to the c.total structure which define the paths
        and file names for all files to be exported (MAT, ASCII, & NetCDF) for
        the given process, domain, resolution, and timestamp.

        Unless process is provided, the process defined in rtvProcessObj is used
        to determine the process to return filenames and paths for.  Otherwise,
        if process is provided, filenames and paths for the named process are
        returned. Valid process names are 'rtv', 'stc' and 'lta'.  The
        additional parameter subprocess is only required for 'lta' where
        possible options are 'month' or 'year'.

        HF-Radar Network
        Scripps Institution of Oceanography
        Coastal Observing Research and Development Center
    """

    retFileLoc = deepcopy(fileLocObj)
    # Define process based on input
    # Use optional input, if provided
    if process is not None:

        # Verify subprocess is provided for lta
        if process.casefold() == 'lta'  and  subprocess is None:
            _log.fatal("Subprocess input required for lta")
            raise ValueError("Subprocess input required for lta")

    else:
        # Otherwise, obtain from configuration structure

        # Verify process field & name are defined in config structure
        if rtvProcessObj.name:
            process = rtvProcessObj.name.casefold()

            # Verify subprocess is defined in config for lta
            if process == 'lta':
                if rtvProcessObj.subprocess_name:
                    subprocess = rtvProcessObj.subprocess_name.casefold()
                else:
                    _log.fatal("Undefined subprocess field or key in "
                               "configuration structure,(required for lta)")
                    raise ValueError("Subprocess input required for lta")
        else:
            _log.fatal("Undefined process name in configuration structure")
            raise ValueError(f"Invalid process name: {process}")

    # Obtain process specific paths & filenames
    if process == 'rtv':
        retFileLoc = getRtvFilenames(fileLocObj, configObj, rtvProcessObj, time)

    elif process ==  'stc':
        retFileLoc = getStcFilenames(fileLocObj, configObj, rtvProcessObj, time)

    elif process == 'lta':

        if subprocess.casefold() == (constsHFR.CONFIGS_DICT['month']).casefold():
            retFileLoc = getLtaMonthFilenames(fileLocObj, configObj,
                                              rtvProcessObj, time)

        elif subprocess.casefold() == (constsHFR.CONFIGS_DICT['year']).casefold():
            retFileLoc = getLtaYearFilenames(fileLocObj, configObj,
                                             rtvProcessObj, time)
        else:
            msg = f"Unknown subprocess {subprocess}"
            _log.fatal(msg)
            raise ValueError(f"Invalid subprocess name: {subprocess}")
    else:
        msg = f"Unknown process {process}"
        _log.fatal(msg)
        raise ValueError(f"Invalid process name: {process}")

    return retFileLoc


def find_file(domain, resolution, method, time, directory, file_format):
    """search for file which matches config"""

    data_file = Path(directory)
    search_par = (f"rtv_*{domain}*{resolution}*"
                  f"{method}*{time.strftime('%Y_%m_%d_%H%M')}*"
                  f".{file_format}")
    if file_format == 'nc':
        search_par = (f"{time.strftime('%Y%m%d%H%M')}"
                      f"*_hfr"
                      f"*_{domain}"
                      f"*_{resolution}"
                      f"*_rtv"
                      f"*_{method}"
                      f"*.{file_format}")

    data_file = list(data_file.glob(f"{search_par}"))
    if len(data_file) == 1:
        return data_file[0]

    data_file_no25hr = [iFile for iFile in data_file if '25hr' not in str(iFile)]
    if len(data_file_no25hr) == 1:
        return data_file_no25hr[0]

    msg = f"{file_format} not found: {data_file_no25hr}, {directory}/{search_par}"
    _log.warning(msg)
    return ""

def find_intermediate_file(directory, search_par, file_format):
    """get the monthSum file"""
    
    #data_file = list(directory.glob(f"{search_par}.{file_format}"))
    data_file = list(directory.glob(f"{search_par}"))
    if len(data_file) == 1:
        return data_file[0]

    if len(data_file) > 1:
        msg = f"Mutiple matching files: {data_file}"
        _log.warning(msg)
        return None

    msg = f"File not found: {directory}/{search_par}.{file_format}"
    _log.warning(msg)
    return None

def get_database_interm_file(retObj, configObj, t, find_proc_name):
    """Get the intermediate input file"""

    fileList, nRows = get_files_list_intem_table(configObj, t, find_proc_name)
    
    if nRows == 1:
        copy_file_from_s3(fileList['dir'][0], fileList['name'][0], retObj.interm_local_dir)
        retObj.input_file = Path(retObj.interm_local_dir, fileList['name'][0])
        if retObj.interm_local_dir:
            retObj.input_file = Path(retObj.interm_local_dir, fileList['name'][0])
    else:
        msg = f"Found {nRows} (zero or multiple) files for settings: {find_proc_name}, time::{t}"
        retObj.input_file = None
        _log.error(msg)


# RTV paths & files
def getRtvFilenames(fileLocObj, configObj, rtvProcessObj, t):
    """files needed for the 'rtv' running mode"""

    retObj = fileLocObj
    domain = configObj.domain.casefold()
    resolution = configObj.resolution.casefold()
    method = rtvProcessObj.method.casefold()
    
    # Output NetCDF
    start_time = t.strftime(constsHFR.NCCF_FORMAT)[:-5]
    end_time = t.strftime(constsHFR.NCCF_FORMAT)[:-5]
    creation_time = current_datetime().strftime(constsHFR.NCCF_FORMAT)[:-5]
    name_nccf = (f"rtv-{domain}-{resolution}-{method}_v1r0_hfr"
                 f"_s{start_time}_e{end_time}_c{creation_time}.nc")
    retObj.output_ncfile = Path(retObj.output_dir, name_nccf)

    retObj.input_file = None
    
    #intermediate input
    get_database_interm_file(retObj, configObj, t, 'rtv')
    
    #search local if not found in database
    if retObj.input_file is None:
        tmp_file = find_intermediate_file(fileLocObj.interm_local_dir, f"*{domain}*{resolution}*intermediate_s{start_time}_e{end_time}*","nc")
        retObj.input_file = tmp_file
    
    # Intermediate NetCDF
    retObj.intermed_filename = (f"rtv-{domain}-{resolution}-{method}_v1r0_hfr_intermediate"
                                f"_s{start_time}_e{end_time}_c{creation_time}.nc")

    retObj.intermed_filepath = Path(retObj.output_dir, retObj.intermed_filename)

    _log.info(f"------------- getRtvFilenames ")
    _log.info(f"------------- output_ncfile :: {retObj.output_ncfile}")
    _log.info(f"------------- intermed_filepath :: {retObj.intermed_filepath}")
    return retObj


# STC paths & files
def getStcFilenames(fileLocObj, configObj, rtvProcessObj, t):
    """files for 'stc' running method"""

    retObj = fileLocObj
    domain = configObj.domain.casefold()
    resolution = configObj.resolution.casefold()

    start_time = t.strftime(constsHFR.NCCF_FORMAT)[:-5]
    end_time = t.strftime(constsHFR.NCCF_FORMAT)[:-5]
    creation_time = current_datetime().strftime(constsHFR.NCCF_FORMAT)[:-5]
    retObj.ncfilename = (f"rtv-{domain}-{resolution}-25h-avg"
                         "_v1r0_hfr"
                         f"_s{start_time}_e{end_time}_c{creation_time}.nc")

    #input NetCDF
    get_database_interm_file(retObj, configObj, t, 'rtv')

    #search local if intermediate not found in database
    if retObj.input_file is None:
        retObj.input_file = find_intermediate_file(retObj.interm_local_dir, f"*{domain}*{resolution}*intermediate_s{start_time}_e{end_time}*", "nc")
    
    # Output NetCDF
    retObj.output_ncfile = Path(fileLocObj.output_dir, retObj.ncfilename)

    #intermediate file
    retObj.intermed_filename = (f"rtv-25HrSum_{configObj.domain}_"
                                f"{configObj.resolution}_{rtvProcessObj.method}"
                                f"_s{start_time}_e{end_time}_c{creation_time}.nc")

    retObj.intermed_filepath = Path(fileLocObj.output_dir, retObj.intermed_filename)

    return retObj

# LTA Month paths & files
def getLtaMonthFilenames(fileLocObj, configObj, rtvProcessObj, t):
    """files for the 'month' average calc"""

    retObj = fileLocObj
    domain = configObj.domain.casefold()
    resolution = configObj.resolution.casefold()
    
    ### Output files
    dayOfWeek, last = calendar.monthrange(t.year, t.month)
    start_time = (t.replace(day=1, hour=0, minute=0, second=0)).strftime(constsHFR.NCCF_FORMAT)[:-5]
    end_time = (t.replace(day=last, hour=23, minute=59, second=59)).strftime(constsHFR.NCCF_FORMAT)[:-5]
    creation_time = current_datetime().strftime(constsHFR.NCCF_FORMAT)[:-5]
    retObj.ncfilename = (f"rtv-{domain}-{resolution}"
                         "-mon-avg_v1r0_hfr"
                         f"_s{start_time}_e{end_time}_c{creation_time}.nc")

    #Input rtv file
    get_database_interm_file(retObj, configObj, t, 'rtv')
    
    #Search in local directory if file not found in database
    if retObj.input_file is None:
        tmp_start = t.strftime(constsHFR.NCCF_FORMAT)[:-5]
        tmp_end = tmp_start
        retObj.input_file = find_intermediate_file(retObj.interm_local_dir, f"*{domain}*{resolution}*intermediate*s{tmp_start}_e{tmp_end}*", "nc")
    
    #intermediate file
    retObj.intermed_filename = (f"rtv-monthSum_{domain}_"
                                f"{resolution}_{rtvProcessObj.method}"
                                f"_s{start_time}_e{end_time}_c{creation_time}.nc")

    retObj.intermed_filepath = Path(fileLocObj.output_dir, retObj.intermed_filename)

    # NetCDF (average)
    retObj.output_ncfile = Path(retObj.output_dir, retObj.ncfilename)

    return retObj

# LTA Year paths & files
def getLtaYearFilenames(fileLocObj, configObj, rtvProcessObj, t):
    """files for the 'year' average calculation"""

    retObj = FileLocations()
    domain = configObj.domain.casefold()
    resolution = configObj.resolution.casefold()
    retObj.output_dir = fileLocObj.output_dir
    retObj.interm_local_dir = fileLocObj.interm_local_dir

    #find_proc_name = "lta-month"
    get_database_interm_file(retObj, configObj, t, 'lta-month')

    #intermediate file
    retObj.intermed_filename = (f"rtv-annualSum_{domain}_"
                                f"{resolution}_{rtvProcessObj.method}_"
                                f"{t.strftime('%Y%m')}.nc")

    retObj.intermed_filepath = Path(fileLocObj.output_dir, retObj.intermed_filename)

    #Output NetCDF
    start_time = (t.replace(month=1, day=1, hour=0, minute=0, second=0)
                  .strftime(constsHFR.NCCF_FORMAT))[:-5]
    end_time = (t.replace(month=12, day=31, hour=23, minute=59, second=59)
                .strftime(constsHFR.NCCF_FORMAT))[:-5]
    creation_time = current_datetime().strftime(constsHFR.NCCF_FORMAT)[:-5]
    retObj.ncfilename = (f"rtv-{domain}-{resolution}-ann-avg_v1r0_hfr_"
                         f"s{start_time}_e{end_time}_c{creation_time}.nc")

    retObj.output_ncfile = Path(retObj.output_dir, retObj.ncfilename)

    return retObj
