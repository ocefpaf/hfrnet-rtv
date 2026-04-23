"""rtvComputeTotals"""

import logging
import numpy as np

from hfrnet.utils_funcs.lib_rtv import RtvTotals, UwlsTotalInfo

import hfrnet.run_rtv.uwlsTotal as uwlsTotal
from hfrnet.utils_funcs.math_funcs import inpolygon, scircle1


_log = logging.getLogger()


def rtvComputeTotals(compTotInput, radials, rtvInfoObj) -> RtvTotals:
    """
    Returns a structure containing total velocity solutions computed from 
    radial velocity measurements using input processing parameters.

    Inputs: 
    Configuration structure, radial data structure

    Output:
    U - total solution structure with fields:
        lat, lon, u, v, dopx, dopy, hdop, nRads, nSites, 
        grid: {resolution_km, projection, x_range, y_range, dx, dy, size, 
               ocean_indices}

    Specific configuration fields required by rtvComputetotals are:
    grid, domain, resolution, rtv('min_rad_sites'), rtv('grid_search_radius'), 
    rtv('min_radials'), rtv('max_rtv_speed'), rtv('uwls_max_hdop_mat')
 
    Small circles are used to narrow in on grid points were solutions are
    possible based on each site's origin and maximum radial data range and
    where the number of overlapping sites meet or exceed the
    rtv('min_rad_sites') value.

    Pre-computed small circles for each grid point corresponding to the
    rtv('grid_search_radius') value are then used to find radials that
    fall within the circle.  A total solution for a given gridpoint is
    computed if the radial data (1) contain data from a 'new' site, (2)
    have equal or greater than rtv('min_rad_sites') sites contributing,
    and (3) have equal to more more than rtv('min_radials') radials.

    Finally, solutions are filtered for complex and infinite values as
    well as for speed exceeding rtv('max_rtv_speed') HDOP value exceeding
    rtv('uwls_max_hdop_mat').

    """

    U_totals = RtvTotals()

    #reduce total grid solution space
    nArrayLen = len(compTotInput.grid.ocean_indices)
    gridAllRadCount = np.zeros(nArrayLen)
    nRads= np.zeros(nArrayLen)
    nRadSites= np.zeros(nArrayLen)
    gridNewRadIndex = np.zeros(nArrayLen, dtype=bool)
    nSites = len(radials)

    #loop over each radial dataset (site)
    for iRadial in range(nSites):

        currRadial = radials[iRadial]

        #Compute small circlebased on maximum range of data, adding grid search radius, using WGS85
        scLat, scLon = scircle1(currRadial.sitelatitude,
                                currRadial.sitelongitude,
                                (currRadial.maxrange +
                                 rtvInfoObj.grid_search_radius))

        #Find total grid points inside the small circle
        grid_ocean_x = compTotInput.grid.ocean_xy[0]
        grid_ocean_y = compTotInput.grid.ocean_xy[1]
        inPoints = np.zeros(len(grid_ocean_x))

        if len(grid_ocean_x) != len(grid_ocean_y):
            _log.error("ERROR: Don't have same amount of x and y vals")
            return U_totals

        inPoints = inpolygon(grid_ocean_x, grid_ocean_y, scLon, scLat)

        #Increment grid count for points inside radial coverage
        gridAllRadCount = gridAllRadCount + inPoints

        #Index grid points covered by new data
        if currRadial.isNew:
            gridNewRadIndex = np.logical_or(gridNewRadIndex, inPoints)

    #Define grid points with potential solutions based on new radial coverage
    #and number of sites overlapping the grid point
    sPoint = np.argwhere(np.logical_and(gridNewRadIndex,
                                        (gridAllRadCount >= rtvInfoObj.min_rad_sites)))

    if len(sPoint) == 0:
        _log.info( 'No potential total solution points found' )
        return U_totals

    #Define grid small circle field name
    scircle_xfield = ""
    scircle_yfield = ""
    if rtvInfoObj.grid_search_radius == np.floor(rtvInfoObj.grid_search_radius):
        scircle_xfield = f"ocean_x_scircle{rtvInfoObj.grid_search_radius:.0f}km"
        scircle_yfield = f"ocean_y_scircle{rtvInfoObj.grid_search_radius:.0f}km"

    elif rtvInfoObj.grid_search_radius*1000 == np.floor(rtvInfoObj.grid_search_radius*1000):
        scircle_xfield = f"ocean_x_scircle{rtvInfoObj.grid_search_radius*1000:.0f}m"
        scircle_yfield = f"ocean_y_scircle{rtvInfoObj.grid_search_radius*1000:.0f}m"

    else:
        msg = (f"Invalid grid search radius of {rtvInfoObj.grid_search_radius}"
                  "km. Value must be a whole number when represented in meters")
        _log.error(msg)
        raise ValueError(msg)

    # Compute total solutions
    uwlsTotalComp = [UwlsTotalInfo() for i in range (nArrayLen)]
    scircle_xfield_arr = getattr(compTotInput.grid, f"{scircle_xfield}")
    scircle_yfield_arr = getattr(compTotInput.grid, f"{scircle_yfield}")

    nPoints = len(sPoint)

    # Loop over each potential solution grid point
    for iPoint in range(nPoints):

        #index of the solution point
        solutionIndex = int(sPoint[iPoint])
        scLat = scircle_yfield_arr[:, solutionIndex]
        scLon = scircle_xfield_arr[:, solutionIndex]

        nSitesContributing = 0
        containsNewData = False
        rpSpeed = []
        rpHeading = []
        # Loop over each site to find radials within the grid point's search radius
        for iSite in range (nSites):

            currRadial = radials[iSite]
            inPolPoints = inpolygon(currRadial.longitude, currRadial.latitude, scLon, scLat)

            if np.any(inPolPoints):
                rpSpeed.append(currRadial.speed[inPolPoints])
                rpHeading.append(currRadial.heading[inPolPoints])
                nSitesContributing = nSitesContributing + 1

                if (not containsNewData) and (currRadial.isNew):
                    containsNewData = True

        if len(rpSpeed) > 0:
            rpSpeed = np.concatenate(rpSpeed)
            rpHeading = np.concatenate(rpHeading)
        
        # See if we have:
        #  (1) New radial data with
        #  (2) enough contributing sites and
        #  (3) enough radials to compute a total
        haveEnoughSitesContributing = nSitesContributing >= rtvInfoObj.min_rad_sites
        haveEnoughRadials = len(rpSpeed) >= rtvInfoObj.min_radials

        if containsNewData and haveEnoughSitesContributing and haveEnoughRadials:
            # Compute total
            uwlsTotalComp[solutionIndex] = uwlsTotal.uwlsTotal(rpSpeed, rpHeading)
            nRads[solutionIndex]  = len(rpSpeed)
            nRadSites[solutionIndex] = nSitesContributing

    
    u_temp = np.array([tot.u for tot in uwlsTotalComp])
    v_temp = np.array([tot.v for tot in uwlsTotalComp])
    dopx_temp = np.array([tot.dopx for tot in uwlsTotalComp])
    dopy_temp = np.array([tot.dopy for tot in uwlsTotalComp])
    hdop_temp = np.array([tot.hdop for tot in uwlsTotalComp])
    #Filter total solutions: infinite, complex, speed threshold, HDOP threshold
    iInf = np.logical_or(np.isinf(u_temp), np.isinf(v_temp))
    iCpx = np.logical_or(np.logical_or(u_temp.imag > 0, v_temp.imag > 0),
                         np.logical_or(dopx_temp.imag > 0, dopy_temp.imag > 0))
    iSpd = np.sqrt(u_temp**2 + v_temp**2) > rtvInfoObj.max_rtv_speed
    iHdop = hdop_temp > rtvInfoObj.uwls_max_hdop
    mask = np.logical_or(np.logical_or(iInf, iCpx), np.logical_or(iSpd, iHdop))

    #Mask the sites
    u_temp[mask] = np.nan
    v_temp[mask] = np.nan
    dopx_temp[mask] = np.nan
    dopy_temp[mask] = np.nan
    hdop_temp[mask] = np.nan
    nRads[mask] = 0
    nRadSites[mask] = 0

    if np.any(mask):
        msg = (f"Masked {np.sum( mask )} total solutions\n"
               f"{np.sum(iInf)} inf, {np.sum(iCpx)} complex, "
               f"{np.sum(iSpd)} speed, {np.sum(iHdop)} hdop")
        _log.info(msg)
    else:
        _log.debug('No solutions eliminated by masking')
        
    #Structure data
    if np.any(nRads) > 0:
        U_totals.lat = compTotInput.grid.ocean_xy[1, :]
        U_totals.lon = compTotInput.grid.ocean_xy[0, :]
        U_totals.u_xvel = u_temp
        U_totals.v_yvel = v_temp
        U_totals.dopx = dopx_temp
        U_totals.dopy = dopy_temp
        U_totals.hdop = hdop_temp
        U_totals.nRads = nRads
        U_totals.nSites = nRadSites
        U_totals.grid.resolution_km = compTotInput.grid.resolution_km
        U_totals.grid.projection = compTotInput.grid.projection
        U_totals.grid.x_range = compTotInput.grid.x_range
        U_totals.grid.y_range = compTotInput.grid.y_range
        U_totals.grid.dx = compTotInput.grid.dx
        U_totals.grid.dy = compTotInput.grid.dy
        U_totals.grid.size = compTotInput.grid.size
        U_totals.grid.ocean_indices = compTotInput.grid.ocean_indices
        U_totals.grid.ocean_xy = compTotInput.grid.ocean_xy

    return U_totals
