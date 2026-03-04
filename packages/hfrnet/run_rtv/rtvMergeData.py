"""rtvMergeData"""

import logging
import numpy as np

_log = logging.getLogger()

from hfrnet.utils_funcs.utility import read_total_file, set_history
from hfrnet.utils_funcs.lib_rtv import RadialInfo

def rtvMergeData(fileLocObj, configObj, radials, U_tot):
    """
    % RTVMERGETOTALS Merges current data with previous run(s)
    %
    %    [radials, U_tot] = rtvMergeData(fileLocObj, configObj, radials, U_tot )
    %    merges radial and total data
    %    from the current run with previous runs and appends to the history.
    %    When reprocessing, an error is thrown if previous runs are found since
    %    it is expected that they have already been removed.
    %
    %
    %    HF-Radar Network
    %    Scripps Institution of Oceanography
    %    Coastal Observing Research and Development Center
    """

    # Check for data file from previous run(s)
    last = None
    if fileLocObj.input_file is None:
        _log.warning('fileLocObj.input_file is None')
        return radials, U_tot
        
    if fileLocObj.input_file.is_file():

        if configObj.reprocess:
            # Warning if we're reprocessing
            msg = (f'Total file {fileLocObj.input_file} exists. Should '
                   'have been removed to ensure consistent results.')
            _log.warning(msg)

        else:
            # Load existing data
            try:
                last = read_total_file(fileLocObj.input_file)
                msg = f'Loaded prior solutions from {fileLocObj.input_file}'
                _log.debug(msg)

            except Exception as e:
                msg = (f'Failed to load prior data from {fileLocObj.input_file}:'
                       f' {str(e)} \n'
                       'Plan to overwrite existing file, data from previous '
                       'run(s) will be lost')
                _log.warning(msg)

    else:
        msg = f'{fileLocObj.input_file} not found, no prior solutions'
        _log.debug(msg)


    # If no prior data, start history and return
    nNew = np.count_nonzero(np.isfinite(U_tot.u_xvel))

    if not last:
        set_history(U_tot, f'Saving {nNew} new solutions')
        _log.debug('Started history')
        return radials, U_tot

    # Merge current run with prior data
    # Loop over radial datasets from previous run(s)
    for I in range(len(last['r'])):

        # and look for matching datasets in the current run.
        r_network = np.array([rr.network for rr in radials])
        r_site = np.array([rr.site for rr in radials])
        r_patterntype = np.array([rr.patterntype for rr in radials])

        siteMatch = (r_network == last['r'][I]['network']) & \
            (r_site == last['r'][I]['site']) & (r_patterntype == last['r'][I]['patterntype'])
        
        # Append the radial dataset to the current run if it hasn't already been loaded
        if not np.any(siteMatch):
            
            fields = list(last['r'][I].keys())
            newRadial = RadialInfo()
            
            for field in fields:
                setattr(newRadial, field, last['r'][I][field])
            
            radials.append(newRadial)

            msg = (f'Merged radial dataset from {last["r"][I]["network"]}'
                   f'{last["r"][I]["site"]} {last["r"][I]["patterntype"]}')
            _log.debug(msg)

    # Find previous solutions that aren't being updated by new solutions
    osi = np.isnan(U_tot.u_xvel) & np.isfinite(last['U']['u_xvel'])

    if np.any(osi):
        
        # Keep previous solutions that aren't being updated by this run
        U_tot.u_xvel[osi] = last['U']['u_xvel'][osi]
        U_tot.v_yvel[osi] = last['U']['v_yvel'][osi]
        U_tot.dopx[osi] = last['U']['dopx'][osi]
        U_tot.dopy[osi] = last['U']['dopy'][osi]
        U_tot.hdop[osi] = last['U']['hdop'][osi]
        U_tot.nRads[osi] = last['U']['nRads'][osi]
        U_tot.nSites[osi] = last['U']['nSites'][osi]

    # Append to history
    if 'history' in last['U']:
        U_tot.history = last['U']['history']

    msg =  (f'Saving {np.count_nonzero(np.isfinite(U_tot.u_xvel))} solutions; '
            f'{nNew} new or updated, {np.count_nonzero(osi)} unmodified from '
            'previous run(s)')
    set_history(U_tot, msg)

    msg = f'Updated history: {U_tot.history[-1]["message"]}'
    _log.info(msg)

    return radials, U_tot
