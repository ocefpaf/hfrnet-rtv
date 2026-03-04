#!/usr/bin/env python

"""lib of Classes needed for doing sum and avg"""

import numpy as np

from hfrnet.utils_funcs.lib_rtv import Grid, LandInfo, BaseObject

class SumAvgInfo(BaseObject):
    """
       Info after doing average calculation
    """
    def __init__(self):
        self.nGood = []
        self.uSum = []
        self.vSum = []
        self.u2sum = []
        self.v2sum = []
        self.uMin = []
        self.uMax = []
        self.vMin = []
        self.vMax = []
        self.uAvg = []
        self.vAvg = []
        self.uVar = []
        self.vVar = []
        self.lat = []
        self.lon = []
        #self.hdop = []
        self.grid = Grid()
        self.land = LandInfo([], [], 0)

    def to_dict(self):
        """return the dict for all attributes in the object"""
        d = super().to_dict()
        d['grid'] = d['grid'].to_dict()
        d.pop('land', None)
        return d

class StcInfo(BaseObject):
    """
       Stc info needed to do calculations properly
    """
    def __init__(self):
        self.max_age = np.float64(0)
        self.max_error = np.float64(0)
        self.min_temporal_coverage = np.float64(0)

class LtaInfo(BaseObject):
    """
       Lta info needed to do calculations properly
    """
    def __init__(self):
        self.min_month_temporal_coverage = np.float64(0)
        self.min_year_temporal_coverage = np.float64(0)
        self.max_error = np.float64(0)

class StcLtaInfo:
    """
       Needed to do calculations properly
    """
    def __init__(self):
        self.stcInfo = StcInfo()
        self.ltaInfo = LtaInfo()

    def to_dict(self):
        d = {'stcInfo': self.stcInfo.to_dict(),
             'ltaInfo': self.ltaInfo.to_dict()}
        return d

    def from_dict(self, **kwargs):
        if 'stcInfo' in kwargs:
            self.stcInfo.from_dict(**kwargs['stcInfo'])
        if 'ltaInfo' in kwargs:
            self.ltaInfo.from_dict(**kwargs['ltaInfo'])
