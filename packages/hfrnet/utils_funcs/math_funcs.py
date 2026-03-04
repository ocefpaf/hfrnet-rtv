"""Contains the math functions used for calculations"""


from decimal import Decimal
import math
from math import cos, sin, sqrt
from polycircles import polycircles
import shapely
from shapely.geometry.polygon import Polygon
from geographiclib.geodesic import Geodesic
import numpy as np

def azimuth(lat1, long1, lat2, long2):
    """get azimuth"""
    def _azimuth(lat1, long1, lat2, long2):
        brng = Geodesic.WGS84.Inverse(lat1, long1, lat2, long2)['azi1']
        return brng
    
    azi = np.vectorize(_azimuth)

    return azi(lat1, long1, lat2, long2)

def cart2pol(x, y):
    """cartesian to polar"""
    rho = np.sqrt(np.array(x)**2 + np.array(y)**2)
    phi = np.arctan2(y, x)
    return(phi, rho)

def pol2cart(rho, phi):
    """polar to cartesian"""
    x = rho * np.cos(phi)
    y = rho * np.sin(phi)
    return(x, y)

def scircle1(lat, lon, radius, num=99):
    """Number of vertices inside circle"""
    polycircle = polycircles.Polycircle(latitude=lat, longitude=lon,
                                        radius=radius*1e3,
                                        number_of_vertices=num)
    verticles = np.array(polycircle.vertices)
    return verticles[:, 0], verticles[:, 1]

def inpolygon(xq, yq, xv, yv):
    """number of points inside polygon"""
    #rst = []
    polygon = Polygon(list(zip(xv, yv)))
    if not polygon.is_valid:
        polygon = polygon.buffer(0)

    pts = shapely.points(xq, yq)
    return polygon.touches(pts) | polygon.contains(pts)

def km2deg(km, radius=6371):
    """km to degree"""
    degree = km*360/(np.pi*radius*2)
    return degree

