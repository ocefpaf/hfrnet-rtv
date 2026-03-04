""" Unit1 ***Update to unit name***

@Description:
    *** Update to describe the unit ***
    Anything needed to run unit1.
    This basically just calls the Interface. So details can usually go in that
    instead.

@Rules:
    *** Update to list your production rules ***
    - (e.g. run hourly.)
    - sample config file located under data/test/config.yaml

@History:
    - brian.helgans, Sep 23, 2021, Created
    *** Update to add your history ***
"""
# *** Update to today's date ****
__updated__ = "2021-09-23"

import argparse
import logging
import sys
import autologging
import aim
from datetime import datetime, timezone

from . import interface
from hfrnet.utils_funcs.utility import setup_log_filename

_log = logging.getLogger()

def update_nested_dict(d, key, value):
	for k, v in d.items():
		if isinstance(v, dict):
			update_nested_dict(v, key, value)
		elif k == key:
			d[k] = value

def main(my_args):
    """Command line options."""

    #
    # set up the logger
    #
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr,
        format="%(asctime)s %(levelname)s (%(name)s:%(funcName)s) %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S')

    # "Handoff" is basically just a dictionary
    # allows accessing nested data as 'directory.bin'
    # rather than having my_dict['directory']['bin']
    
    cfg = aim.Handoff(my_args.cfg)

    # --------------------------------
    #-- the call to main should include these two args
    # python -m hfrnet.run_rtv ../test_data/config_hfr.yml" -dom ushi -res 6km
    # --- check for args and update
    if my_args.dom:
        update_nested_dict(cfg.info, 'domain', my_args.dom)
    if my_args.res:
        update_nested_dict(cfg.info, 'resolution', my_args.res)
    # create an instance of this package Interface class.
    pkg_int = interface.Interface(cfg)

    # handler = setup_log_filename(pkg_int,"hfrnet")

    # call all methods, rather than one at a time.
    # PyDevs may call each method individually if it is somehow beneficial.
    pkg_int.run_methods()
    
    # handler.close()


# main
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='This executable is capable of running all units of this'
                    'package.')
    parser.add_argument("cfg", help="the config file")
    parser.add_argument("-d", "--debug", dest='debug',
                        action='store_true', help="set debug log level")
    parser.add_argument("-t", "--trace", dest='trace',
                        action='store_true', help="set trace log level")
    # --------------------------------
    #-- the call to main should include these two args
    # python -m hfrnet.run_rtv ../test_data/config_hfr.yml" -dom ushi -res 6km

    parser.add_argument("-dom", help="the domain")
    parser.add_argument("-res", help="the resolution")

    # Process arguments
    stime = datetime.now(timezone.utc)
    args = parser.parse_args()
    try:
        main(args)
    except Exception as exp:
        _log.error(f"Error in main: {exp}")
    etime = datetime.now(timezone.utc)
    print('===========================================')
    print('===========================================')
    print(f" Execution time:: {(etime - stime)}")
    msg = '\n' + '='*80 + f"\nExecution time:: {(etime - stime)}\n" + "="*80
    _log.info(msg)
