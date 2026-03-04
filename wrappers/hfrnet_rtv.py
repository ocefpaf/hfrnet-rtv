"""
Program name:        hfrnet_rtv.py
Date:                10/30/2024
History:             Original
Author:              Tianzhu Qiao
Email:               tianzhu.qiao@noaa.gov
Description:         When run inside of a Docker container, this script
                     will execute the program interface and generate
                     ouput for the hfrnet algorithm.
Input:               config.yaml - A YAML file containing all
                     required variables and paths.
Files needed:        Requires the configuration file.
Output:              After a successful execution of the container, output
                     data will be available in the output directory,
                     and logs should be available in the logging
                     directory. Please read the README document for more
                     information.
Modules/subroutines: t4_utils.future.parse_config
Calling sequence:    python hfrnet_rtv.py <config_yaml>
"""

import sys
import traceback
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Union


from t4_utils.future.ccap.parse_config import parse_config

import logging
logger = logging.getLogger()

def get_logger(cfg: dict) -> logging.getLogger:
    """
    Creates a logging object.
    """

    level = logging.getLevelName(cfg['algorithm']['logging_level'])
    logger = logging.getLogger('hfrnet')
    logger.setLevel(level)
    print(f"get_logger:: {level} ")
    print(logger)

    return logger

def aim_config(cfg: dict) -> dict:
    """
    From the config file, create the
    dictionary that AIM needs in the
    handoff.
    """

    aim_cfg = dict((cfg)['algorithm'])
    
    aim_cfg['time'] ={
        'start_date': aim_cfg['coverage']['start'],
        'end_date': aim_cfg['coverage']['end']
    }

    aim_cfg.pop('coverage')

    aim_cfg['production']['version'] = cfg['info']['alg_version']

    dirs = aim_cfg.pop('ref')
    aim_cfg['directory'] = dirs

    aim_cfg.pop('io')
    aim_cfg.pop('logging_level')
    return aim_cfg

def run_aim(cfg: dict, interface_cfg: dict, logger: logging.getLogger) -> None:
    """
    Run the AIM interface
    """
    print("===============================================")
    print(cfg)
    print("===============================================")
    print(interface_cfg)
    sys.path.append(cfg['algorithm']['ref']['algorithm_dir']+'/packages/')
    print("===============================================")
    logger.info("===========  run_aim  =/===============")

    try:
        import hfrnet.run_rtv
        import aim
    except Exception as err:
        logger.error(err, exc_info=True)
        traceback.print_exc()
        sys.exit(1)
        
    try:
        aim_cfg = aim.Handoff(interface_cfg)
    except Exception as err:
        traceback.print_exc()
        logger.error(err, exc_info=True)
        sys.exit(1)
        
    logger.info('Completed succesfully: aim.Handoff(interface_config)')
    try:
        pkg_interface = hfrnet.run_rtv.interface.Interface(aim_cfg)
    except Exception as err:
        traceback.print_exc()
        logger.error(err, exc_info=True)
        sys.exit(1)
        
    logger.info('Completed succesfully: hfrnet.interface.Interface(aim_cfg)')

    try:
        pkg_interface.run_methods()
    except Exception as err:
        traceback.print_exc()
        logger.info('pkg_interface.run_methods() returned an error:')
        logger.error(err, exc_info=True)
        sys.exit(1)
    logger.info('Completed succesfully: pkg_interface.run_methods()')

def main(config_path: Union[str, Path], logger: logging.getLogger=None) -> None:
    """
    Main function that performs the following:
        1) Calls parse_config to read in the application yaml
        2) Creates a logging object by calling get_logger
        3) Creates the runtime directory
        4) Creates the AIM Handoff config
        5) Executes the aim
    """

    cfg = parse_config(config_path)

    if logger is None:
        logger = get_logger(cfg)

    logger.info('Creating AIM config')
    aim_cfg = aim_config(cfg)

    start = datetime.now(timezone.utc)
    logger.info('Start Time: %s', start)
    logger.info('Interface Config:\n%s', str(aim_cfg))

    run_aim(cfg, aim_cfg, logger)

    end = datetime.now(timezone.utc)
    run = end - start
    logger.info('End Time: %s', end)
    logger.info('Total Run Time: %f sec', run.total_seconds())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('application_yaml_path')
    args = parser.parse_args()
    print(f"args.application_yaml_path:: {args.application_yaml_path}")
    main(args.application_yaml_path)
