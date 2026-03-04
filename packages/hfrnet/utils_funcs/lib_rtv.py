#!/usr/bin/env python

"""lib for processing rtv"""

import numpy as np


class BaseObject:
    """the base object to provice some common functions"""
    def to_dict(self):
        """return the dict for all attributes in the object"""
        return dict(vars(self))

    def from_dict(self, **kwargs):
        """set the object attributes"""
        var = vars(self)
        for k, v in kwargs.items():
            if k in var:
                if isinstance(getattr(self, k), BaseObject):
                    getattr(self, k).from_dict(**v)
                else:
                    setattr(self, k, v)

class Grid(BaseObject):
    """
        The 'grid' class keeps info about the ocean velocities
    """
    def __init__(self):
        self.resolution_km = np.float64(0)
        self.projection = ""
        self.x_range = np.array([], dtype=np.float64)
        self.y_range = np.array([], dtype=np.float64)
        self.dx = np.float64(0)
        self.dy = np.float64(0)
        self.size = np.array([], dtype=np.float64)
        self.ocean_indices = np.array([], dtype=np.float64)
        self.ocean_xy = [[]]
        self.ocean_x_scircle = [[]]
        self.ocean_y_scircle = [[]]

class LandInfo:
    """
        Land information
    """
    def __init__(self, floatArray1, floatArray2, intVar):
        self.region = np.array(floatArray1)
        self.polygon = np.array(floatArray2)
        self.length = intVar


class RtvTotals(BaseObject):
    """
        Information needed for the radial totals
        All are arrays of variable length and grid of class Grid
    """
    def __init__(self):
        self.lat = np.array([], dtype=np.float64)
        self.lon = np.array([], dtype=np.float64)
        self.u_xvel = np.array([], dtype=np.float64)
        self.v_yvel = np.array([], dtype=np.float64)
        self.dopx = np.array([], dtype=np.float64)
        self.dopy = np.array([], dtype=np.float64)
        self.hdop = np.array([], dtype=np.float64)
        self.nRads = np.array([], dtype=np.float64)
        self.nRadSites = np.array([], dtype=np.float64)
        self.nSites = np.array([], dtype=np.float64)
        self.grid = Grid()
        self.land = LandInfo(self.lat, self.lon, 10)

    def to_dict(self):
        """return the dict for all attributes in the object"""
        d = super().to_dict()
        d['lat'] = np.array(d['lat'])
        d['lon'] = np.array(d['lon'])
        d['grid'] = d['grid'].to_dict()
        d.pop('land', None)
        return d

class DatabaseConfig:
    """
       The database configuration info
    """
    def __init__(self):
        self.user = ""
        self.host = ""
        self.port = ""
        self.password = ""
        self.ssl_ca = ""
        self.region = ""
        self.dbname = ""
        self.ssl_context = ""
        self.run_env = "rhw" # "aws" "ao" "rhw"
        # self.ssl_verify_identity = ""
        # self.ssl_verify_cert = ""
        # self.auth_plugin_map = ""
        #--- This is to use the correct parameteres when connection
        # to the DB server depends on the OS
        # if it's on a linux, set it to 'rhw'
        # if it's on the cloud 9, set it to 'aws'

#things from the configureRtv
class ConfigureVals(BaseObject):
    """
        The configuration values needed to run
    """
    def __init__(self, domain="USHI", resolution="6km"):
        self.domain = domain
        self.domain_description = ""
        self.resolution = resolution
        self.times = None
        #-- The DB object
        self.dbObject = DatabaseConfig()
        self.config_dbname=''
        self.radial_dbname=''
        # self.raddb = DatabaseConfig()
        self.reprocess = True
        # This will be the now time whenever the current time is needed
        # This will be set to the start time in the yml file
        self.runTime = None
        self.product_version = ''

        self.production_site = ''
        self.production_environment = ''
        self.output_s3_loc = ''
        self.output_intermed_s3_loc = ''

    def to_dict(self):
        """return the dict for all attributes in the object"""
        d = super().to_dict()
        for k in ['dbObject', 'times']:
            d.pop(k)
        return d