def scxsc(p1, r1, p2, r2):
    # p1 = Coordinates of Point 1: latitude, longitude. This serves as the
    #      center of circle 1. Ex: (36.110174,  -90.953524)
    # r1 = Radius of circle 1 in meters
    # p2 = Coordinates of Point 2: latitude, longitude. This serves as the
    #      center of circle 1. Ex: (36.110174,  -90.953524)
    # r2 = Radius of circle 2 in meters
    '''
    1. Convert (lat, lon) to (x,y,z) geocentric coordinates.
    As usual, because we may choose units of measurement in which the earth
    has a unit radius
    '''
    x_p1 = Decimal(cos(math.radians(p1[1]))*cos(math.radians(p1[0])))  # x = cos(lon)*cos(lat)
    y_p1 = Decimal(sin(math.radians(p1[1]))*cos(math.radians(p1[0])))  # y = sin(lon)*cos(lat)
    z_p1 = Decimal(sin(math.radians(p1[0])))                           # z = sin(lat)
    x1 = (x_p1, y_p1, z_p1)

    x_p2 = Decimal(cos(math.radians(p2[1]))*cos(math.radians(p2[0])))  # x = cos(lon)*cos(lat)
    y_p2 = Decimal(sin(math.radians(p2[1]))*cos(math.radians(p2[0])))  # y = sin(lon)*cos(lat)
    z_p2 = Decimal(sin(math.radians(p2[0])))                           # z = sin(lat)
    x2 = (x_p2, y_p2, z_p2)
    '''
    2. Convert the radii r1 and r2 (which are measured along the sphere) to
       angles along the sphere.
       By definition, one nautical mile (NM) is 1/60 degree of arc (which is 
       pi/180 * 1/60 = 0.0002908888 radians).
    '''
    r1 = Decimal(math.radians(r1))
    r2 = Decimal(math.radians(r2))
    '''
    3. The geodesic circle of radius r1 around x1 is the intersection of the
       earth's surface with an Euclidean sphere of radius sin(r1) centered
       at cos(r1)*x1.

    4. The plane determined by the intersection of the sphere of radius sin(r1)
       around cos(r1)*x1 and the earth's surface is perpendicular to x1 and
       passes through the point cos(r1)x1, whence its equation is x.x1 = cos(r1)
       (the "." represents the usual dot product); likewise for the other plane.
       There will be a unique point x0 on the intersection of those two planes
       that is a linear combination of x1 and x2. Writing x0 = ax1 + b*x2 the
       two planar equations are;
       cos(r1) = x.x1 = (a*x1 + b*x2).x1 = a + b*(x2.x1)
       cos(r2) = x.x2 = (a*x1 + b*x2).x2 = a*(x1.x2) + b
       Using the fact that x2.x1 = x1.x2, which I shall write as q,
       the solution (if it exists) is given by
       a = (cos(r1) - cos(r2)*q) / (1 - q^2),
       b = (cos(r2) - cos(r1)*q) / (1 - q^2).
    '''
    q = Decimal(np.dot(x1, x2))

    if q**2 != 1 :
        a = (Decimal(cos(r1)) - Decimal(cos(r2))*q) / (1 - q**2)
        b = (Decimal(cos(r2)) - Decimal(cos(r1))*q) / (1 - q**2)
        '''
        5. Now all other points on the line of intersection of the two planes
           differ from x0 by some multiple of a vector n which is mutually
           perpendicular to both planes. The cross product  n = x1~Cross~x2
           does the job provided n is nonzero: once again, this means that x1
           and x2 are neither coincident nor diametrically opposite. (We need to
           take care to compute the cross product with high precision, because
           it involves subtractions with a lot of cancellation when x1 and x2
           are close to each other.)
        '''
        n = np.cross(x1, x2)
        '''
        6. Therefore, we seek up to two points of the form x0 + t*n which lie
           on the earth's surface: that is, their length
           equals 1. Equivalently, their squared length is 1:
           1 = squared length = (x0 + t*n).(x0 + t*n) = x0.x0 + 2t*x0.n + t^2*n.n = x0.x0 + t^2*n.n
        '''
        x0_1 = [a*f for f in x1]
        x0_2 = [b*f for f in x2]
        x0 = [sum(f) for f in zip(x0_1, x0_2)]
        '''
          The term with x0.n disappears because x0 (being a linear combination
          of x1 and x2) is perpendicular to n. The two solutions easily are
          t = sqrt((1 - x0.x0)/n.n)    and its negative. Once again high precision
          is called for, because when x1 and x2 are close, x0.x0 is very close
          to 1, leading to some loss of floating point precision.
        '''
        # This is to secure that (1 - np.dot(x0, x0)) / np.dot(n,n) > 0
        if (np.dot(x0, x0) <= 1) & (np.dot(n,n) != 0):
            t = Decimal(sqrt((1 - np.dot(x0, x0)) / np.dot(n,n)))
            t1 = t
            t2 = -t

            i1 = x0 + t1*n
            i2 = x0 + t2*n
            '''
            7. Finally, we may convert these solutions back to (lat, lon) by
               converting geocentric (x,y,z) to geographic coordinates. For the
               longitude, use the generalized arctangent returning values in
               the range -180 to 180 degrees (in computing applications, this
               function takes both x and y as arguments rather than just the
               ratio y/x; it is sometimes called "ATan2").
            '''

            i1_lat = math.degrees( math.asin(i1[2]))
            i1_lon = math.degrees( math.atan2(i1[1], i1[0] ) )
            ip1 = (i1_lat, i1_lon)

            i2_lat = math.degrees( math.asin(i2[2]))
            i2_lon = math.degrees( math.atan2(i2[1], i2[0] ) )
            ip2 = (i2_lat, i2_lon)
            return ip1, ip2
        if np.dot(n,n) == 0:
            #("The centers of the circles can be neither the same point nor antipodal points.")
            return None, None
        else:
            return None, None #("The circles do not intersect")
    else:
        #("The centers of the circles can be neither the same point nor antipodal points.")
        return None, None

'''
Example: The output of below is  [(36.989311051533505, -88.15142628069133),
                                  (38.2383796094578, -92.39048549120287)]
         intersection_points = intersection((37.673442, -90.234036), 
                                            107.5*1852, (36.109997, -90.953669),
                                            145*1852)
         print(intersection_points)
'''
def all_range(start, end, step):
    """get an array with range and step"""
    return np.arange(start, end + step/2.0, step)

def set_2darray_by_index(u, idx, v):
    """reshape 2d array"""
    sz = u.shape
    u = u.transpose().flatten()
    u[idx-1] = v
    u = u.reshape((sz[1], sz[0])).transpose()
    return u

def array_rotate_and_round(grid, var, mode='std'):
    """return array with grid indices rotated and rounded"""

    var_avg = np.full(grid.size, np.nan)
    var_avg = set_2darray_by_index(var_avg, grid.ocean_indices, var)
    var_avg = np.rot90(var_avg, -1)

    if mode in ('nGood','nRads'):
        #don't need to round these fields
        return var_avg

    if mode in ('dopx', 'dopy', 'hdop'):
        var_avg = np.round(var_avg*100) # Scale to store as short; accuracy to 100ths
    else:
        var_avg = np.round(var_avg) # 1 cm/s accuracy since hfr error ~3 - 20 cm/s

    return var_avg
