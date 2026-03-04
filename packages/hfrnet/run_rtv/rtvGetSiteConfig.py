"""rtvGetSiteConfig"""

import numpy as np

from hfrnet.utils_funcs.lib_rtv import SiteInfo
from hfrnet.db_tools.db_tables import get_active_sitelist

import logging
_log = logging.getLogger()

def rtvGetSiteConfig(configObj, siteInfoObj, t):
    """
    % RTVGETSITECONFIG Obtains time-dependent site configurations
    %
    %    siteConfig = rtvGetSiteConfig( configObj, siteInfoObj,  time) obtains
    %    time-dependent HF-RADAR site configurations from the database for the
    %    domain, resolution, and time being processed.
    %
    %    Required configuration structure fields are:
    %
    %        domain
    %        resolution
    %        confdb
    %
    %    Sites obtained and their parameters are written to the site field in
    %    the configuration object.
    %
    %
    %    HF-Radar Network
    %    Scripps Institution of Oceanography
    %    Coastal Observing Research and Development Center
    """
    siteInfoObj = []
    results, nRows = get_active_sitelist(configObj, t)
    if nRows == 0:
        # No sites configured
        msg = f'Site configuration not found for {configObj.domain}, {configObj.resolution}'
        _log.warning(msg)

        return siteInfoObj

    if nRows > 0:
        # Verify we got a unique list of sites (i.e. no duplicate configs for a
        # given site)
        ids = results['id']
        _, idx = np.unique(ids, return_index=True)
        if len(ids) != len(idx):
            idx = np.setxor1d(idx, np.arange(len(ids)))
            list_tmp = ",".join([results['name'][i] for i in idx])
            errmsg = (f'Found {len(idx)} site(s) with overlapping configurations; '
                      f'{list_tmp}')
            _log.error(errmsg)

        for i in range(nRows):
            siteInfoObj.append(
                SiteInfo(results['network'][i], results['name'][i],
                           results['beampattern'][i], results['use_radial_minute'][i]))
            
            # Check minute range
            if siteInfoObj[i].useMinute > 59:
                errmsg = (f'{configObj.site.network[i]}:{configObj.site.name[i]}'
                          f' useMinute value of {configObj.site.useMinute[i]} '
                          f'is out of range. Valid range is [0-59]')
                _log.error(errmsg)

    return siteInfoObj
