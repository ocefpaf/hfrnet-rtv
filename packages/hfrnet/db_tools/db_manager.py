"""db_manager"""

import os
import boto3
from botocore.config import Config
import ssl
import urllib.request
import pymysql

from hfrnet.utils_funcs.lib_rtv import DatabaseConfig
from hfrnet.utils_funcs.constsHFR import rds_CERTIFICATE_URL, docker_CERTIFICATE_PATH
import logging

_log = logging.getLogger()

class db_manager:
    """manages the database connection and queries"""

    def __init__(self, dbObject, dbname='rtvproc'):
        self.dbConfig = dbObject
        self.dbConfig.db_name=dbname
        self.conn_handel = None

    def __enter__(self):
        _log.info(f" >>> self.connect ::{self.dbConfig.db_name}::")
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def generate_token(self):
        """
        Use IAM database authentication when your application requires fewer than 200 new IAM database authentication connections per second. 
        The database engines that work with Amazon RDS don't impose any limits on authentication attempts per second. However, when you use
        IAM database authentication, your application must generate an authentication token. Your application then uses that token to connect
        to the DB instance. If you exceed the limit of maximum new connections per second, then the extra overhead of IAM database 
        authentication can cause connection throttling.
        """
        from botocore.config import Config

        my_config = Config(
            retries = {
                'max_attempts' : 3,
                'mode': 'adaptive'
            }
        )
        
        if self.dbConfig.run_env == 'ao':
            session = boto3.Session()
        else:
            session = boto3.Session(region_name=self.dbConfig.region)
        client = session.client('rds', config=my_config)

        # Generate the authentication token
        self.dbConfig.password = client.generate_db_auth_token(DBHostname=self.dbConfig.host,
                                                               Port=self.dbConfig.port,
                                                               DBUsername=self.dbConfig.user,
                                                               Region=self.dbConfig.region)
        _log.info("Generating --> token = client.generate_db_auth_token")
        _log.info("======= token =================================")
        _log.info(f"{self.dbConfig.password}")
        _log.info("========================================")

    def connect(self):
        _log.info(f"-- Running in {self.dbConfig.run_env }")

        self.generate_token()

        try:
            if self.dbConfig.run_env == 'rhw':
                # -- connect on local rhw linux
                self.conn_handel = pymysql.connect(
                    host=self.dbConfig.host,
                    user=self.dbConfig.user,
                    database=self.dbConfig.db_name)
            else:
                # #--- connect on AWS
                # _log.info(f"---------------------------------------------")
                _log.info(f" ::self.dbConfig.run_env::{self.dbConfig.run_env}")
                # _log.info(f"--------self.dbConfig.password ::{self.dbConfig.password} ")
                # _log.info(f"-------- pymysql.connect ")

                self.conn_handel = pymysql.connect(host = self.dbConfig.host,
                                                user = self.dbConfig.user,
                                                password = self.dbConfig.password,
                                                database = self.dbConfig.db_name,
                                                port =self.dbConfig.port,
                                                ssl = self.dbConfig.ssl_context)
        
                _log.info(f"---------------------------- connected to ::{self.dbConfig.db_name} database")
                # _log.info(f"---------------------------------------------")
        except Exception as err:
            msg = (f" ---- FATAL ERROR:Unexpected {err} ::::, {type(err)}::::"
                f", Can't connect to the database: user={self.dbConfig.user}, "
                f"database={self.dbConfig.db_name}")
            _log.fatal(msg)
        if self.conn_handel is None:
            msg = " Database connection failed, handle is none"
            _log.fatal(msg)
            raise ValueError(msg)
            
            
    #----------------------------------------------------------
    
    def get_query(self, query):
        _log.info(" -------->>>>>>>>>>>>>> get_query ------------------ ")
        _log.info(query)
        datasetdict = {}
        with self.conn_handel.cursor() as cursor:
            cursor.execute(query)
            # Fetch the first row
            rows = cursor.fetchall()
            self.create_dict(rows, cursor.description, datasetdict)
            
            _log.info(" ------------------ ")
            _log.info(f" ------------------  {len(datasetdict)}")
            for key, value in datasetdict.items():
                msg = f"{key}:::{value}"
                _log.info(msg)
            _log.info(" -------->>>>>>>>>>>>>> get_query ------------------ ")

        return datasetdict
    #----------------------------------------------------------
    def write_query(self, query):
        _log.info(" -------->>>>>>>>>>>>>>------------------ ")
        _log.info(query)
        
        with self.conn_handel.cursor() as cursor:
            nNpdated_rows = cursor.execute(query)
            if nNpdated_rows>0:
                _log.info(f" Database table is updated")
                self.conn_handel.commit()

        return

    # ----------------------------------------------------------
    def check_dict(self, my_dict, key, add, value):
        # Check if the key exists in the dictionary
        if key in my_dict:
            # Append the string to the existing value
            # value = my_dict[key]
            key += f"{add}"
            my_dict[key] = value
        else:
            # Add the key with the new string as its value
            my_dict[key] = value
    #----------------------------------------------------------

    def create_dict(self, data_rows, headers, datasetdict):
        # List of tuples
        for i in range(len(headers)):
            col_head = headers[i][0]
            list1 = []
            for row in data_rows:
                list1.append(row[i])

            #-- to check the repeated dict key, then append "_2"
            self.check_dict(datasetdict, col_head, "_2", list1)

    #----------------------------------------------------------

    def close(self):
        self.conn_handel.close()
        _log.info(f" >>> self.conn_handel.close ::{self.dbConfig.db_name}::")
    #----------------------------------------------------------
