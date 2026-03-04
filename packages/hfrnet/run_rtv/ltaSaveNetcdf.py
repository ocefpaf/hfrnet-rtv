"""Saves LTA data to a NetCDF file"""

from datetime import datetime
import logging
import numpy as np
import netCDF4
from netCDF4 import Dataset
from hfrnet.utils_funcs.utility import (_dict, next_month_start,
                                        set_history, rtvNcid, current_datetime,
                                        get_timestamp_from_filename,
                                        wrap_text, resolution_spaced)
import hfrnet.utils_funcs.constsHFR as constsHFR
from hfrnet.utils_funcs.math_funcs import array_rotate_and_round, all_range

_log = logging.getLogger()

def ltaSaveNetcdf(metaDataObj, configObj, fileLocObj, stcLtaInfoObj, rtvProcessObj,
                  time, A_totObj, inputs):
    '''
    % Saves LTA data to a NetCDF file
    %
    %    ltaSaveNetCDF( metaDataObj, configObj, fileLocObj, stcLtaInfoObj, rtvProcessObj,
                        time, A_totObj )
    %    saves long-term average solutions and corresponding metadata in NetCDF format using
    %    the Climate and Foecast (CF) and Attribute Convention for Data
    %    Discovery (ACDD) metadata standards.
    %
    %    The specific conventions and versions are hard-coded in this function
    %    as it only supports one version for each convention and there is no
    %    intention to provide options or support for multiple conventions or
    %    versions.
    %
    %    The return values success and message will be true and empty,
    %    respectively, if there are no errors.  Otherwise, success will be
    %    false and any response will be provided in message.
    %
    %
    %    HF-Radar Network
    %    Scripps Institution of Oceanography
    %    Coastal Observing Research and Development Center

    % Developer Notes:
    %
    %    Update the NetCDF format version as needed (e.g. changes to the way
    %    data are encoded; types, new vars, new metadata, updates in metadata
    %    standards, ...). Use major.minor.maintenance as indicated below.
    %
    %    Note that grid needs to be oriented from NW in (1,1) to SE in (M,N)
    %    for proper orientation when written.  Worth noting if/when grids and
    %    land mask files are documented somewhere.
    %
    %    The deflation parameters are hard-coded in this function. They could
    %    be abstracted to the configuration, since there's likely every only
    %    going to be a single set of parameters, it's OK to define here - at
    %    least for now.
    '''

    ## Save
    try:
        writeNetCDF(metaDataObj, configObj, fileLocObj, stcLtaInfoObj,
                    rtvProcessObj, time, A_totObj, inputs)

    except Exception as e:
        message = f'Error saving {fileLocObj.output_ncfile}: \n {e}'
        raise RuntimeError(message) from e

    success = f"Saved {fileLocObj.output_ncfile}"
    _log.info(success)

