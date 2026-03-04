"""uwlsTotal"""

import numpy as np
from hfrnet.utils_funcs.lib_rtv import UwlsTotalInfo

def uwlsTotal(rSpeed, rHeading) -> UwlsTotalInfo:
    """
    input of two vectors:
    rSpeed   - Column vector (n* x 1) of radial velocity magnitude
    rHeading - Column vector (n* x 1) of radial velocity heading 
               in degres counterclockwise from +x (east)
    n* >= 2
    """

    retValUwlsTotal = UwlsTotalInfo()
    
    #copying the calculation
    X = np.zeros((np.size(rHeading), 2))
    X[:, 0] = np.cos(np.deg2rad(rHeading))
    X[:, 1] = np.sin(np.deg2rad(rHeading))

    X_transpose_X = np.matmul(np.transpose(X), X)
    det_transpose = np.linalg.det(X_transpose_X)
    
    #can't do inverse
    if abs(det_transpose) < 1e-5:
        return retValUwlsTotal
    
    C = np.linalg.inv(X_transpose_X)

    retValUwlsTotal.dopx = np.sqrt(C.item(0,0))
    retValUwlsTotal.dopy = np.sqrt(C.item(1,1))
    retValUwlsTotal.hdop = np.sqrt(C.item(0,0) + C.item(1,1))

    b = np.linalg.multi_dot([C, np.transpose(X), rSpeed])

    retValUwlsTotal.u = b[0]
    retValUwlsTotal.v = b[1]

    return retValUwlsTotal
