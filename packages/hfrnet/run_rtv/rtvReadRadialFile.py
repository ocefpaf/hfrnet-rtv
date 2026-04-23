"""rtvReadRadialFile"""

import re
import logging
import numpy as np
from hfrnet.utils_funcs.lib_rtv import RadialInfo
from hfrnet.utils_funcs.math_funcs import azimuth, cart2pol
import hfrnet.utils_funcs.constsHFR as constsHFR

_log = logging.getLogger()

def rtvReadRadialFile(inFile):
    """
    % RTVREADRADIALFILE Read lluv radial file to structure
    %
    %    radialObj = rtvReadRadialFile( inFile ) reads the radial file defined in the
    %    structure and returns a structure containing radial data used during RTV
    %    processing. The radial file format must be lluv.  The radar location is
    %    used to compute speed and heading fields from radial velocity if they
    %    aren't directly available in the file.
    %
    %    Input used:
    %        inFile.fullfile - radial file name (including the full path if not on
    %                     the MATLAB path)
    %        inFile.lat      - radar latitude (deg N)
    %        inFile.lon      - radar longitude (deg E)
    %
    %    Output:
    %        r - Structure of radial velocity data including the fields:
    %
    %            latitude
    %            longitude
    %            speed
    %            heading
    %            range (if available)
    %            vflag (if available)
    %
    %    The heading is returned in polar convention (counterclockwise from the
    %    +x axis).  The range and vflag fields are only returned if they're
    %    available in the file.
    %
    %    See also RTVLOADRADIALS
    %
    %    HF-Radar Network
    %    Scripps Institution of Oceanography
    %    Coastal Observing Research and Development Center
    """

    # Check file exists
    if not (inFile.fullfile).is_file():
        msg = f'File {inFile.fullfile} not found'
        _log.error(msg)

    # Get LLUV Table Column Names
    # if could not open the file , still initialize columnIndex 
    columnIndex = {}
    try:
        with open(inFile.fullfile, 'r') as fid:
            tableType = ''
            columnIndex = {}
            for tline in fid:
                # Look for column names if the current table is the right type
                if tableType == 'LLUV':
                    m = re.match(r'^%TableColumnTypes:((\s*\w+\s*)+)', tline)

                    # Table column name match; save & break
                    if m:
                        m = m.groups()[0].strip().split()
                        for I in range(len(m)):
                            columnIndex[m[I]] = I

                        break
                else:
                # Keep looking for the LLUV table if we haven't found it yet
                    m = re.match(r'^%TableType:\s*LLUV', tline)
                    if m:
                        tableType = 'LLUV'

    except Exception as e:
        msg = f'Could not open file: {str(e)}'
        _log.error(msg)

    # Check we got required column names
    if len(columnIndex) == 0:
        _log.error('noColumnName: No column names were found')
    elif 'LOND' not in columnIndex:
        _log.error('missingColumnName: Longitude column (LOND) not found')
    elif 'LATD' not in columnIndex:
        _log.error('missingColumnName: Latitude column (LATD) not found')
    elif 'HEAD' not in columnIndex:
        _log.warning('missingColumnName: '
                     'Radial heading column (HEAD) not found')
    elif 'VELO' not in columnIndex:
        _log.warning('missingColumnName: Radial velocity'
                     ' column (VELO) not found')
    elif 'RNGE' not in columnIndex:
        _log.warning('missingColumnName: Radial range '
                     'column (RNGE) not found')


    # Load data
    radialInfoObj = RadialInfo()
    d = np.loadtxt(inFile.fullfile, comments="%")

    if d.size == 0:
        _log.error('noDataLoaded: '
                   'Load function returned an empty array. No data in radial file?')

    else:
        # Radial location
        radialInfoObj.latitude = d[:, columnIndex['LATD']]
        radialInfoObj.longitude = d[:, columnIndex['LOND']]

        # Radial heading (toward origin)
        if 'HEAD' in columnIndex:

            # Convert deg CW from N to deg CCW from E
            radialInfoObj.heading = ((constsHFR.RIGHT_ANGLE - d[:, columnIndex['HEAD']]) %
                                     constsHFR.NUM_DEGREES)

        else:

            # Compute bearing from each radial to the origin
            az = azimuth(radialInfoObj.latitude, radialInfoObj.longitude,
                         inFile.lat, inFile.lon)

            # Convert deg CW from N to deg CCW from E
            radialInfoObj.heading = (constsHFR.RIGHT_ANGLE - az) % constsHFR.NUM_DEGREES

        # Radial speed
        if "VELO" in columnIndex:
            radialInfoObj.speed = d[:, columnIndex['VELO']]

        elif 'VELU'  in columnIndex and 'VELV' in columnIndex:

            # Convert radial vector to polar coords (speed and bearing)
            rdir, rspd = cart2pol(d[:, columnIndex['VELU']], d[:, columnIndex['VELV']])

            # Convert rad to deg
            rdir = np.rad2deg(rdir)

            # Find difference in bearing (binary result, either 0 or 180)
            dd = round(np.abs(radialInfoObj.heading - rdir)) % constsHFR.NUM_DEGREES

            # 180 deg differences imply direction away from radar which gets a
            # negative value by convention
            mask = dd > 10 # allow for some error observed in small velocities
            rspd[mask] = -rspd[mask]
            radialInfoObj.speed = rspd

        else:
            _log.error('missingColumnName: Radial velocity components (VELU & VELV) not found')

        # Radial range (from origin)
        if 'RNGE' in columnIndex:
            radialInfoObj.range = d[:, columnIndex['RNGE']]

        # Radial flags
        if 'VFLG' in columnIndex:
            radialInfoObj.vflag = d[:, columnIndex['VFLG']]

    return radialInfoObj
