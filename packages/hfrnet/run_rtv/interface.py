#!/usr/bin/env python
""" HFRnet Unit1:run_config Interface

@Description:
    *** Update to add description about unit ***
    Responsible for interfacing with unit 1

@History:
    - Letitia Soulliard, July, 26 2021, Created
    - brian.helgans, Sep 23, 2021, Reworked
    *** Update to add your history ***
"""
# *** Update to today ***
__updated__ = "2024-07-23"

import logging
import os
from pathlib import Path
from datetime import datetime

import aim

#hfrnet modules
from hfrnet.db_tools.db_tables import (read_domain, read_resolution, read_methods,
                                       check_lock_process, clear_state_table,
                                       clear_db_lock)
from hfrnet.utils_funcs.utility import (setup_log_filename, current_datetime, Set_s3_output_bucket
                                        ,generate_time_spans)
from hfrnet.utils_funcs.lib_rtv import (ConfigureVals, Metadata, RtvInfo,
                                        FileLocations, RtvProcess, RtvTotals,
                                        DatabaseError)
from hfrnet.utils_funcs.lib_sumavg import StcLtaInfo
import hfrnet.run_rtv.processRtv as processRtv
from hfrnet.db_tools.db_manager import db_manager, set_db_info

_log = logging.getLogger()


