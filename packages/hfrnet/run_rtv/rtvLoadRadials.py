"""rtvLoadRadials"""

#import re
import logging
from pathlib import Path

import numpy as np

from hfrnet.utils_funcs.lib_rtv import RadialInfo
from hfrnet.run_rtv.rtvReadRadialFile import rtvReadRadialFile

from hfrnet.utils_funcs.utility import (_dict, read_total_file, prev_radial_data,
                                        copy_file_from_s3)
from hfrnet.utils_funcs.math_funcs import  km2deg, scircle1, inpolygon, scxsc
from hfrnet.db_tools.db_tables import get_files_list_radialtable

_log = logging.getLogger()

def _update_key(d):
    """Rename result columns and convert to structure"""
    m = {'t': 't', 'net': 'network', 'sta': 'site', 'patterntype': 'beampattern',
         'file_arrival_time': 'arrivaltime', 'lat': 'lat', 'lon': 'lon', 
         'range_res': 'rangeres', 'range_bin_end': 'rangeend', 
         'manufacturer': 'manufacturer', 'dfile': 'file', 'dir': 'dir'}
    return _dict((m.get(key, key), value) for (key, value) in d.items())

def rtvLoadRadials(configObj, siteInfoObj, fileLocObj, rtvInfoObj, landInfoObj, calcTime):
    """
    % RTVLOADRADIALS Loads radial data for RTV processing
    %
    %    radials = rtvLoadRadials( configObj, siteInfoObj, fileLocObj, rtvInfoObj, 
    %                              landInfoObj, calcTime )
    %    returns a structure containing
    %    radial data from all sites for the given hour of RTV processing.
    %    Data are provided for the preferred beam pattern and filtered by
    %    velocity flag (if available), speed threshold, and landmasked.
    %
    %    Only data from 'new' sites that have potential overlap with
    %    neighboring sites are returned. Overlap is determined by using small
    %    circles at each site's origin with radius computed from the site's
    %    range resolution and last range cell. With the exception of reprocessing,
    %    'new' sites are defined as sites whose file arrival time are greater than
    %    or equal to the current rtv state time.
    %
    %    Reprocessing, indicated by the existance of the 'reprocess' field in
    %    configObj bypasses radial selection by arrival time such that all available
    %    radial files for the given timestamp are obtained and all are
    %    considered 'new'.
    %
    %    Previous total solutions for the same domain, resolution, and time are
    %    checked to ensure radial selection parameters are consistent.  During
    %    reprocessing, this function errors out as it is expected that any
    %    previous data has already been removed.  During near real-time
    %    processing, site selection parameters are modified based on previous
    %    runs to ensure consistency.
    %
    %    Inputs:
    %
    %        (configObj, siteInfoObj, fileLocObj, rtvInfoObj, landInfoObj) - Structures 
    %                    containing configuration parameters
    %        calcTime      - Datetime (scalar)
    %
    %    Outputs:
    %
    %     radials - Radial data structure with fields:
    %            isnew
    %            network
    %            site
    %            sitelatitude
    %            sitelongitude
    %            patterntype
    %            manufacturer
    %            file
    %            dir
    %            latitude
    %            longitude
    %            speed
    %            heading
    %            maxrange
    %
    %    Specific configuration fields required by rtvLoadRadials are:
    %
    %        domain
    %        grid_search_radius
    %        max_rad_speed
    %        new_state
    %        site
    %        raddb
    %        land
    %
    %    and, during reprocessing, the following fields are also required:
    %        reprocess
    %
    %
    %    HF-Radar Network
    %    Scripps Institution of Oceanography
    %    Coastal Observing Research and Development Center
    """

    # Initialize return values
    radials = [] # isempty returns true
    nSite = len(siteInfoObj)

    # Ensure radial selection consistent with previous run(s)
    # Check if a file already exists
    last = None
    if fileLocObj.input_file is not None:

        if fileLocObj.input_file.is_file():

            # Load previous radial dataset
            try:
                last = read_total_file(fileLocObj.input_file)
                msg = f'Loaded radial structure from prior run ({fileLocObj.input_file})'
                _log.info(msg)

            except Exception as e:
                errmsg = (f'Failed to load radial structure from prior run ('
                        f'{fileLocObj.input_file}): {str(e)}')
                _log.warning(errmsg)
                _log.warning('Cannot ensure consistent radial selection if results are '
                            'combined with previous run(s)')

    else:
        errmsg = f'{fileLocObj.input_file} not found, no pre-existing radial data'
        _log.debug(errmsg)
        
    # Modify radial selection as needed based on previous run(s)
    if last is not None:
        nMod = 0

        last_network, last_site, last_patterntype, last_time = prev_radial_data(fileLocObj.input_file,
                                                                                last)

        for iSiteInfo in siteInfoObj:
            _log.info(f" -- Processing site:: {iSiteInfo.network} :: {iSiteInfo.name}")

            # Look for a site/network match in existing radial data
            siteMatch = ((iSiteInfo.network == last_network) &
                         (iSiteInfo.name == last_site))

            if not np.any(siteMatch):
                continue

            # Error out if there is more than one matched record
            if np.count_nonzero(siteMatch) > 1:

                errmsg = (f'Found two records of radial data from {iSiteInfo.network}:'
                          f'{iSiteInfo.name} in previous radial data structure '
                          f'loaded from {fileLocObj.input_file}')
                _log.error(errmsg)

            # Check that the patterntypes are consistent
            siteMatch = np.argwhere(siteMatch)[0][0]

            if iSiteInfo.beampattern != last_patterntype[siteMatch]:

                if 'i' == last_patterntype[siteMatch]:
                    iSiteInfo.beampattern = 'ideal'

                elif 'm' == last_patterntype[siteMatch]:
                    iSiteInfo.beampattern = 'measured'

                else:
                    errmsg = (f'Unknown beam pattern type {last_patterntype[siteMatch]}'
                              f' found for {iSiteInfo.network}:{iSiteInfo.name}'
                              ' in previous radial data structure loaded from '
                              f'{fileLocObj.input_file}')
                    _log.error(errmsg)

                errmsg = (f"Modified {iSiteInfo.network }:{iSiteInfo.name} "
                          f"selection to use {iSiteInfo.beampattern} radials for "
                          f"consistency with previous run(s)")
                _log.info(errmsg)

                nMod = nMod + 1

            # Python can't handle reading the Matlab Datetime
            # Matlab useMinute is set to 0, hasn't affected the results
            last_data_minute = last_time[siteMatch].minute
            if iSiteInfo.useMinute != last_data_minute:

                iSiteInfo.useMinute = int(last_data_minute)

                errmsg = (f'Modified {iSiteInfo.network}:{iSiteInfo.name} '
                          f'selection to use radials from {iSiteInfo.useMinute} '
                          f'minute(s) for consistency with previous run(s)')
                _log.info(errmsg)

                nMod = nMod + 1

        # Logging
        if nMod > 0:
            msg = (f'{nMod} modifications made to radial site parameters based'
                   ' on previous runs')
            _log.info(msg)

        else:
            _log.debug('No modification needed to current radial config based on '
                       'previous runs')

    # Build radial query
    file_list_temp = []
    results, nfiles = get_files_list_radialtable(configObj, calcTime, siteInfoObj)

    # Note: t +/- 30 min. is a query optimization
    if results:
        file_list_temp = results

    # Log & remove any records that have NULL where data should be required
    rmRecordIndex = np.zeros(nfiles, dtype=bool)

    for I in range(nfiles):

        file_list_temp[I] = _update_key(file_list_temp[I])
        Radialfile_record = file_list_temp[I]
        _log.info(f" -- Processing file:: {file_list_temp[I].file}")

        if (Radialfile_record.file == "" or Radialfile_record.dir == "" or
            np.isnan(Radialfile_record.lat) or np.isnan(Radialfile_record.lon) or
            (not configObj.reprocess and (Radialfile_record.arrivaltime == ""))):
            rmRecordIndex[I] = True
            errmsg = (f'Radialfiles record {Radialfile_record.network}:'
                      f'{Radialfile_record.site} {Radialfile_record.beampattern} '
                      f'{Radialfile_record.t} is missing required fields, removing from processing')
            _log.warning(errmsg)

    if np.any(rmRecordIndex):
        for I in range(nSite-1, -1, -1):
            if rmRecordIndex[I]:
                del file_list_temp[I]

    nq = len(file_list_temp)
    newRadialIndex = None
    # Index new radials
    if configObj.reprocess:
        newRadialIndex = np.ones(nq, dtype=bool)

    else:
        newRadialIndex = np.zeros(nq, dtype=bool)

        for I in range(nq):

            if file_list_temp[I].arrivaltime >= rtvInfoObj.current_state:

                newRadialIndex[I] = True
                errmsg = (f'New radial from {file_list_temp[I].network}:{file_list_temp[I].site} '
                          f'({file_list_temp[I].beampattern}) arrived at '
                          f'{file_list_temp[I].arrivaltime}')
                _log.debug(errmsg)

            else:
                errmsg = (f'Obtained radial from {file_list_temp[I].network}:'
                          f'{file_list_temp[I].site} ({file_list_temp[I].beampattern})')
                _log.debug(errmsg)

    nNewRadials = np.count_nonzero(newRadialIndex)
    if nNewRadials:

        if configObj.reprocess:
            errmsg = f'{nNewRadials} radial(s) to be reprocessed'
            _log.info(errmsg)

        else:
            errmsg = f'{nNewRadials} new radial(s) to be processed'
            _log.info(errmsg)
    else:
        return radials

    # Find sites that potentially overlap with new data
    loadRadialIndex = np.zeros(nq, dtype=bool)

    # Define small circle radius buffer amount
    #
    # The small circle radius is typically extended beyond the maximum range
    # by ~3% of the range resolution to account for small differences observed
    # between small circle estimates of data range and actual radial locations.
    buf = 0.05

    # Pre-compute small circles
    sc = [_dict({'lat': [], 'lon':[]})]*len(newRadialIndex)
    for I in range(len(newRadialIndex)):

        # Site range
        #   If range resolution or end metadata are either NaN (NULL) or less than zero,
        #   assume metadata is bad or unavailable and fall back to a max range value
        if (file_list_temp[I].rangeend is None or file_list_temp[I].rangeres is None or
            file_list_temp[I].rangeend <= 0 or file_list_temp[I].rangeres <= 0):

            file_list_temp[I].siterange = 300 + rtvInfoObj.grid_search_radius

            errmsg = (f'Missing radial range resolution or end from {file_list_temp[I].network}:'
                      f'{file_list_temp[I].site}, setting siterange to '
                      f'{file_list_temp[I].siterange } km')
            _log.warning(errmsg)
        else:
            file_list_temp[I].siterange = (file_list_temp[I].rangeres * file_list_temp[I].rangeend +
                                           buf * file_list_temp[I].rangeres +
                                           rtvInfoObj.grid_search_radius)

        # Small circle using WGS84, adding grid search radius and fraction of
        # range resolution
        sc[I].lat, sc[I].lon = scircle1(file_list_temp[I].lat, file_list_temp[I].lon,
                                        file_list_temp[I].siterange)


    # Iterate over each new site
    for I in range(len(newRadialIndex)):

        if not newRadialIndex[I]:
            continue

        # Iterate over every other site
        for J in range(len(newRadialIndex)):

            # Skip self
            if I == J:
                continue

            # Skip sites that have already been selected for loading
            if loadRadialIndex[J]:
                continue

            # Check if this site's origin is inside the new site's domain
            is_in = inpolygon([file_list_temp[J].lon], [file_list_temp[J].lat],
                              sc[I].lon, sc[I].lat)
            if is_in[0]:
                loadRadialIndex[I] = True
                loadRadialIndex[J] = True
                continue

            # Check if the new site's origin is inside this site's domain
            is_in = inpolygon([file_list_temp[I].lon], [file_list_temp[I].lat],
                              sc[J].lon, sc[J].lat)
            if is_in[0]:
                loadRadialIndex[I] = True
                loadRadialIndex[J] = True
                continue

            # Look for intersection of sites
            ip1, ip2 = scxsc((file_list_temp[I].lat, file_list_temp[I].lon),
                             km2deg(file_list_temp[I].siterange),
                             (file_list_temp[J].lat, file_list_temp[J].lon),
                             km2deg(file_list_temp[J].siterange))

            if ip1 is None:
                # No intersection
                continue

            if ip1 == ip2:
                # Tangential intersection
                continue

            # Site pair intersection, plan to load
            loadRadialIndex[I] = True
            loadRadialIndex[J] = True

    # Log results
    for I in range(len(newRadialIndex)):
        if not newRadialIndex[I]:
            continue

        if not loadRadialIndex[I]:
            errmsg = (f'No overlap found with new data from {file_list_temp[I].network}'
                      f':{file_list_temp[I].site}')
            _log.info(errmsg)


    nLoadRadials = np.count_nonzero(loadRadialIndex)
    if nLoadRadials:
        errmsg = f'{nLoadRadials} radial files to be loaded for processing'
        _log.info(errmsg)
    else:
        _log.info('No potential data overlap with new radials')
        return radials


    #% Obtain data from sites
    nLand = len(landInfoObj)
    n = 0
    for I in range(len(loadRadialIndex)):
        if not loadRadialIndex[I]:
            continue

        n = n + 1
        ifile = file_list_temp[I]
        # ifile.fullfile = Path(f"{ifile.dir}/{ifile.file}")
        ifile.fullfile = Path(copy_file_from_s3(ifile.dir,ifile.file,fileLocObj.radial_local_dir))
        
        # raise ValueError("==================")   
        # if fileLocObj.radial_local_dir:
        #     ifile.fullfile = Path(f"{fileLocObj.radial_local_dir}",
        #                           f"{ifile.network}", f"{ifile.site}",
        #                           f"{ifile.t.strftime('%Y-%m')}",
        #                           f"{ifile.file}")
        # Load radial data
        d = None
        try:
            d = rtvReadRadialFile(ifile)
            msg = (f'Loaded {len(d.latitude)} radials from {ifile.file} '
                   f' ({n} of {nLoadRadials})')
            _log.info(msg)

        except Exception as e:
            errmsg = f': {str(e)}'
            _log.error(errmsg)

        if d is None:
            continue

        # VFLG filtering
        if hasattr(d, "vflag"):

            idx = d.vflag == 128
            nIdx = np.sum(idx)
            
            if nIdx > 0:

                d.latitude = d.latitude[~idx]
                d.longitude = d.longitude[~idx]
                d.speed = d.speed[~idx]
                d.heading = d.heading[~idx]

                if hasattr(d, "range"):
                    d.range = d.range[~idx]
                errmsg = f'Removed {nIdx} velocity flagged radials'
                _log.debug(errmsg)
                
                if not np.any(d.latitude):
                    errmsg = (f'No radial data left from {ifile.file}'
                              f' after velocity flag filtering')
                    _log.info(errmsg)
                    continue
            
            #d.pop('vflag', None)

        # Speed thresholding
        idx = abs(d.speed) > rtvInfoObj.max_rad_speed
        nIdx = np.sum(idx)
        
        if nIdx > 0:

            d.latitude = d.latitude[~idx]
            d.longitude = d.longitude[~idx]
            d.speed = d.speed[~idx]
            d.heading = d.heading[~idx]

            if hasattr(d, "range"):
                d.range = d.range[~idx]

            errmsg = (f'Removed {nIdx} radials with speed greater than '
                      f'{rtvInfoObj.max_rad_speed} cm/s')
            _log.debug(errmsg)

            if not np.any(d.latitude):
                errmsg = f'No radial data left from {ifile.file} after speed thresholding'
                _log.info(errmsg)
                continue


        # Landmasking
        #
        # Approximate data domain as a rectangle
        dLim = [np.max(d.latitude), np.min(d.latitude),
                np.max(d.longitude), np.min(d.longitude)]

        # Loop over each land polygon
        nOverLand = 0

        for J in range(nLand):

            # # If land and data rectangles overlap...
            #---- this is the new land
            if (dLim[0] >= landInfoObj[J]['region'][1] and
                dLim[1] <= landInfoObj[J]['region'][0] and
                dLim[2] >= landInfoObj[J]['region'][3] and
                dLim[3] <= landInfoObj[J]['region'][2]):  ##ok<AND2>

                # ... see if any radials fall inside the land polygon ...
                is_in = inpolygon(d.longitude, d.latitude,
                                  landInfoObj[J]['polygon'][:,0],
                                  landInfoObj[J]['polygon'][:,1])

                # ... and remove any data falling over land
                if np.any(is_in):
                    d.latitude = d.latitude[~is_in]
                    d.longitude = d.longitude[~is_in]
                    d.speed = d.speed[~is_in]
                    d.heading = d.heading[~is_in]

                    if hasattr(d, 'range'):
                        d.range = d.range[~is_in]

                    nOverLand = nOverLand + sum(is_in)

                    

        if nOverLand > 0:
            errmsg = f'Removed {nOverLand} radials falling over land'
            _log.debug(errmsg)

            if len(d.latitude) == 0:
                errmsg = f'No radial data left from {ifile.file} after land masking'
                _log.info(errmsg)
                continue



        # Save loaded data
        if not radials:
            ri = 0

        radials.append(RadialInfo())
        radials[ri].isNew = newRadialIndex[I]
        radials[ri].time = ifile.t
        radials[ri].network = ifile.network
        radials[ri].site = ifile.site
        radials[ri].sitelatitude = ifile.lat
        radials[ri].sitelongitude = ifile.lon
        radials[ri].patterntype = ifile.beampattern
        radials[ri].manufacturer = ifile.manufacturer
        radials[ri].file = ifile.file
        radials[ri].dir = ifile.dir
        radials[ri].latitude = d.latitude
        radials[ri].longitude = d.longitude
        radials[ri].speed = d.speed
        radials[ri].heading = d.heading

        # maxrange field
        if hasattr(d, "range"):
            if ifile.rangeres is None or ifile.rangeres <= 0:

                # Use 6km as range resolution if unavailable
                radials[ri].maxrange = np.max(d.range) + buf * 6
                errmsg = (f'Missing radial range resolution from {ifile.network}:'
                          f' {ifile.site}, using 6km range resolution to estimate maxrange')
                _log.warning(errmsg)

            else:

                # Use all available information
                radials[ri].maxrange = max(d.range) + buf * ifile.rangeres


        else:

            # Use 300km as overall max range when range isn't available
            radials[ri].maxrange = 300
            errmsg = (f'Missing radial range data from {ifile.file}'
                      ', setting maxrange to 300 km')
            _log.info(errmsg)


        ri = ri + 1

    return radials