#------------------ new stuff here \/
    def table_exists(self, table_name):
        self.cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
        result = self.cursor.fetchone()
        return result is not None
    #----------------------------------------------------------
    def create_lock_process_table(self, table_name):
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS lock_process (
            id INT AUTO_INCREMENT PRIMARY KEY,
            exe_time DATETIME,
            domain VARCHAR(255),
            resolution VARCHAR(255)
        )
        """
        self.write_query(create_table_query)
    #----------------------------------------------------------

def set_db_host():
    """
        The database host will change depending on the environment
    """
    _log.info('----------------------')
    _log.info('Set the database host based on the running env id')
    
    my_config = Config(
        retries = {
            'max_attempts' : 3,
            'mode' : 'adaptive'
        }
    )
    
    sts = boto3.client('sts', config=my_config)
    response = sts.get_caller_identity()
    acc_id = response.get('Account')
    
    _log.info(f'------Account {acc_id}')
    if acc_id == '560271376700': # Dev/Sandbox
        host = 'nesdis-nccfdev5006-hfrnet-db.cluster-cggwesdxhbs9.us-east-1.rds.amazonaws.com'
    elif acc_id == '656149346314': # UAT
        host = 'nesdis-nccfuat5065-hfrnet-db.cluster-ciaelnl1aaal.us-east-1.rds.amazonaws.com'
    elif acc_id == '844319835141': # Prod
        host = 'nesdis-nccfprod5065-hfrnet-db.cluster-c1a7lh8kiqkv.us-east-1.rds.amazonaws.com'

    return host


# ----------------------------------------------------------
def set_db_info( config, configObj):
    """
    Set DB info to be used later...?
    """
    from hfrnet.db_tools.db_tables import create_db_table_inter_files, create_db_table_lock_process

    configObj.dbObject.user = config['databases.user']
    configObj.dbObject.host = set_db_host()
    configObj.dbObject.port = config['databases.port']
    configObj.dbObject.password = config['databases.password']
    configObj.dbObject.ssl_ca = config['databases.ssl_ca']
    configObj.dbObject.region = config['databases.region']
    configObj.dbObject.run_env = config['databases.run_env']

    #-------------------------------------------
    # --- set the ceritication parameters
    download_rds_certificate()
    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(configObj.dbObject.ssl_ca)
    context.verify_identity = True
    context.verify_cert = True
    context.auth_plugin_map = {'mysql_clear_password': None}
    configObj.dbObject.ssl_context = context

    #-------------------------------------------
    #---- set the environment parameters
    configObj.config_dbname = config['databases.config_dbname']
    configObj.radial_dbname = config['databases.radial_dbname']

    _log.info(f"---------------------------------------------")
    _log.info(f" set_db_info::Running Env is :: {configObj.dbObject.run_env}")
    os.environ['LIBMYSQL_ENABLE_CLEARTEXT_PLUGIN'] = '1'

    _log.info("========================================")
    _log.info(f" Create tables,inter_files,lock_process  if not exist")
    create_db_table_inter_files(configObj)
    create_db_table_lock_process(configObj)
    _log.info("========================================")


def download_rds_certificate():
    """Downloads the RDS certificate. Falls back to env variable if download fails."""

    def download_with_retries(url, filename, retries=3, delay=2):
        for attempt in range(retries):
            try:
                urllib.request.urlretrieve(url, filename)
                return
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(delay * (2 ** attempt))
                else:
                    error_msg = f"Not able to download certificate: {e}"
                    _log.error(error_msg)
                    raise e


    _log.info(f"------ in download_rds_certificate")   
    try:
        _log.debug("Attempting to download RDS certificate from AWS...")
        #urllib.request.urlretrieve(rds_CERTIFICATE_URL, docker_CERTIFICATE_PATH)
        download_with_retries(rds_CERTIFICATE_URL, docker_CERTIFICATE_PATH)
        _log.debug("Certificate downloaded successfully.")
    except Exception as download_error: # TODO: coding standards require catching specific errors.
        _log.debug(f"Download failed: {download_error}")
        # Fallback to ENV variable if download fails
        if os.getenv('DEFAULT_RDS_CERTIFICATE'):
            _log.debug("Using RDS certificate from environment variable.")
            with open(docker_CERTIFICATE_PATH, 'w') as cert_file:
                cert_file.write(os.environ['DEFAULT_RDS_CERTIFICATE'])
        else:
            raise RuntimeError("Failed to download certificate and no backup available in environment variable.")





