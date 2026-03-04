#!/usr/bin/env python

"""processRtv"""

import logging
from datetime import timedelta
from pathlib import Path
import numpy as np

from hfrnet.utils_funcs.lib_rtv import RtvProcess
from hfrnet.run_rtv import rtv
from hfrnet.utils_funcs.filenames import filenames
from hfrnet.run_rtv.sumAvg import SumAndAvg
from hfrnet.run_rtv.stcSaveNetcdf import stcSaveNetcdf
from hfrnet.run_rtv.ltaSaveNetcdf import ltaSaveNetcdf
from hfrnet.run_rtv.saveNetcdf import saveNetcdf
from hfrnet.run_rtv.rtvProcessMetadata import rtvProcessMetadata
from hfrnet.utils_funcs.utility import (load_land, load_grid, ltaRunConfig,
                                        current_time, current_datetime,
                                        copy_file_to_s3)
from hfrnet.db_tools.db_tables import (update_state_time, record_output_files,
                                       update_db_lock, check_time_len_db)

_log = logging.getLogger()

def processRtv(configObj, siteInfoObj, fileLocObj, rtvProcessObj, rtvInfoObj,
               stcLtaInfoObj, compTotObj):
    """

    Processes all RTV products

    processRtv( domain, resolution, configFunction ) processes all RTV
    products for the given domain and resolution based on configuration
    parameters obtained by configFunction.  This form is typically used
    in near real-time processing.  Process locking is mandatory and
    prevents concurrent instances for the given domain and resulution from
    running.

    processRtv( ..., reprocessTimes, reprocessLock ) is the form used
    during reprocessing where additional inputs reprocessTimes and
    reprocessLock define the times to be reprocessed and whether or not
    process locking should be used. Process locking is optional during
    reprocessing and has a default value of true.  Whether or not
    locking should be used depends on whether or not the reprocessing
    overlaps with data that are still within the near real-time processing
    window.  The same lock file is used for near-real time processing and
    reprocessing.  The reprocessTimes input should be a vector of 1 or
    more datetime values.

    Inputs:
        domain         - character array
        resolution     - character array
        configFunction - character array
        reprocessTimes - datetime vector (optional)
        reprocessLock  - logical (optional, default=true)

    The configFunction must be a function in the runtime environment's
    path or otherwise be defined with its full path. It must return all
    required configuration parameters for this and any subsequent
    functions. A general overview is provided in configFunction while
    operational branches serve as working examples.

    Processing is defined by the configuration structure's processes field
    which is a table of processes listed in order of processing. Supported
    processing options are real-time vector (rtv), sub-tidal current
    (stc), and long-term averages (lta).  Only the unweightted
    least-squares (uwls) method is supported.  Reprocessing parameters are
    saved to the configuration structure's reprocess field as a map.

    Use runRtv to call processRtv in batch mode from the command-line.

    """

    #time for db lock checking
    process_start_time = current_datetime()
    
    process = RtvProcess()

    domain = configObj.domain.lower()
    #load land and grid files
    land = load_land(fileLocObj.landfile, domain)
    grid = None
    gridvar = f'{domain}{configObj.resolution}'
    try:
        grid = load_grid(fileLocObj.gridfile, domain,
                         configObj.resolution, rtvInfoObj)
        if len(grid.size) < 1:
            grid.size = np.array([0, 0], dtype=int)
    except Exception as e:
        errmsg = f'Error loading variable {gridvar} from {fileLocObj.gridfile}: {str(e)}'
        _log.error(errmsg)

    newRtvFiles = []
    nProcesses = len(rtvProcessObj)
    for iProcess in range(nProcesses):

        process = rtvProcessObj[iProcess]

        if process.method != 'uwls':
            message = f"ERROR: Only 'uwls' methods are supported, not {process.method}"
            _log.warning(message)
            continue

        if process.name.casefold() == 'rtv':
            stime = current_datetime()
            _log.info("#########################################")
            _log.info( f"processing:: {process.name.casefold()}")
            _log.info( f"{stime}")
            _log.info("#########################################")

            #update the timestamp for db_lock if it has been longer than the set time limit (constsHFR.process_time)
            process_start_time = check_time_len_db(process_start_time, configObj)
                           
            newRtvFiles = rtv.rtv(configObj, siteInfoObj, fileLocObj,
                                  process, rtvInfoObj, compTotObj, land, grid)
            if newRtvFiles is None:
                _log.info('No rtv files created or updated')
            else:
                msg = f'Created or updated {len(newRtvFiles)} rtv files'
                _log.info(msg)

            rtvTime = current_datetime()
            msg = "\n" + "="*80 + f"\nRtv execution time:  {(rtvTime - stime)}\n" + "="*80
            _log.info(msg)

        if process.name.casefold() == 'stc' and newRtvFiles is not None:

            _log.info("#########################################")
            _log.info( f"processing:: {process.name.casefold()} , newRtvFiles={len(newRtvFiles)}")
            _log.info("#########################################")
            for iTime in newRtvFiles:
                #for execution time logging
                stime = current_datetime() # datetime obj

                #update the timestamp for db_lock if it has been longer than the set time limit (constsHFR.process_time)
                process_start_time = check_time_len_db(process_start_time, configObj)

                #offset time to the center of the 25 hr window
                center_time = iTime - timedelta(hours=12)
                _log.info("-----------------------------------")
                _log.info(f"--- stime:{stime}::center_time:{center_time}::---")
                sumAvg = SumAndAvg('25 Hour', configObj, process,
                                   fileLocObj, center_time, stcLtaInfoObj)
                sumObj = sumAvg.get_sum()
                avgObj = sumAvg.get_avg()
                
                if avgObj is not None:
                    
                    inputs = [Path(f.input_file).name for f in sumAvg.fileList if f.input_file is not None]
                    
                    metaDataObj = rtvProcessMetadata(process, configObj)
                    fileNameList = filenames(configObj, process,
                                             fileLocObj, center_time)
                    
                    stcInfoObj = stcLtaInfoObj.stcInfo
                    
                    #save intermediate file
                    allInfo = {'metaDataObj': metaDataObj.to_dict(),
                               'configObj': configObj.to_dict(),
                               'stcInfoObj': stcInfoObj.to_dict(),
                               'process': process.to_dict()}
                    allInfo_dict = {'c': allInfo, 'tc': center_time, 'A': sumObj.to_dict()}
                    _log.info(f"--- saveNetcdf:{fileNameList.intermed_filepath}::---")
                    saveNetcdf(fileNameList.intermed_filepath, allInfo_dict)
                    _log.info("Saving stc total intermediate files in netcdf format")
                    #copy intermediate file to s3 bucket
                    copy_file_to_s3(configObj.output_intermed_s3_loc, fileNameList.intermed_filepath, configObj, center_time, metaDataObj, 'stc-intermed')
                    
                    #Save the average file
                    avgObj.land = land
                    avgObj.grid = grid
                    stcSaveNetcdf(metaDataObj, configObj,
                                  fileNameList, stcInfoObj,
                                  process, center_time, avgObj, inputs)
                    #copy file to s3 bucket
                    copy_file_to_s3(configObj.output_s3_loc, fileNameList.output_ncfile, configObj, center_time, metaDataObj, 'stc')
                    
                    stcTime = current_time() # time in constsHFR.DATETIME_FORMAT
                    _log.info(f"Update the process {process.name} time {stcTime} in the state table")
                    update_state_time(configObj, process.name.casefold(), stcTime)
                    record_output_files(configObj, fileNameList.intermed_filename, process.name.casefold(), 'stc-intermed')
                    
                    stcTime = current_datetime() # datetime obj
                    msg = "\n" + "="*80 + f"\nSTC execution time:  {(stcTime - stime)}\n" + "="*80
                    _log.info(msg)
                    
                else:
                    _log.error("Could not save the sum nor average file because the average was not calculated.")
                
        if process.name.casefold() == 'lta' and newRtvFiles is not None:

            _log.info("#########################################")
            _log.info( f"processing:: {process.name.casefold()} , newRtvFiles={len(newRtvFiles)}")
            _log.info("#########################################")
            for iTime in newRtvFiles:

                doMonthly, doYearly, monthTime, yearTime = ltaRunConfig(iTime, configObj, process)

                if doMonthly:
                    
                    #for execution time logging
                    stime = current_datetime() # time in constsHFR.DATETIME_FORMAT
                    
                    #update the timestamp for db_lock if it has been longer than the set time limit (constsHFR.process_time)
                    process_start_time = check_time_len_db(process_start_time, configObj)
                    
                    #calculation
                    sumAvg = SumAndAvg("monthly", configObj, process,
                                       fileLocObj, monthTime, stcLtaInfoObj)
                    sumObj = sumAvg.get_sum()
                    avgObj = sumAvg.get_avg()

                    if avgObj is not None:
                        
                        inputs = [Path(f.input_file).name for f in sumAvg.fileList if f.input_file is not None]
                        
                        #metadata and filenames for output
                        metaDataObj = rtvProcessMetadata(process, configObj)
                        fileNameList = filenames(configObj, process,
                                                 fileLocObj, monthTime)
                        
                        #save intermediate file
                        allInfo = {'metaDataObj': metaDataObj.to_dict(),
                                   'configObj': configObj.to_dict(),
                                   'stcLtaInfoObj': stcLtaInfoObj.to_dict(),
                                   'process': process.to_dict()}
                        allInfo_dict = {'c': allInfo, 't': iTime, 'S': sumObj.to_dict()}
                        
                        _log.info("------------- Saving monthly total files in netcdf "
                                  "format")
                        saveNetcdf(fileNameList.intermed_filepath, allInfo_dict)
                        #copy intermediate file to s3 bucket
                        copy_file_to_s3(configObj.output_intermed_s3_loc, fileNameList.intermed_filepath, configObj, iTime, metaDataObj, 'monthly-intermed')
                        record_output_files(configObj, fileNameList.intermed_filename, process.name.casefold(), 'monthly-intermed')
                        
                        #save final file
                        _log.info("------------- Saving intermediate monthly total files "
                                  "in netcdf format")
                    
                        avgObj.land = land
                        avgObj.grid = grid
                        ltaSaveNetcdf(metaDataObj, configObj,
                                      fileNameList, stcLtaInfoObj,
                                      process, iTime, avgObj, inputs)
                        #copy file to s3 bucket
                        copy_file_to_s3(configObj.output_s3_loc, fileNameList.output_ncfile, configObj, iTime, metaDataObj, 'monthly')
                        
                        monthlyTime = current_time() # time in constsHFR.DATETIME_FORMAT
                        _log.info(f"Update the process {process.name} time "
                                  f"{monthlyTime} in the state table")
                        update_state_time(configObj, process.name.casefold(), monthlyTime)
                        
                        monthlyTime = current_datetime() # datetime obj
                        msg = ("\n" + "="*80 + "\nMonthly average execution time:"
                               f"{(monthlyTime - stime)}\n" + "="*80)
                        _log.info(msg)
                    else:
                        _log.error("Could not save the monthly sum nor average file.")

                if doYearly:

                    #for execution time logging
                    stime = current_datetime() # datetime obj

                    #calculation
                    sumAvgYear = SumAndAvg("annual", configObj, process,
                                       fileLocObj, yearTime, stcLtaInfoObj)
                    sumObjYear = sumAvgYear.get_sum()
                    avgObjYear = sumAvgYear.get_avg()

                    if avgObjYear is None:

                        inputs = [Path(f.input_file).name for f in sumAvgYear.fileList if f.input_file is not None]
                        
                        #metadata and filenames for output
                        metaDataObj = rtvProcessMetadata(process, configObj)
                        fileNameList = filenames(configObj, process,
                                                 fileLocObj, yearTime)
                        #save final file
                        _log.info("------------- Saving annual total files in netcdf format")
                        avgObjYear.land = land
                        avgObjYear.grid = grid
                        ltaSaveNetcdf(metaDataObj, configObj,
                                      fileNameList, stcLtaInfoObj,
                                      process, iTime, avgObjYear, inputs)
                        #copy file to s3 bucket
                        copy_file_to_s3(configObj.output_s3_loc, fileNameList.output_ncfile, configObj, iTime, metaDataObj, 'annual')
                        
                        yearlyTime = current_time() # time in constsHFR.DATETIME_FORMAT
                        _log.info(
                            f"Update the process {process.name} time {yearlyTime} in the state table")
                        update_state_time(configObj, process.name.casefold(), yearlyTime)
                        
                        yearlyTime = current_datetime() # datetime obj
                        msg = ("\n" + "="*80 + "\nYearly average execution time:"
                               f"{(yearlyTime - stime)}\n" + "="*80)
                        _log.info(msg)
                    else:
                        _log.error("Could not save the yearly average file.")
