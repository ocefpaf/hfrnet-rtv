"""rtvSaveNetcdf"""

from datetime import timedelta
import logging
import numpy as np
import netCDF4
from netCDF4 import Dataset
from hfrnet.utils_funcs.utility import (_dict, set_history, rtvNcid,
                                        current_datetime, get_timestamp_from_filename,
                                        wrap_text, resolution_spaced)
from hfrnet.utils_funcs.math_funcs import array_rotate_and_round, all_range

_log = logging.getLogger()


def rtvSaveNetcdf(metaDataObj, configObj, fileLocObj, rtvInfoObj, rtvProcessObj,
                  time, U_tot, radials):
    '''
    % RTVSAVENETCDF Saves RTV data to a NetCDF file
    %
    %    rtvSaveNetCDF(metaDataObj, configObj, fileLocObj, rtvInfoObj, rtvProcessObj,
                       time, U_tot, radials)
    %    saves total solutions and corresponding metadata in NetCDF format using the
    %    Climate and Forecast (CF) and Attribute Convention for Data Discovery
    %    (ACDD) metadata standards.
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
    %    See also PRODUCTVERSION, NETCDF
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

    # Save
    try:
        writeNetCDF(fileLocObj, configObj, metaDataObj, rtvInfoObj,
                    rtvProcessObj, time, U_tot, radials)

    except Exception as e:
        message = f'Error saving {fileLocObj.output_ncfile}: {str(e)}'
        _log.error(message)
        raise RuntimeError(message) from e

    success = f"Saved file: {fileLocObj.output_ncfile}"
    _log.info(success)

def writeNetCDF(fileLocObj, configObj, metaDataObj, rtvInfoObj, rtvProcessObj,
                time, U, r):
    """Formats RTV data and writes NetCDF file"""

    # Define conventions & versions

    # Changes to the way data are encoded (types, new vars, new metadata, updates in metadata, ...)
    # should be reflected here
    nc = _dict()
    nc.formatVersion = '2.0.00' # major.minor.maintenance

    # Metadata conventions used
    nc.conventions = _dict()
    nc.conventions['CF'] = 'CF-1.12'
    nc.conventions['ACDD'] = 'ACDD-1.3'

    # CF Standard Name Version
    nc.cfStdNameVersion = 'CF Standard Name Table, Version 89'

    # Define default deflation parameters
    nc.deflate = _dict()
    nc.deflate['enable'] = True
    nc.deflate['level'] = 2
    nc.deflate['shuffle'] = True

    # Format Variable Data
    # Need to reshape back to gridded matrices and rotate to convert from
    # column-major (MATLAB/Fortran) to row-major (C) order
    #
    # Also round to appropriate accuracy

    # make sure size/index is integer
    U.grid.size = U.grid.size.astype(int)
    U.grid.ocean_indices = U.grid.ocean_indices.astype(int)

    # u
    u = array_rotate_and_round(U.grid, U.u_xvel)

    # v
    v = array_rotate_and_round(U.grid, U.v_yvel)

    # dopx
    dopx = array_rotate_and_round(U.grid, U.dopx, 'dopx')

    # dopy
    dopy = array_rotate_and_round(U.grid, U.dopy, 'dopy')

    # hdop
    hdop = array_rotate_and_round(U.grid, U.hdop, 'hdop')

    # n_sites
    n_sites = array_rotate_and_round(U.grid, U.nSites, 'nGood')

    # n_rads
    n_rads = array_rotate_and_round(U.grid, U.nRads, 'nRads')

    # Filter all data by HDOP
    mask = hdop >= (rtvInfoObj.uwls_max_hdop_nc * 100)
    if np.any(mask):
        u[mask] = np.nan
        v[mask] = np.nan
        dopx[mask] = np.nan
        dopy[mask] = np.nan
        hdop[mask] = np.nan
        n_sites[mask] = np.nan
        n_rads[mask] = np.nan
        msg = (f"Removed {np.sum(mask)} solutions exceeding HDOP threshold of "
               f"{rtvInfoObj.uwls_max_hdop_nc:.2f}")
        set_history(U, msg)
    
    nSol_points = np.sum(~np.isnan(u))
    _log.info(f" Number of solution points in u = {nSol_points}")
    # Replace NaN with fill values
    mask = np.isnan(u)
    u[mask] = netCDF4.default_fillvals['i2']
    v[mask] = netCDF4.default_fillvals['i2']
    dopx[mask] = netCDF4.default_fillvals['i2']
    dopy[mask] = netCDF4.default_fillvals['i2']
    hdop[mask] = netCDF4.default_fillvals['i2']
    n_sites[mask] = netCDF4.default_fillvals['i1']
    n_rads[mask] = netCDF4.default_fillvals['i2']
    
    # Open NetCDF file
    # Keep the classic data model to increase compatibility since we
    # aren't using features specific to the NetCDF-4.0 model.
    ncid = Dataset(fileLocObj.output_ncfile, 'w', data_mode='NETCDF4_CLASSIC')

    # Define Dimensions
    # Add in order of T, Z, Y, X for CF/COARDS compliance
    dimid_t = ncid.createDimension('time', None)
    dimid_lat = ncid.createDimension('lat', U.grid.size[0])
    dimid_lon = ncid.createDimension('lon', U.grid.size[1])
    dimid_nv = ncid.createDimension('nv', 2) #number of 'vertices' (nv) for bounds


    # Define Coordinate Variables & Add Attributes
    # Add in the same order as the dimensions were written
    compression='zlib' if nc.deflate['enable'] else None
    complevel=nc.deflate['level']
    shuffle=nc.deflate['shuffle']
    fill = netCDF4.default_fillvals['i2']

    # For time coordinate variable, when using the standard or gregorian
    # calender, units should be in seconds and shifted forward beyond
    # 1582/10/15 to avoid Julian -> Gregorian crossover and potential
    # problems with the udunits package, if used.  Year length should be
    # exactly 365.2425 days long for the Gregorian/standard and proleptic
    # Gregorian calender.
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
                                    shuffle=shuffle )
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
    list_source = [f"{rr.file}" for rr in r]
    ncid.source = ', '.join(list_source)

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
    ncid.geospatial_lat_min = np.float32(U.grid.y_range[0])
    ncid.geospatial_lat_max = np.float32(U.grid.y_range[1])
    ncid.geospatial_lat_resolution = resolution_spaced(configObj.resolution)
    ncid.geospatial_lat_units = 'degrees_north'
    ncid.geospatial_lon_min = np.float32(U.grid.x_range[0])
    ncid.geospatial_lon_max = np.float32(U.grid.x_range[1])
    ncid.geospatial_lon_resolution = resolution_spaced(configObj.resolution)
    ncid.geospatial_lon_units = 'degrees_east'

    # Processing Level (ACDD)
    ncid.processing_level = wrap_text(metaDataObj.processing_level)

    # History (CF, ACDD)
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

    # RTV Format Version ()
    ncid.format_version = nc.formatVersion

    # RTV Product Version (ACDD)
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
    varid_time_bnds = ncid.createVariable('time_bnds', 'i4',
                                          reversed([dimid_nv, dimid_t]),
                                          compression=compression,
                                          complevel=complevel,
                                          shuffle=shuffle)

    # Depth (scalar coodinate vertical variable)
    varid_z = ncid.createVariable('depth', 'f4', (),
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


    # u
    # reverse the dimension to match matlab
    varid_u = ncid.createVariable('u', 'i2',
                                  reversed([dimid_lon, dimid_lat, dimid_t]),
                                  compression=compression,
                                  complevel=complevel,
                                  shuffle=shuffle,
                                  fill_value=fill)
    varid_u.set_auto_scale(False)

    if configObj.domain == "glna":
        varid_u.long_name = 'surface eastward water velocity'
    else:
        varid_u.standard_name = 'surface_eastward_sea_water_velocity'

    varid_u.units = 'm s-1'
    varid_u.scale_factor = np.float32(0.01)
    varid_u.grid_mapping = 'wgs84'
    varid_u.coordinates = 'depth'
    varid_u.cell_methods = 'depth: mean time: mean'
    varid_u.ancillary_variables = 'dopx'

    # v
    varid_v = ncid.createVariable('v', 'i2',
                                  reversed([dimid_lon, dimid_lat, dimid_t]),
                                  compression=compression,
                                  complevel=complevel,
                                  shuffle=shuffle,
                                  fill_value=fill)
    varid_v.set_auto_scale(False)
    if configObj.domain == "glna":
        varid_v.long_name = 'surface northward water velocity'
    else:
        varid_v.standard_name = 'surface_northward_sea_water_velocity'

    varid_v.units = 'm s-1'
    varid_v.scale_factor = np.float32(0.01)
    varid_v.grid_mapping = 'wgs84'
    varid_v.coordinates = 'depth'
    varid_v.cell_methods = 'depth: mean time: mean'
    varid_v.ancillary_variables = 'dopy'

    # dopx
    dopxComment = ('The longitudinal dilution of precision (dopx) represents the contribution of '
        'radial geometry to uncertainty in the eastward velocity estimate (u).')
    varid_dopx = ncid.createVariable('dopx', 'i2',
                                     reversed([dimid_lon, dimid_lat, dimid_t]),
                                     compression=compression,
                                     complevel=complevel,
                                     shuffle=shuffle,
                                     fill_value=fill)
    varid_dopx.set_auto_scale(False)

    varid_dopx.long_name = 'longitudinal dilution of precision'
    varid_dopx.comment = wrap_text(dopxComment)
    varid_dopx.scale_factor = np.float32(0.01)
    varid_dopx.grid_mapping = 'wgs84'
    varid_dopx.coordinates = 'depth'

    # dopy
    dopyComment = ('The latitudinal dilution of precision (dopy) represents the contribution of '
        'radial geometry to uncertainty in the northward velocity estimate (v).')
    varid_dopy = ncid.createVariable('dopy', 'i2',
                                     reversed([dimid_lon, dimid_lat, dimid_t]),
                                     compression=compression,
                                     complevel=complevel,
                                     shuffle=shuffle,
                                     fill_value=fill)
    varid_dopy.set_auto_scale(False)

    varid_dopy.long_name = 'latitudinal dilution of precision'
    varid_dopy.comment = wrap_text(dopyComment)
    varid_dopy.scale_factor = np.float32(0.01)
    varid_dopy.grid_mapping = 'wgs84'
    varid_dopy.coordinates = 'depth'


    # hdop
    hdopComment = ('The horizontal dilution of precision (hdop) is the vector length (magnitude) '
        'of the eastward (dopx) and northward (dopy) dilution of precision.  It represents the '
        'contribution of radial geometry to the overall uncertainty in the total velocity '
        '(u and v) estimate.')
    varid_hdop = ncid.createVariable('hdop', 'i2',
                                     reversed([dimid_lon, dimid_lat, dimid_t]),
                                     compression=compression,
                                     complevel=complevel,
                                     shuffle=shuffle,
                                     fill_value=fill )
    varid_hdop.set_auto_scale(False)

    varid_hdop.long_name = 'horizontal dilution of precision'
    varid_hdop.comment = wrap_text(hdopComment)
    varid_hdop.scale_factor = np.float32(0.01)
    varid_hdop.grid_mapping = 'wgs84'
    varid_hdop.coordinates = 'depth'
    varid_hdop.ancillary_variables = 'dopx dopy'


    # Number of Contributing Sites
    nSitesComment = 'Number of radars contributing radials to the total solution'
    varid_nsites = ncid.createVariable('number_of_sites', 'i1',
                                       reversed([dimid_lon, dimid_lat, dimid_t]),
                                       compression=compression,
                                       complevel=complevel,
                                       shuffle=shuffle,
                                       fill_value=netCDF4.default_fillvals['i1'])
    varid_nsites.long_name = 'number of contributing radars'
    varid_nsites.units = 'count'
    varid_nsites.comment = wrap_text(nSitesComment)
    varid_nsites.grid_mapping = 'wgs84'
    varid_nsites.coordinates = 'depth'

    # Number of Contributing Radials
    nRadsComment = 'Number of radials contributing to the total solution'
    varid_nrads = ncid.createVariable('number_of_radials', 'i2',
                                      reversed([dimid_lon, dimid_lat, dimid_t]),
                                      compression=compression,
                                      complevel=complevel,
                                      shuffle=shuffle,
                                      fill_value=fill)

    varid_nrads.long_name = 'number of contributing radials'
    varid_nrads.units = 'count'
    varid_nrads.comment = wrap_text(nRadsComment)
    varid_nrads.grid_mapping = 'wgs84'
    varid_nrads.coordinates = 'depth'

    # RTV Processing parameter 'variable'
    varid_pp = ncid.createVariable('processing_parameters', 'i1' )

    varid_pp.long_name = 'Methods and parameters used to compute total solutions'

    varid_pp.combine_method_name = rtvProcessObj.methoddesc
    varid_pp.combine_method_description = ('Method used to compute total '
                                           'solutions from radial velocities')

    varid_pp.grid_search_radius = np.float32(rtvInfoObj.grid_search_radius)
    varid_pp.grid_search_radius_units = 'km'
    varid_pp.grid_search_radius_description = ('Search radius used for finding '
                                               'contributing radial velocities')

    varid_pp.max_radial_speed = np.int32(rtvInfoObj.max_rad_speed)
    varid_pp.max_radial_speed_units = 'cm s-1'
    varid_pp.max_radial_speed_description = \
        'Maximum radial speed allowed to contribute to total solutions'

    varid_pp.max_rtv_speed = np.int32(rtvInfoObj.max_rtv_speed)
    varid_pp.max_rtv_speed_units =  'cm s-1'
    varid_pp.max_rtv_speed_description = 'Maximum allowed total speed'

    varid_pp.min_radar_sites = np.int16(rtvInfoObj.min_rad_sites)
    varid_pp.min_radar_sites_description = \
        'Minimum number of radar sites required to make a total solution'

    varid_pp.min_radials = np.int16(rtvInfoObj.min_radials)
    varid_pp.min_radials_description = \
        'Minimum number of radials required to make a solution'

    varid_pp.max_hdop = np.float32(rtvInfoObj.uwls_max_hdop_nc)
    varid_pp.max_hdop_description = 'Maximum allowed HDOP'

    # Radial Metadata 'variable'
    varid_rm = ncid.createVariable('radial_metadata', 'i1')

    varid_rm.long_name = \
        'Metadata on radial velocities used to compute total solutions'

    varid_rm.number_files_loaded = np.int16(len(r))
    varid_rm.number_files_loaded_description = 'Number of radial files loaded'

    list_loaded = [f"{rr.file}" for rr in r]
    varid_rm.files_loaded = ', '.join(list_loaded)
    varid_rm.files_loaded_description = 'Radial file names loaded'

    # ======================================
    # prod mon variable Number of solution points
    varid_prodmon = ncid.createVariable('prod_mon', 'u4')
    varid_prodmon.assignValue(int(nSol_points))
    varid_prodmon.long_name = 'Total (actual) number of retrievals'
    # ======================================
    
    ## Add Data Values
    varid_lat[:] = all_range(U.grid.y_range[0], U.grid.y_range[1], U.grid.dy )
    varid_lon[:] = all_range(U.grid.x_range[0], U.grid.x_range[1], U.grid.dx )
    varid_t[0] = time.timestamp()
    varid_time_bnds[:] =  np.array([(time - timedelta(minutes=30)).timestamp(),
                                    (time + timedelta(minutes=30)).
                                    timestamp()]).reshape(1, 2) # 1 hr
    varid_z[:] = metaDataObj.depth_mean
    varid_z_bnds[:] = [0, metaDataObj.depth_bottom]
    varid_u[:] = u.reshape((u.shape[0], u.shape[1], -1)).transpose()
    varid_v[:] = v.reshape((v.shape[0], v.shape[1], -1)).transpose()
    varid_dopx[:] = dopx.reshape((dopx.shape[0], dopx.shape[1], -1)).transpose()
    varid_dopy[:] = dopy.reshape((dopy.shape[0], dopy.shape[1], -1)).transpose()
    varid_hdop[:] = hdop.reshape((hdop.shape[0], hdop.shape[1], -1)).transpose()
    varid_nsites[:] = n_sites.reshape((n_sites.shape[0], n_sites.shape[1], -1)).transpose()
    varid_nrads[:] = n_rads.reshape((n_rads.shape[0], n_rads.shape[1], -1)).transpose()

    ## Close file
    ncid.close()