class Interface(aim.Interface):
    """ Defines the interface to run unit1.

    (This class is inheriting some of its functionality from aim.Interface.)

    This comment section is called a "docstring". It's an important feature of
    python.
    The first line brief.
    You may write as much of a detailed description as you like in these lines
    here.

    *** Update docstring to be descriptive and useful ****

    """

    # initialization of the Interface class expects "template"
    # for validating the incoming configuration file
    # *** Update with your needed configuration ****
    template = {
        'processing': {
                'domain': str,
                'resolution': str,
                'batch_processing': bool,
        },
        'time': {
                'start_date': str,
                'end_date': str,
        },
        'production': {
                'site': str,
                'environment': str,
                'version': str,
        },
        'directory': {
            'algorithm_dir': str,
            'log': str,
            'output': str,
            'radial_local_dir': str,
            'interm_local_dir': str,
            'output_s3_bucket': str,
            'output_intermed_s3_bucket': str,
        },
        'databases': {
            'run_env': str,
            'user': str,
            'host': str,
            'port': int,
            'password': str,
            'ssl_ca': str,
            'region': str,
            'config_dbname': str,
            'radial_dbname': str,
        },
    }

    mconfigureVals = ConfigureVals("", "")
    mrtvInfo = RtvInfo()
    mstcLtaInfo = StcLtaInfo()
    mstcInfo = mstcLtaInfo.stcInfo
    mltaInfo = mstcLtaInfo.ltaInfo
    mnetcdf_metadata = Metadata()
    fileLocObj = FileLocations()
    siteInfoObj = []
    rtvProcessObj = RtvProcess()
    compTotObj = RtvTotals()
    lock_process_flag = False

    def setup(self):
        """ Generate a configuration for the science code.
        This method exists to transform the incoming configuration
        into the configuration understood by the science executable.

        NOTE: The idea is for operations to provide a simple config
            (self.config) then this code handles any additional logic while we
            generate the "real" configuration file.

        *** Update docstring to be descriptive and useful ****
        """
        #--------------- check if
        print(f"---------------------------------------------")
        print(f" set_db_info::Running Env is :: {self.config['databases.run_env']}")
        if self.config['databases.run_env'] == 'ao':
            #--- this must be done in order for AO to move anything outside the AO sys
            #--- default path is /workflow/data/
            print(f"AO_WORKFLOW_DATA_DIR is defined: {os.getenv('AO_WORKFLOW_DATA_DIR')}")
        # else:
        #     #---- default for running inside the docker
        #     self.config['directory.log'] = '/home/WORKING_DIR/logs'
        #     self.config['directory.output'] = '/home/WORKING_DIR/output'
        #     print('Setting log and output dirs to /home/WORKING_DIR')

        #----------------------

        self.mconfigureVals.domain = self.config['processing.domain']
        self.mconfigureVals.resolution = self.config['processing.resolution']
        log_dir = Path(self.config['directory.log'])
        log_dir.mkdir(parents=True, exist_ok=True)

        self.mconfigureVals.product_version = self.config['production.version']
        self.mconfigureVals.production_environment = self.config['production.environment']
        self.mconfigureVals.production_site = self.config['production.site']

        setup_log_filename(self, f"hfrnet_{self.mconfigureVals.domain}"
                            f"_{self.mconfigureVals.resolution}")
        # ------ setup the rtvproc connection
        set_db_info(self.config, self.mconfigureVals)

        # ---- Set the output and intermediate s3 bucket locations
        self.mconfigureVals.output_s3_loc = self.config['directory.output_s3_bucket']
        self.mconfigureVals.output_intermed_s3_loc = self.config['directory.output_intermed_s3_bucket']
        
        # ---- Set the intermedite files s3 bucket based on the running env id 
        Set_s3_output_bucket(self.mconfigureVals)
        
        #====== delete this
        # clear_state_table(self.mconfigureVals)

        #Check if the process is locked
        _log.info("=============================================")
        _log.info("=============================================")
        if check_lock_process( self.mconfigureVals):
            self.lock_process_flag = True
            return
        _log.info("=============================================")
        _log.info("=============================================")


        _log.info("-------------------------------------- ")
        _log.info(f"Start processing HFRnet for domain::"
                    f"{self.mconfigureVals.domain} "
                    f"and Resolution::{self.mconfigureVals.resolution} ")
        _log.info(log_dir)
        # set the runtime to the start time
        self.mconfigureVals.runTime = current_datetime()
        # self.mconfigureVals.runTime = datetime.strptime(self.config['time.start_date'],'%Y%m%d%H%M%S%f')
        # This is used when reporcessing a patch of time in the past
        self.mconfigureVals.reprocess = False
        if self.config['processing.batch_processing']:
            self.mconfigureVals.times = generate_time_spans(self.config['time.start_date'],
                                                            self.config['time.end_date'])
            self.mconfigureVals.reprocess = True



    def process(self):
        """ This executes the algorithm's executable (for this unit).

        *** Update docstring to be descriptive and useful ****
        python -m hfrnet.run_config config_hfr_run_config.yml
        """
        # Terminate if the process is locked
        _log.info("=============================================")
        _log.info("=============================================")
        self.output_info['status'] = "good"
        if self.lock_process_flag:
            _log.info(f" Process lock = true, Run can't be executed")
            return

        _log.info(f" Process lock is set, Process is running")
        _log.info("=============================================")
        _log.info("=============================================")

        # ------ setup the rtvproc connection

        # get the analysis parametrers for domain, res, rtv,stc,lta
        with db_manager(self.mconfigureVals.dbObject) as db_class:

            # Check for valid domain
            try:
                read_domain(db_class, self.mconfigureVals)
            except DatabaseError:
                _log.info(f"No domain {self.mconfigureVals.domain} description were found or "
                        f"database connection failed")
                return

            # ---------------------------------
            # Check for valid resolution
            try:
                read_resolution(db_class, self.mconfigureVals)
            except DatabaseError:
                _log.info(f"No domain {self.mconfigureVals.resolution}  were found "
                        f"or database connection failed")
                return
            # ---------------------------------
            # Check for valid resolution
            process_list = []
            read_methods(db_class, self.mconfigureVals, self.mrtvInfo,
                        self.mstcInfo, self.mltaInfo,process_list)

        self.set_file_locations(self.fileLocObj)

        try:
            processRtv.processRtv(self.mconfigureVals,
                                  self.siteInfoObj,
                                  self.fileLocObj,
                                  process_list,
                                  self.mrtvInfo,
                                  self.mstcLtaInfo,
                                  self.compTotObj)
        except Exception as exp:
            _log.error(f"Could not run procesRtv: {exp}")

        clear_db_lock(self.mconfigureVals)
        self.output_info['status'] = "good"

    def reformat(self):
        """ we sometimes want to reformat the output after processing runs.

        *** Update docstring to be descriptive and useful ****
        """

    def output(self):
        """ Inform OPS of any remaining files it should know about.
        Add any files that need to be pulled out of the container and saved
        into the output_info hand off object.  Create a FileToken object for
        each file and give each file a useful label value.

        *** Update docstring to be descriptive and useful ****
        """

    def set_file_locations(self, fileLocObj):
        """
            Set all the directory locations
        """
        _log.info(f" ---- Setting up the dirs")
        algo_dir = Path(self.config['directory.algorithm_dir'])
        _log.info(f" ---- algo_dir::{algo_dir}")

        fileLocObj.landfile = algo_dir / 'ancillary_data/land_data'
        fileLocObj.gridfile = algo_dir / 'ancillary_data/grid_data'
        _log.info(f" ---- fileLocObj.landfile::{fileLocObj.landfile}")
        _log.info(f" ---- fileLocObj.gridfile::{fileLocObj.gridfile}")

        # --- output dirs to save the nc, asc, intermediate files
        fileLocObj.output_dir = Path(self.config['directory.output'])
        fileLocObj.output_dir.mkdir(parents=True, exist_ok=True)
        _log.info(f" ---- fileLocObj.output_dir::{fileLocObj.output_dir}")

        _log.info(f" ---- directory.radial_local_dir::{self.config['directory.radial_local_dir']}")
        _log.info(f" ---- directory.interm_local_dir::{self.config['directory.interm_local_dir']}")

        if self.config['directory.radial_local_dir']:
            fileLocObj.radial_local_dir = Path(self.config['directory.radial_local_dir'])
            _log.info(f" ---- fileLocObj.radial_local_dir::{fileLocObj.radial_local_dir}")
        else:
            fileLocObj.radial_local_dir = Path('/home/WORKING_DIR/input/radials')
            _log.info(f" ---- fileLocObj.radial_local_dir")

        if self.config['directory.interm_local_dir']:
            fileLocObj.interm_local_dir = Path(self.config['directory.interm_local_dir'])
        else:
            fileLocObj.interm_local_dir = Path('/home/WORKING_DIR/input/intermediate')
            _log.info(f" ---- fileLocObj.interm_local_dir")

        fileLocObj.radial_local_dir.mkdir(parents=True, exist_ok=True)
        fileLocObj.interm_local_dir.mkdir(parents=True, exist_ok=True)
            