class FileLocations(BaseObject):
    """
        Keep track of all file locations
    """
    def __init__(self):
        self.landfile = ""
        self.gridfile = ""
        self.radial_local_dir = ""
        self.input_file = ""
        self.output_dir = ""
        self.output_ncfile = ""
        self.intermed_filename = ""
        self.intermed_filepath = ""
        self.interm_local_dir = ""

class RtvProcess(BaseObject):
    """
        The configuration of the process
    """
    def __init__(self, name="", method="", description="", save_as=""):
        self.name = name
        self.method = method
        self.methoddesc = description
        self.saveas = save_as
        self.reprocess = False
        self.subprocess = False
        self.subprocess_name = ""


class SiteInfo:
    """
       Info about the data collection site
    """
    def __init__(self, network="", name="", beampattern="", useMinute = 0):
        self.network = network
        self.name = name
        self.beampattern = beampattern
        self.useMinute = useMinute

class RtvInfo(BaseObject):
    """
       All the different variable parameters for RTV running
    """
    def __init__(self):
        self.grid_search_radius = np.float64(0)
        self.max_age = np.float64(0)
        self.max_rad_speed = np.float64(0)
        self.max_rtv_speed = np.float64(0)
        self.min_rad_sites = np.float64(0)
        self.min_radials = np.float64(0)
        self.uwls_max_hdop = np.float64(0)
        self.uwls_max_hdop_ascii = np.float64(0)
        self.uwls_max_hdop_nc = np.float64(0)
        self.new_state = None
        self.current_state = None

class UwlsTotalInfo:
    """
       Vector calculations info
    """
    def __init__(self):
        self.u = np.float64(np.nan)
        self.v = np.float64(np.nan)
        self.dopx = np.float64(np.nan)
        self.dopy = np.float64(np.nan)
        self.hdop = np.float64(np.nan)

class RadialInfo(BaseObject):
    """
       Radial velocity info needed for calculations
    """
    def __init__(self):
        self.time = ""
        self.site = ""
        self.network = ""
        self.patterntype = ""
        self.manufacturer = ""
        self.file = ""
        self.dir = ""
        self.sitelatitude = np.float64(0)
        self.sitelongitude = 9999.0
        self.maxrange = 9999.0
        self.isNew = False
        self.longitude = []
        self.latitude = []
        self.speed = []
        self.heading = []

class Metadata(BaseObject):
    """
       Metadata info
    """
    def __init__(self):
        self.creator_email = ""
        self.creator_name = ""
        self.creator_type = ""
        self.creator_url = ""
        self.depth_bottom = np.float64(0)
        self.depth_mean = np.float64(0)
        self.domain_description = ""
        self.institution = ""
        self.institution_acronym = ""
        self.instrument = ""
        self.instrument_vocabulary = ""
        self.keywords = ""
        self.keywords_vocabulary = ""
        self.naming_authority = ""
        self.processing_level = ""
        self.program = ""
        self.references = ""
        self.summary = ""
        self.title = ""
        self.cdm_data_type = "Grid"
        self.day_night_data_flag = "both"
        self.metadata_link = "https://cdn.ioos.noaa.gov/media/2017/12/hfradar_nodc_sep_2014.pdf"
        self.platform = "CODAR SeaSonde, COASTAL STATIONS"
        self.platform_vocabulary = "Global Change Master Directory (GCMD) Keywords, Version 21.2"
        self.project = "NESDIS Common Cloud Framework."
        self.publisher_email = "espcoperations@noaa.gov"
        self.publisher_type = "institution"
        self.publisher_name = "DOC/NOAA/NESDIS/OSPO > Office of Satellite and Product Operations, NESDIS, NOAA, U.S. Department of Commerce."
        self.publisher_url = "http://www.ospo.noaa.gov"
        self.history = ""
        self.uuid = ""
        
class SetupError(Exception):
    pass

class DatabaseError(Exception):
    pass