def writeNetCDF(metaDataObj, configObj, fileLocObj, stcLtaInfoObj,
                rtvProcessObj, time, A_totObj, inputs):
    """ Formats LTA data and writes NetCDF file """

    A = A_totObj

    ## Define conventions & versions

    # Changes to the way data are encoded (types, new vars, new metadata, updates in metadata, ...)
    # should be reflected here
    nc = _dict()
    nc.formatVersion = '2.0.00' # major.minor.maintenance

    # Metadata conventions used
    nc.conventions = _dict()
    nc.conventions['CF'] = 'CF-1.12'
    nc.conventions['ACDD'] = 'ACDD-1.3'

    # CF Standard Name Version
    nc.cfStdNameVersion = 'CF Standard Name Table version 89'


    ## Define default deflation parameters
    nc.deflate = _dict()
    nc.deflate['enable'] = True
    nc.deflate['level'] = 2
    nc.deflate['shuffle'] = True

    ## Define subprocess specific parameters
    if rtvProcessObj.subprocess_name == constsHFR.CONFIGS_DICT['month']:
        min_temporal_coverage = np.int16(stcLtaInfoObj.ltaInfo.min_month_temporal_coverage)
        min_temporal_coverage_description = 'Minimum number of days required to compute monthly statistics'
        time_bnds = [datetime(year=time.year, month=time.month, day=1).timestamp(),
                     next_month_start(time).timestamp()]

    elif rtvProcessObj.subprocess_name == constsHFR.CONFIGS_DICT['year']:
        min_temporal_coverage = np.int16(stcLtaInfoObj.ltaInfo.min_year_temporal_coverage)
        min_temporal_coverage_description = 'Minimum number of days required to compute annual statistics'
        time_bnds = [datetime(year=time.year, month=1, day=1).timestamp(),
                     datetime(year=time.year+1, month=1, day=1).timestamp()]
    else:
        min_temporal_coverage = np.int16(0)
        time_bnds = np.int16(0)

    ## Format Variable Data
    # Need to reshape back to gridded matrices and rotate to convert from
    # column-major (MATLAB/Fortran) to row-major (C) order
    #
    # Also round to appropriate accuracy

    # make sure size/index is integer
    A.grid.size = A.grid.size.astype(int)
    A.grid.ocean_indices = A.grid.ocean_indices.astype(int)

    # u mean
    u_avg = array_rotate_and_round(A.grid, A.uAvg)

    # v mean
    v_avg = array_rotate_and_round(A.grid, A.vAvg)

    # u var
    u_var = array_rotate_and_round(A.grid, A.uVar)

    # v var
    v_var = array_rotate_and_round(A.grid, A.vVar)

    # u min
    u_min = array_rotate_and_round(A.grid, A.uMin)

    # v min
    v_min = array_rotate_and_round(A.grid, A.vMin)

    # u max
    u_max = array_rotate_and_round(A.grid, A.uMax)

    # v max
    v_max = array_rotate_and_round(A.grid, A.vMax)

    # n_obs
    n_obs = array_rotate_and_round(A.grid, A.nGood, 'nGood')

    # Replace NaN with fill values
    mask = np.isnan(u_avg)
    u_avg[mask] = netCDF4.default_fillvals['i2']
    v_avg[mask] = netCDF4.default_fillvals['i2']
    u_var[mask] = netCDF4.default_fillvals['i2']
    v_var[mask] = netCDF4.default_fillvals['i2']
    u_min[mask] = netCDF4.default_fillvals['i2']
    v_min[mask] = netCDF4.default_fillvals['i2']
    u_max[mask] = netCDF4.default_fillvals['i2']
    v_max[mask] = netCDF4.default_fillvals['i2']
    n_obs[mask] = netCDF4.default_fillvals['i2']

    ## History
    set_history(A, 'Writing values to file')

    ## Open NetCDF file
    # Keep the classic data model to increase compatibility since we
    # aren't using features specific to the NetCDF-4.0 model.
    ncid = Dataset(fileLocObj.output_ncfile, 'w', data_mode='NETCDF4_CLASSIC')

    ## Define Dimensions
    # Add in order of T, Z, Y, X for CF/COARDS compliance
    dimid_t = ncid.createDimension('time', None)
    dimid_lat = ncid.createDimension('lat', A.grid.size[0] )
    dimid_lon = ncid.createDimension('lon', A.grid.size[1] )
    dimid_nv = ncid.createDimension('nv', 2 ) #number of 'vertices' (nv) for bounds


    ## Define Coordinate Variables & Add Attributes
    # Add in the same order as the dimensions were written
    compression='zlib' if nc.deflate['enable'] else None
    complevel=nc.deflate['level']
    shuffle=nc.deflate['shuffle']
    fill_value = netCDF4.default_fillvals['i2']

    # For time coordinate variable, when using the standard or gregorian
    # calender, units should be in seconds and shifted forward beyond
    # 1582/10/15 to avoid Julian -> Gregorian crossover and potential
    # problems with the udunits package, if used.  Year length should be
    # exactly 365.2425 days long for the Gregorian/standard and proleptic
    # Gregorian calender.
    #
    # MATLAB's datenum uses the proleptic gregorian calender as defined
    # by the CF standard.  When using standard_name attribute for time
    # coordinate be sure to include the calender and units attributes.
    #
    # Use int for time data type because need 8 significant figures to
    # represent number of seconds in 1 year (31556952 seconds), float
    # isn't enough (7 sig. figures).  Would need to use double beyond
    # int.  Besides, don't need sub-second accuracy.  Unix time will
    # overflow int in 2038.  New epoch will be needed then to keep int
    # representation.  Unix time epoch is:
    #	1970-01-01 00:00:00Z = 0 seconds, 86,400 sec/day
    varid_t = ncid.createVariable('time', 'i4', dimid_t,
                                compression=compression,
                                complevel=complevel,
                                shuffle=shuffle)
    varid_t.standard_name = 'time'
    varid_t.units = 'seconds since 1970-01-01'
    varid_t.calendar = 'gregorian'
    varid_t.bounds = 'time_bnds'


    # A minimum of 4 significant figures to the right of the decimal
    # place is needed to keep resolution below 10's of meters.  Using
    # float data type for lat yields at least 5 significant digits to
    # the right of the decimal giving ~1/2m resolution in latitude.
    # Nine significant figures (at least 7 to the right of the
    # decimal) could be achieved using int data type but need to
    # introduce a scale factor.
    varid_lat = ncid.createVariable('lat', 'f4', dimid_lat,
                                    compression=compression,
                                    complevel=complevel,
                                    shuffle=shuffle)
    varid_lat.standard_name = 'latitude'
    varid_lat.units = 'degrees_north'


    # A minimum of 4 significant figures to the right of the decimal
    # place is needed to keep resolution below 10's of meters.  Using
    # float data type for lon yields at least 4 significant digits to
    # the right of the decimal giving ~1/2m resolution in longitude.
    # Nine significant figures (at least 6 to the right of the
    # decimal) could be achieved using int data type but need to
    # introduce a scale factor.
    varid_lon = ncid.createVariable('lon', 'f4', dimid_lon,
                                    compression=compression,
                                    complevel=complevel,
                                    shuffle=shuffle)
    varid_lon.standard_name = 'longitude'
    varid_lon.units = 'degrees_east'


    # Conventions (CF)
    ncid.Conventions = ','.join(nc.conventions.values())

    # ID (ACDD)
    ncid.id_HFR = rtvNcid(metaDataObj, configObj, rtvProcessObj, time)

    # UUID
    ncid.id = metaDataObj.uuid
    
    # Date Created (ACDD)
    ncid.date_created = current_datetime().strftime('%Y-%m-%dT%H:%M:%SZ')

    # Source (CF)
    ncid.source = ', '.join(inputs)

    # Program (ACDD)
    if hasattr(metaDataObj, 'program'):
        ncid.program = metaDataObj.program

    # Project (ACDD)
    if hasattr(metaDataObj, 'project'):
        ncid.project = metaDataObj.project

    # Title (CF, ACDD)
    ncid.title = metaDataObj.title

    # Summary (ACDD)
    ncid.summary = wrap_text(metaDataObj.summary)

    # Instrument (ACDD)
    ncid.instrument = wrap_text(metaDataObj.instrument)

    # Keywords (ACDD)
    ncid.keywords = wrap_text(metaDataObj.keywords)
        
    # Geospatial Bounds (ACDD)
    ncid.geospatial_lat_min = np.float32(A.grid.y_range[0])
    ncid.geospatial_lat_max = np.float32(A.grid.y_range[1])
    ncid.geospatial_lat_resolution = resolution_spaced(configObj.resolution)
    ncid.geospatial_lat_units = 'degrees_north'
    ncid.geospatial_lon_min = np.float32(A.grid.x_range[0])
    ncid.geospatial_lon_max = np.float32(A.grid.x_range[1])
    ncid.geospatial_lon_resolution = resolution_spaced(configObj.resolution)
    ncid.geospatial_lon_units = 'degrees_east'

    # Processing Level (ACDD)
    ncid.processing_level = wrap_text(metaDataObj.processing_level)

    ncid.history = metaDataObj.history

    # References (CF, ACDD)
    if hasattr(metaDataObj, 'references'):
        ncid.references = wrap_text(metaDataObj.references)

    # Institution (CF, ACDD)
    ncid.institution = metaDataObj.institution

    # Creator (ACDD)
    ncid.creator_type = metaDataObj.creator_type
    ncid.creator_name = metaDataObj.creator_name
    ncid.creator_email = metaDataObj.creator_email
    ncid.creator_url = metaDataObj.creator_url

    # Naming Authority (ACDD)
    ncid.naming_authority = metaDataObj.naming_authority

    # Vocabularies (ACDD)
    ncid.standard_name_vocabulary = nc.cfStdNameVersion
    ncid.keywords_vocabulary = metaDataObj.keywords_vocabulary
    ncid.instrument_vocabulary = metaDataObj.instrument_vocabulary

    # LTA Format Version ()
    ncid.format_version = nc.formatVersion

    # LTA Product Version (ACDD)
    ncid.product_version = configObj.product_version

    # time converage
    start, end = get_timestamp_from_filename(fileLocObj.output_ncfile.name)
    ncid.time_coverage_start = start
    ncid.time_coverage_end = end

    #
    ncid.cdm_data_type = metaDataObj.cdm_data_type
    ncid.day_night_data_flag = metaDataObj.day_night_data_flag
    ncid.metadata_link = metaDataObj.metadata_link
    ncid.platform = metaDataObj.platform
    ncid.platform_vocabulary = metaDataObj.platform_vocabulary
    ncid.production_environment = configObj.production_environment
    ncid.production_site = configObj.production_site
    ncid.project = metaDataObj.project
    ncid.publisher_email = metaDataObj.publisher_email
    ncid.publisher_type = metaDataObj.publisher_type
    ncid.publisher_name = metaDataObj.publisher_name
    ncid.publisher_url = metaDataObj.publisher_url

    ## Define Data Variables & Add Attributes

    # Time Bounds (cell boundaries)
    varid_time_bnds = ncid.createVariable('time_bnds', 'i4', reversed([dimid_nv, dimid_t]),
                                          compression=compression,
                                          complevel=complevel,
                                          shuffle=shuffle)

    # Depth (scalar coodinate vertical variable)
    varid_z = ncid.createVariable('depth', 'f4',
                                  compression=compression,
                                  complevel=complevel,
                                  shuffle=shuffle)
    varid_z.standard_name = 'depth'
    varid_z.units = 'm'
    varid_z.positive = 'down'
    varid_z.axis = 'Z'
    varid_z.bounds = 'depth_bnds'
    zComment = 'Nominal depth (and corresponding bounds) based on contributing radars'
    varid_z.comment = wrap_text(zComment)


    # Depth Bounds (cell boundaries)
    varid_z_bnds = ncid.createVariable('depth_bnds', 'f4', dimid_nv,
                                       compression=compression,
                                       complevel=complevel,
                                       shuffle=shuffle)

    # WGS84 Geoid
    varid_wgs84 = ncid.createVariable('wgs84', 'i1')
    varid_wgs84.grid_mapping_name = 'latitude_longitude'
    varid_wgs84.longitude_of_prime_meridian = np.float32(0.0)
    varid_wgs84.semi_major_axis = np.float32(6378137.0)
    varid_wgs84.inverse_flattening = np.float64(298.257223563)


    #.mean
    varid_u_avg = ncid.createVariable('u_mean', 'i2',
                                      reversed([dimid_lon, dimid_lat, dimid_t]),
                                      compression=compression,
                                      complevel=complevel,
                                      shuffle=shuffle,
                                      fill_value=fill_value)
    varid_u_avg.set_auto_scale(False)

    if configObj.domain == "glna":
        varid_u_avg.long_name = 'mean eastward surface velocity'
    else:
        varid_u_avg.standard_name = 'surface_eastward_sea_water_velocity'
        varid_u_avg.long_name = 'mean eastward surface velocity'
    # domain check - glna

    varid_u_avg.units = 'm s-1'
    varid_u_avg.scale_factor = np.float32(0.01)
    varid_u_avg.grid_mapping = 'wgs84'
    varid_u_avg.coordinates = 'depth'
    varid_u_avg.cell_methods = \
        'depth: mean time: mean (interval: 1 hour comment: 1 hour average)'
    varid_u_avg.ancillary_variables = 'n_obs'


    # v_mean
    varid_v_avg = ncid.createVariable('v_mean', 'i2', reversed([dimid_lon, dimid_lat, dimid_t]),
                                      compression=compression,
                                      complevel=complevel,
                                      shuffle=shuffle,
                                      fill_value=fill_value)
    varid_v_avg.set_auto_scale(False)

    if configObj.domain == "glna":
        varid_v_avg.long_name = 'mean northward surface velocity'
    else:
        varid_v_avg.standard_name = 'surface_northward_sea_water_velocity'
        varid_v_avg.long_name = 'mean northward surface velocity'
    # domain check - glna

    varid_v_avg.units = 'm s-1'
    varid_v_avg.scale_factor = np.float32(0.01)
    varid_v_avg.grid_mapping = 'wgs84'
    varid_v_avg.coordinates = 'depth'
    varid_v_avg.cell_methods = 'depth: mean time: mean (interval: 1 hour comment: 1 hour average)'
    varid_v_avg.ancillary_variables = 'n_obs'

    # u_var
    varid_u_var = ncid.createVariable('u_var', 'i2', reversed([dimid_lon, dimid_lat, dimid_t]),
                                      compression=compression,
                                      complevel=complevel,
                                      shuffle=shuffle,
                                      fill_value=fill_value)
    varid_u_var.set_auto_scale(False)

    varid_u_var.standard_name = 'surface_eastward_sea_water_velocity'
    varid_u_var.long_name = 'eastward surface velocity variance'
    varid_u_var.units = 'm2 s-2'
    varid_u_var.scale_factor = np.float32(0.0001)
    varid_u_var.grid_mapping = 'wgs84'
    varid_u_var.coordinates = 'depth'
    varid_u_var.cell_methods = ('depth: mean time: variance (interval: 1 hour '
                                'comment: 1 hour average)')
    varid_u_var.ancillary_variables = 'n_obs'


    # v_var
    varid_v_var = ncid.createVariable('v_var', 'i2',
                                      reversed([dimid_lon, dimid_lat, dimid_t]),
                                      compression=compression,
                                      complevel=complevel,
                                      shuffle=shuffle,
                                      fill_value=fill_value)
    varid_v_var.set_auto_scale(False)

    varid_v_var.standard_name = 'surface_northward_sea_water_velocity'
    varid_v_var.long_name = 'northward surface velocity variance'
    varid_v_var.units = 'm2 s-2'
    varid_v_var.scale_factor = np.float32(0.0001)
    varid_v_var.grid_mapping = 'wgs84'
    varid_v_var.coordinates = 'depth'
    varid_v_var.cell_methods = ('depth: mean time: variance (interval: 1 hour '
                                'comment: 1 hour average)')
    varid_v_var.ancillary_variables = 'n_obs'


    # u_min
    varid_u_min = ncid.createVariable('u_min', 'i2',
                                      reversed([dimid_lon, dimid_lat, dimid_t]),
                                      compression=compression,
                                      complevel=complevel,
                                      shuffle=shuffle,
                                      fill_value=fill_value)
    varid_u_min.set_auto_scale(False)

    if configObj.domain == "glna":
        varid_u_min.long_name = 'minimum eastward surface velocity'
    else:
        varid_u_min.standard_name = 'surface_eastward_sea_water_velocity'
        varid_u_min.long_name = 'minimum eastward surface velocity'
    # domain check - glna

    varid_u_min.units = 'm s-1'
    varid_u_min.scale_factor = np.float32(0.01)
    varid_u_min.grid_mapping = 'wgs84'
    varid_u_min.coordinates = 'depth'
    varid_u_min.cell_methods = \
        'depth: mean time: minimum (interval: 1 hour comment: 1 hour average)'
    varid_u_min.ancillary_variables = 'n_obs'


    # v_min
    varid_v_min = ncid.createVariable('v_min', 'i2', reversed([dimid_lon, dimid_lat, dimid_t]),
                                      compression=compression,
                                      complevel=complevel,
                                      shuffle=shuffle,
                                      fill_value=fill_value )
    varid_v_min.set_auto_scale(False)

    if configObj.domain == "glna":
        varid_v_min.long_name = 'minimum northward surface velocity'
    else:
        varid_v_min.standard_name = 'surface_northward_sea_water_velocity'
        varid_v_min.long_name = 'minimum northward surface velocity'
    # domain check - glna

    varid_v_min.units = 'm s-1'
    varid_v_min.scale_factor = np.float32(0.01)
    varid_v_min.grid_mapping = 'wgs84'
    varid_v_min.coordinates = 'depth'
    varid_v_min.cell_methods = ('depth: mean time: minimum (interval: 1 hour '
                                'comment: 1 hour average)')
    varid_v_min.ancillary_variables = 'n_obs'


    # u_max
    varid_u_max = ncid.createVariable('u_max', 'i2',
                                      reversed([dimid_lon, dimid_lat, dimid_t]),
                                      compression=compression,
                                      complevel=complevel,
                                      shuffle=shuffle,
                                      fill_value=fill_value)
    varid_u_max.set_auto_scale(False)

    if configObj.domain == "glna":
        varid_u_max.long_name = 'maximum eastward surface velocity'
    else:
        varid_u_max.standard_name = 'surface_eastward_sea_water_velocity'
        varid_u_max.long_name = 'maximum eastward surface velocity'
    # domain check - glna

    varid_u_max.units = 'm s-1'
    varid_u_max.scale_factor = np.float32(0.01)
    varid_u_max.grid_mapping = 'wgs84'
    varid_u_max.coordinates = 'depth'
    varid_u_max.cell_methods = \
        'depth: mean time: maximum (interval: 1 hour comment: 1 hour average)'
    varid_u_max.ancillary_variables = 'n_obs'


    # v_max
    varid_v_max = ncid.createVariable('v_max', 'i2', reversed([dimid_lon, dimid_lat, dimid_t]),
                                      compression=compression,
                                      complevel=complevel,
                                      shuffle=shuffle)
    varid_v_max.set_auto_scale(False)

    if configObj.domain == "glna":
        varid_v_max.long_name = 'maximum northward surface velocity'
    else:
        varid_v_max.standard_name = 'surface_northward_sea_water_velocity'
        varid_v_max.long_name = 'maximum northward surface velocity'
    # domain check - glna

    varid_v_max.units = 'm s-1'
    varid_v_max.scale_factor = np.float32(0.01)
    varid_v_max.grid_mapping = 'wgs84'
    varid_v_max.coordinates = 'depth'
    varid_v_max.cell_methods = \
        'depth: mean time: maximum (interval: 1 hour comment: 1 hour average)'
    varid_v_max.ancillary_variables = 'n_obs'


    # n_obs
    varid_n_obs = ncid.createVariable('n_obs', 'i2', reversed([dimid_lon, dimid_lat, dimid_t]),
                                      compression=compression,
                                      complevel=complevel,
                                      shuffle=shuffle)
    varid_n_obs.standard_name = 'number_of_observations'
    varid_n_obs.units = 'count'
    varid_n_obs.grid_mapping = 'wgs84'
    varid_n_obs.coordinates = 'depth'
    varid_n_obs.cell_methods = 'time: sum (interval: 1 hour)'


    # LTA Processing parameter 'variable'
    varid_pp = ncid.createVariable('processing_parameters', 'i1')

    varid_pp.long_name = \
        'Methods and parameters used to compute average current'

    varid_pp.combine_method_name = rtvProcessObj.methoddesc
    varid_pp.combine_method_description = \
        'Method used to compute hourly total solutions from radial velocities'

    varid_pp.min_temporal_coverage = min_temporal_coverage
    varid_pp.min_temporal_coverage_description = min_temporal_coverage_description

    if rtvProcessObj.method == 'uwls':
        varid_pp.max_hdop = np.float32(stcLtaInfoObj.stcInfo.max_error)
        varid_pp.max_hdop_description = 'Maximum allowed hourly vector HDOP'

    else:
        msg = ('max_error metadata description is undefined for processing '
               f"method:  {rtvProcessObj.method}")
        _log.error(msg)

    ## Add Data Values
    varid_lat[:] = all_range(A.grid.y_range[0], A.grid.y_range[1], A.grid.dy)
    varid_lon[:] = all_range(A.grid.x_range[0], A.grid.x_range[1], A.grid.dx)
    varid_t[0] = time.timestamp()
    varid_time_bnds[:] = np.array(time_bnds).reshape(1, 2)
    varid_z[:] = metaDataObj.depth_mean
    varid_z_bnds[:] = [0, metaDataObj.depth_bottom]
    varid_u_avg[:] = u_avg.reshape((u_avg.shape[0], u_avg.shape[1], -1)).transpose()
    varid_v_avg[:] = v_avg.reshape((v_avg.shape[0], v_avg.shape[1], -1)).transpose()
    varid_u_var[:] = u_var.reshape((u_var.shape[0], u_var.shape[1], -1)).transpose()
    varid_v_var[:] = v_var.reshape((v_var.shape[0], v_var.shape[1], -1)).transpose()
    varid_u_min[:] = u_min.reshape((u_min.shape[0], u_min.shape[1], -1)).transpose()
    varid_v_min[:] = v_min.reshape((v_min.shape[0], v_min.shape[1], -1)).transpose()
    varid_u_max[:] = u_max.reshape((u_max.shape[0], u_max.shape[1], -1)).transpose()
    varid_v_max[:] = v_max.reshape((v_max.shape[0], v_max.shape[1], -1)).transpose()
    varid_n_obs[:] = n_obs.reshape((n_obs.shape[0], n_obs.shape[1], -1)).transpose()


    ## Close file
    ncid.close()
