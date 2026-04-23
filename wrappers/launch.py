"""
Program name:        launch.py
History:
                     10/30/2024 Tianzhu Qiao
Description:         This script launches a Docker container that will execute
                     a python command, which will in turn generate
                     hfrnet output.
Input:               config.yaml file containing required paths
                     to scripts, source code, and test data.
Files needed:        Requires the configuration file, with the correct paths.
Output:              After a successful execution of the container, output
                     data will be available in the output directory,
                     and logs will be available in the logs directory.
                     Please read the README document for more information.
Modules/subroutines: t4_utils.future.ccap.docker
                     t4_utils.future.ccap.parse_config
Calling sequence:    python wrapper/launch.py wrapper/config/config.yaml
"""

from subprocess import CalledProcessError
import subprocess
import argparse

from t4_utils.future.ccap.docker import make_cmd
from t4_utils.future.ccap.parse_config import parse_config
from t4_utils.future.deco.stats import stats


# @stats
def run(cmd):
    return subprocess.run(cmd, check=True)


def main(config_path, interactive, dryrun):
    print(f"config_path::{config_path}")
    config = parse_config(config_path)
    cmd = make_cmd(config, interactive)
    print('Running the following command:')
    print(' '.join(cmd))
    if not dryrun:
        try:
            # If run() is called with the stats decorator then proc will be None
            # This will be fixed in future revisions of t4_utils but should not
            # affect production as the @stats decorator should NOT be used
            # outside of development environments.
            proc = run(cmd)
        except CalledProcessError as err:
            print("Some error occurred during processing. See below for more")
            print(err)
            return -1
        else:
            print(f'Process done, return code {proc.returncode}')

    return 0

def parse_cl_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("config",
                        help="Full path to the CCAP config yaml")
    parser.add_argument("-i", "--interactive", action="store_true",
                        default=False, help="Open interactive container")
    parser.add_argument("-d", "--dry-run", action="store_true",
                        default=False, dest="dryrun")
    args = parser.parse_args()
    return args.config, args.interactive, args.dryrun


if __name__ == "__main__":
    main(*parse_cl_args())
