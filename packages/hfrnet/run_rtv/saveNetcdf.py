"""saveNetcdf"""

"""saveNetcdf"""

from collections.abc import Mapping
import datetime
import json
import copy
import logging
import numpy as np
from netCDF4 import Dataset

_log = logging.getLogger()

def datetime_to_timestamp(d, k):
    """convert the datetime to timestamp to be saved in netcdf file"""

    if k in d:
        if isinstance(d[k], list):
            d[k] = [t.timestamp() for t in d[k]]
        else:
            d[k] = d[k].timestamp()

def timestamp_to_datetime(d, k):
    """convert the timestamp to datetime"""
    if k in d:
        if isinstance(d[k], list):
            d[k] = [datetime.datetime.fromtimestamp(t) for t in d[k]]
        else:
            d[k] = datetime.datetime.fromtimestamp(d[k])

def saveNetcdf(filename, d):
    """save the dictionary d from rtv to netcdf file with filename"""

    nc = Dataset(filename, 'w', data_mode='NETCDF4_CLASSIC')
    compression = 'zlib'
    complevel = 2
    shuffle = True

    def _save_dict(group, data):
        dimensions = {}
        for k, v in data.items():
            if k == 'history':
                v = json.dumps(v)
            if isinstance(v, Mapping):
                subgroup = group.createGroup(k)
                _save_dict(subgroup, v)
            elif isinstance(v, (str, int, float, bool)):
                setattr(group, k, v)
            elif hasattr(v, "shape"):
                shape = v.shape
                dimid = []
                for s in shape:
                    if s not in dimensions:
                        dimensions[s] = group.createDimension(f'{s}', s)
                    dimid.append(dimensions[s])
                dimid = tuple(dimid)
                varid = group.createVariable(k, 'd', dimid,
                                  compression=compression,
                                  complevel=complevel,
                                  shuffle=shuffle)
                varid[:] = v
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    # save the list of dict
                    if isinstance(item, Mapping):
                        subgroup = group.createGroup(f"{k}_{i}_")
                        _save_dict(subgroup, item)
                        # additional attributes to recovry the list
                        subgroup.origin_key = k
                        subgroup.list_size = len(v)
                        subgroup.list_index = i

    # pre-process the input dict
    for k in ['t', 'tc']:
        datetime_to_timestamp(d, k)
    if 'c' in d:
        d['c'] = copy.deepcopy(d['c'])
        ncid = d['c'].pop('ncid', None)
        if 'reprocess' in d['c']:
            for k in ['times', 'tNewRtvFiles']:
                datetime_to_timestamp(d['c']['reprocess'], k)
        if 'lta' in d['c']:
            datetime_to_timestamp(d['c']['lta'], 'annual_min_date')
        if 'runTime' in d['c']['configObj']:
            datetime_to_timestamp(d['c']['configObj'], 'runTime')
        if 'rtvInfoObj' in d['c']:
            for k in ['new_state', 'current_state']:
                if d['c']['rtvInfoObj'][k] is not None:
                    datetime_to_timestamp(d['c']['rtvInfoObj'], k)
        d['c'] = json.dumps(d['c'])
    if 'r' in d:
        for iRad in d['r']:
            datetime_to_timestamp(iRad, 'time')

    # same the dict to netcdf file
    _save_dict(nc, d)

    # post process the dict to undo the change
    for k in ['t', 'tc']:
        timestamp_to_datetime(d, k)
    if 'c' in d:
        d['c'] = json.loads(d['c'])
        if ncid is not None:
            d['c']['ncid'] = ncid

        if 'reprocess' in d['c']:
            for k in ['times', 'tNewRtvFiles']:
                timestamp_to_datetime(d['c']['reprocess'], k)
        if 'lta' in d['c']:
            timestamp_to_datetime(d['c']['lta'], 'annual_min_date')
        if 'runTime' in d['c']['configObj']:
            timestamp_to_datetime(d['c']['configObj'], 'runTime')
        if 'rtvInfoObj' in d['c']:
            for k in ['new_state', 'current_state']:
                if d['c']['rtvInfoObj'][k] is not None:
                    timestamp_to_datetime(d['c']['rtvInfoObj'], k)
    if 'r' in d:
        for iRad in d['r']:
            timestamp_to_datetime(iRad, 'time')

    msg = f"Saved file: {filename}"
    _log.info(msg)

    nc.close()


def loadNetcdf(filename):
    """load the netcdf file into a dict"""

    ncid = Dataset(filename)
    data = {}

    def _load_dict(group):
        data = {}
        for att in group.ncattrs():
            v = group.getncattr(att)
            if att in ['list_index', 'list_size', 'origin_key']:
                # ignore the additional attributes to recovry the list
                continue
            if att == 'history':
                data[att] = json.loads(v)
            else:
                data[att] = v
        for k, v in group.variables.items():
            data[k] = v[:].filled(fill_value=np.nan)
        for k, g in group.groups.items():
            v = _load_dict(g)
            if 'origin_key' in g.ncattrs():
                k = g.getncattr('origin_key')
                if k not in data:
                    size = g.getncattr('list_size')
                    data[k] = [None]*size
                idx = g.getncattr('list_index')
                data[k][idx] = v
            else:
                data[k] = v

        return data


    data = _load_dict(ncid)
    for k in ['t', 'tc']:
        timestamp_to_datetime(data, k)
    if 'c' in data:
        data['c'] = json.loads(data['c'])
        if 'reprocess' in data['c']:
            for k in ['times', 'tNewRtvFiles']:
                timestamp_to_datetime(data['c']['reprocess'], k)
        if 'lta' in data['c']:
            timestamp_to_datetime(data['c']['lta'], 'annual_min_date')
        if 'rtvInfoObj' in data['c']:
            for k in ['new_state', 'current_state']:
                if data['c']['rtvInfoObj'][k] is not None:
                    timestamp_to_datetime(data['c']['rtvInfoObj'], k)

    if 'r' in data:
        for iRad in data['r']:
            timestamp_to_datetime(iRad, 'time')

    ncid.close()

    msg = f"Loaded file: {filename}"
    _log.info(msg)

    return data


