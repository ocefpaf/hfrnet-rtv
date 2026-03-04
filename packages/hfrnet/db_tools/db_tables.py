import logging
from hfrnet.utils_funcs.lib_rtv import DatabaseError, RtvProcess
from hfrnet.db_tools.db_manager import db_manager
from datetime import timedelta, timezone, datetime
from decimal import Decimal
from hfrnet.utils_funcs import constsHFR
from hfrnet.utils_funcs.utility import get_s3_directory_path, check_lock


_log = logging.getLogger()


def read_domain(db_class, configureVals):
	# Check for valid domain
	sqlquery = (f"SELECT description, id FROM domain WHERE name = "
				f"'{configureVals.domain}'")
	result_list = db_class.get_query(sqlquery)
	# % Expect exactly one record to match
	n = len(result_list)
	if n == 0:
		_log.error(f"{configureVals.domain} is not defined in the configuration "
					f"database")
		db_class.close()
		raise DatabaseError()
	elif n > 2:
		_log.error(f"{configureVals.domain} returned {n} rows where only one expected")
		db_class.close()
		raise DatabaseError()

	configureVals.domain_id = result_list['id'][0]
	configureVals.domain_description = result_list['description'][0]
	# --- success


def read_resolution(db_class, configureVals):
	# %% Check for valid resolution
	sqlquery = (f"SELECT id FROM resolution WHERE name = "
				f"'{configureVals.resolution}'")
	result_list = db_class.get_query(sqlquery)

	# % Expect exactly one record to match
	n = len(result_list)
	if n != 1:
		if n == 0:
			_log.error(f"Resolution {configureVals.resolution} is not defined in the "
						f"database for domain {configureVals.domain}")
			db_class.close()
			raise DatabaseError()
		else:
			_log.error(f"Resolution query for {configureVals.domain} : "
						f"{configureVals.resolution} "
						f"returned {n} rows where only one expected")
			db_class.close()
			raise DatabaseError()
	configureVals.resolution_id = result_list['id'][0]


def read_methods(db_class, mconfigurevals, mrtvparameters, mstcparameters,
				mltaparameters, process_list):
	# Get realtime process(es) to run, the methods table
	sqlquery = f"SELECT p.name,m.name,m.description,rp.save_as FROM realtime_process rp " \
				f"JOIN domain d ON d.id = rp.domain_id " \
				f"JOIN resolution r ON r.id = rp.resolution_id " \
				f"JOIN process p ON p.id = rp.process_id " \
				f"JOIN combine_method m ON m.id = p.combine_method_id " \
				f"WHERE rp.status = 'enabled' " \
				f"AND d.name = '{mconfigurevals.domain}' " \
				f"AND r.name = '{mconfigurevals.resolution}' " \
				f"ORDER BY rp.priority"

	result_list = db_class.get_query(sqlquery)
	# % Return if there are no processes found to run


	n = len(next(iter(result_list.values())))
	if n == 0:
		_log.error(f"there are no processes found to run")
		db_class.close()
		raise DatabaseError()

	# RTV uwls Unweighted Least Squares ascii,netcdf
	# STC uwls Unweighted Least Squares ascii,netcdf
	# LTA uwls Unweighted Least Squares ascii,netcdf

	_log.info("--------------------------------------------------------------")

	for i in range(n):
		process_list.append(
			RtvProcess(result_list['name'][i], result_list['name_2'][i],
						result_list['description'][i], result_list['save_as'][i]))

	for row in process_list:
		_log.info(f"{row.name}, {row.method}, {row.methoddesc}, {row.saveas}")

	for row in process_list:
		processname = row.name
		methodname = row.method
		if processname.lower() == "rtv":
			_log.info("--rtv--")
			sqlquery = f"SELECT " \
						f"p.max_age,p.min_rad_sites,p.min_radials,p.max_rad_speed," \
						f"p.grid_search_radius,p.max_rtv_speed,p.uwls_max_hdop," \
						f"p.uwls_max_hdop_ascii,p.uwls_max_hdop_nc " \
						f"FROM rtv_parameter p " \
						f"JOIN domain d ON d.id = p.domain_id " \
						f"JOIN resolution r ON r.id = p.resolution_id " \
						f"JOIN combine_method m ON m.id = p.combine_method_id " \
						f"WHERE m.name = '{methodname.lower()}' " \
						f"AND d.name = '{mconfigurevals.domain}' " \
						f"AND r.name = '{mconfigurevals.resolution}'"

			result_list = db_class.get_query(sqlquery)

			nrows = len(result_list['max_age'])

			if nrows == 0:
				_log.error(f"RTV parameters are not defined for "
							f"{mconfigurevals.resolution} and {mconfigurevals.domain}")
				db_class.close()
				raise DatabaseError()

			elif nrows > 1:
				_log.error(f"RTV parameter query for {mconfigurevals.domain} "
							f"{mconfigurevals.resolution} returned {n} rows where only "
							f"one expected")
				db_class.close()
				raise DatabaseError()

			elif nrows == 1:
				# collect the parameters
				tmp = dict(result_list)
				mrtvparameters.max_age = tmp['max_age'][0]
				mrtvparameters.grid_search_radius = tmp['grid_search_radius'][0]
				mrtvparameters.max_rad_speed = tmp['max_rad_speed'][0]
				mrtvparameters.max_rtv_speed = tmp['max_rtv_speed'][0]
				mrtvparameters.min_rad_sites = tmp['min_rad_sites'][0]
				mrtvparameters.min_radials = tmp['min_radials'][0]
				mrtvparameters.uwls_max_hdop = tmp['uwls_max_hdop'][0]
				mrtvparameters.uwls_max_hdop_ascii = tmp['uwls_max_hdop_ascii'][0]
				mrtvparameters.uwls_max_hdop_nc = tmp['uwls_max_hdop_nc'][0]

		# ------------------------------------------------------------
		elif processname.lower() == "stc":
			_log.info("--stc--")
			sqlquery = f"SELECT " \
						f"p.min_temporal_coverage,p.max_age,p.max_error  " \
						f"FROM stc_parameter p " \
						f"JOIN domain d ON d.id = p.domain_id " \
						f"JOIN resolution r ON r.id = p.resolution_id " \
						f"JOIN combine_method m ON m.id = p.combine_method_id " \
						f"WHERE m.name = '{methodname.lower()}' " \
						f"AND d.name = '{mconfigurevals.domain}' " \
						f"AND r.name = '{mconfigurevals.resolution}'"
			result_list = db_class.get_query(sqlquery)

			nrows = len(result_list['max_error'])
			_log.info(nrows)
			if nrows == 0:
				_log.error(f"STC parameters are not defined for "
							f"{mconfigurevals.resolution} and {mconfigurevals.domain}")
				db_class.close()
				raise DatabaseError()

			elif nrows > 1:
				_log.error(f"STC parameter query for {mconfigurevals.domain} "
							f"{mconfigurevals.resolution} returned {n} rows where only "
							f"one expected")
				db_class.close()
				raise DatabaseError()

			elif nrows == 1:
				# collect the parameters
				tmp = dict(result_list)
				mstcparameters.min_temporal_coverage = tmp['min_temporal_coverage'][0]
				mstcparameters.max_age = tmp['max_age'][0]
				mstcparameters.max_error = tmp['max_error'][0]
				# ------------------------------------------------------------
		elif processname.lower() == "lta":
			_log.info("--lta--")
			sqlquery = f"SELECT " \
						f"p.min_month_temporal_coverage,p.min_year_temporal_coverage," \
						f"p.max_error  " \
						f"FROM lta_parameter p " \
						f"JOIN domain d ON d.id = p.domain_id " \
						f"JOIN resolution r ON r.id = p.resolution_id " \
						f"JOIN combine_method m ON m.id = p.combine_method_id " \
						f"WHERE m.name = '{methodname.lower()}' " \
						f"AND d.name = '{mconfigurevals.domain}' " \
						f"AND r.name = '{mconfigurevals.resolution}'"
			result_list = db_class.get_query(sqlquery)

			nrows = len(result_list['max_error'])
			_log.info(nrows)
			if nrows == 0:
				_log.error(f"LTA parameters are not defined for "
							f"{mconfigurevals.resolution} and {mconfigurevals.domain}")
				db_class.close()
				raise DatabaseError()

			elif nrows > 1:
				_log.error(f"LTA parameter query for {mconfigurevals.domain} "
							f"{mconfigurevals.resolution} returned {n} rows where only "
							f"one expected")
				db_class.close()
				raise DatabaseError()

			elif nrows == 1:
				# collect the parameters
				# mltaparameters = dict(result_list)
				tmp = dict(result_list)
				mltaparameters.min_month_temporal_coverage = \
					tmp['min_month_temporal_coverage'][0]
				mltaparameters.min_year_temporal_coverage = \
					tmp['min_year_temporal_coverage'][0]

		else:
			_log.error(f"Unknown process {processname}"
						f"obtained, no parameters obtained")
			db_class.close()
			raise DatabaseError()


def read_site_table(configObj):
	# Connect to the configuration database

	with db_manager(configObj.dbObject) as db_class:

		# Build & execute query
		sqlquery = (
			'SELECT s.network,s.name '
			'FROM site s '
			'JOIN site_config c ON s.id = c.site_id '
			'JOIN domain d ON c.domain_id = d.id '
			'JOIN resolution r ON c.resolution_id = r.id '
			f"WHERE d.name LIKE '{configObj.domain}' "
			f"AND r.name LIKE '{configObj.resolution}' "
			'GROUP BY s.network,s.name')

		sites_list = db_class.get_query(sqlquery)

	# % Expect exactly one record to match

	nRows = len(next(iter(sites_list.values())))

	if nRows == 0:
		errmsg = (f'No sites defined for RTV {configObj.resolution} '
					f'{configObj.domain} processing')
		_log.error(errmsg)

		raise DatabaseError()

	elif nRows > 0:
		msg = f'Found {nRows} sites associated with {configObj.domain} {configObj.resolution}'
		_log.info(msg)
	return sites_list
	# ------------------------------------


def get_files_times_radialtable(configObj, rtvInfoObj, sites_list, minTime):
	# Check for valid domain
	# Connect to the configuration database
	with db_manager(configObj.dbObject,configObj.radial_dbname) as db_class:

		# Build & execute query
		sqlquery = (
			'SELECT FROM_UNIXTIME(r.time) '
			'FROM radialfiles r '
			'JOIN network n ON n.network_id = r.network_id '
			'JOIN site s ON s.site_id = r.site_id '
			f"WHERE (r.file_arrival_time >= '{rtvInfoObj.current_state}') "
			f"AND r.file_arrival_time < '{rtvInfoObj.new_state}' "
			f"AND FROM_UNIXTIME(r.time) >= '{minTime}' "
			'AND ( ')
		# Site conditions
		nSite = len(next(iter(sites_list.values())))
		for i in range(nSite):

			# Network and site
			network_tmp = sites_list["network"][i]
			name_tmp = sites_list["name"][i]
			sqlquery = (f'{sqlquery}'
						f"( n.net = '{network_tmp}' AND s.sta = '{name_tmp}')")

			# End statement
			if i == nSite - 1:
				sqlquery = f"{sqlquery} )"
			else:
				sqlquery = f"{sqlquery} OR "

		time_list = db_class.get_query(sqlquery)

	# % Expect exactly one record to match

	nRows = len(next(iter(time_list.values())))

	msg = f'Found {nRows} sites associated with {configObj.domain} {configObj.resolution}'
	_log.info(msg)
	return time_list, nRows
	# ------------------------------------


def get_files_list_radialtable(configObj, calcTime, siteInfoObj):
	# Check for valid domain
	# Connect to the configuration database
	# DATE_FORMAT = "%Y-%m-%d"
	# TIME_FORMAT = "%H:%M:%S"
	# DATETIME_FORMAT = DATE_FORMAT + " " + TIME_FORMAT
	t_lower = (calcTime - timedelta(minutes=30)).strftime(constsHFR.DATETIME_FORMAT)
	t_upper = (calcTime + timedelta(minutes=30)).strftime(constsHFR.DATETIME_FORMAT)

	with db_manager(configObj.dbObject,configObj.radial_dbname) as db_class:
		sqlquery = ('SELECT '
					'FROM_UNIXTIME(r.time) AS t,n.net,s.sta,patterntype,file_arrival_time,'
					'lat,lon,range_res,range_bin_end,manufacturer,dfile,dir '
					'FROM radialfiles r '
					'JOIN network n ON n.network_id = r.network_id '
					'JOIN site s ON s.site_id = r.site_id '
					f"WHERE FROM_UNIXTIME(r.time) >= '{t_lower}' "
					f"AND FROM_UNIXTIME(r.time) < '{t_upper}' ")
  
					# f"WHERE FROM_UNIXTIME(r.time) >= '{calcTime - timedelta(minutes=30)}' "
					# f"AND FROM_UNIXTIME(r.time) < '{calcTime + timedelta(minutes=30)}' ")

		# Site conditions
		nSite = len(siteInfoObj)

		if nSite > 0:
			sqlquery = f"{sqlquery}AND ( "
		for i in range(nSite):
			# Network and site
			network_temp = siteInfoObj[i].network
			name_temp = siteInfoObj[i].name
			beampattern_temp = siteInfoObj[i].beampattern
			useMinute_temp = siteInfoObj[i].useMinute
			sqlquery = (f'{sqlquery}'
						f"( n.net = '{network_temp}' AND s.sta = '{name_temp}' ")

			# Beampattern
			if beampattern_temp == 'ideal':
				sqlquery = f"{sqlquery}AND r.patterntype = 'i' "
			elif beampattern_temp == 'measured':
				sqlquery = f"{sqlquery}AND r.patterntype = 'm' "
			else:
				errmsg = f'Unknown beam pattern type {beampattern_temp}'
				_log.error(errmsg)

			# Radial timestamp
			if useMinute_temp == 0:
				tr = calcTime.strftime(constsHFR.DATETIME_FORMAT)
			elif useMinute_temp > 0 and useMinute_temp < 30:
				tr = (calcTime + timedelta(minutes=useMinute_temp)).strftime(
					constsHFR.DATETIME_FORMAT)
			elif useMinute_temp >= 30 and useMinute_temp < 60:
				tr = ((calcTime - timedelta(minutes=60 - useMinute_temp)).
						strftime(constsHFR.DATETIME_FORMAT))
			else:
				tr = ""
				errmsg = (
					f'useMinute value of {useMinute_temp} is out of range '
					f'for site {network_temp}:{name_temp}. Value must [0-59]')
				_log.error(errmsg)

			sqlquery = f"{sqlquery}AND FROM_UNIXTIME(FLOOR(r.time/60)*60) = '{tr}')"

			# End statement
			if i == nSite - 1:
				sqlquery = f"{sqlquery})"
			else:
				sqlquery = f"{sqlquery} OR "

		files_list = db_class.get_query(sqlquery)

		# % Expect exactly one record to match
		nRows = len(next(iter(files_list.values())))
		list_of_dicts = [dict(zip(files_list, t)) for t in
							zip(*files_list.values())]

		# Convert all Decimal objects to float
		for ifile_dict in list_of_dicts:
			for key, value in ifile_dict.items():
				if isinstance(value, Decimal):
					ifile_dict[key] = float(value)

		if nRows == 0:
			errmsg = f'No match found in the radial table'
			_log.error(errmsg)

	return list_of_dicts, nRows


def get_active_sitelist(configObj, calcTime):
	# Connect to the configuration database

	with db_manager(configObj.dbObject) as db_class:
		# Build & execute query
		sqlquery = (
			'SELECT s.network,s.name,c.beampattern,c.use_radial_minute,s.id '
			'FROM site s '
			'JOIN site_config c ON c.site_id = s.id '
			'JOIN domain d ON c.domain_id = d.id '
			'JOIN resolution r ON c.resolution_id = r.id '
			f"WHERE d.name LIKE '{configObj.domain}' "
			f"AND r.name LIKE '{configObj.resolution}' "
			f"AND c.start_time <= '{calcTime}' AND "
			f"( c.end_time > '{calcTime}' OR ISNULL(c.end_time) )")

		active_sites = db_class.get_query(sqlquery)

	nRows = len(next(iter(active_sites.values())))

	if nRows == 0:
		errmsg = (f'No sites defined for RTV {configObj.resolution} '
					f'{configObj.domain} processing')
		_log.error(errmsg)

		raise DatabaseError()

	elif nRows > 0:
		msg = f'Found {nRows} sites associated with {configObj.domain} {configObj.resolution}'
		_log.info(msg)

	return active_sites, nRows

def get_state_time(configObj, process_name):
	# Connect to the configuration database

	with db_manager(configObj.dbObject) as db_class:
		# Build & execute query
		state_time = None
		sqlquery = ('SELECT time '
					'FROM state '
					f"WHERE name = '{process_name}' "
					f"AND domain_id = '{configObj.domain_id}' "
					f"AND resolution_id = '{configObj.resolution_id}' ")

		results = db_class.get_query(sqlquery)
		nRows = len(next(iter(results.values())))
		if nRows > 0:
			state_time = results['time'][0]
			# if results['csv']:
			# 	state_csv = results['csv']
			# state_csv = ''

	return state_time


def get_files_list_intem_table(configObj, calcTime, process_name):
	# Check for valid domain
	# Connect to the configuration database

	with db_manager(configObj.dbObject, configObj.radial_dbname) as db_class:
		sqlquery = (
			'SELECT f.name,f.dir from inter_files f '
			f"WHERE f.domain = '{configObj.domain}' "
			f"AND f.res = '{configObj.resolution}' "
			f"AND f.stime = '{calcTime}' "
			f"AND f.process = '{process_name}'")

		file_list = db_class.get_query(sqlquery)

		nrow = len(next(iter(file_list.values())))
		return file_list, nrow


def update_state_time(configObj, process_name, state_time):
	# Connect to the configuration database
	record_pars = {
		"name": f"'{process_name}'",
		"domain_id": f"'{configObj.domain_id}'",
		"resolution_id": f"'{configObj.resolution_id}'",
	}

	record_pars_str = ''.join([f"{key} = {value} AND " for key, value in record_pars.items()])
	record_pars_str = record_pars_str[:-5]

	with db_manager(configObj.dbObject, configObj.config_dbname) as db_class:
		# Build & execute query
		sqlquery = ('SELECT COUNT(*) '
					f"FROM state WHERE {record_pars_str}")

		results = db_class.get_query(sqlquery)
		nRows = len(next(iter(results.values())))
		if nRows > 0:
			# if exists, the delete it
			delete_query = f"DELETE FROM state WHERE {record_pars_str}"
			_log.info(f" Updating the state record for {record_pars_str}")
			try:
				db_class.write_query(delete_query)
			except Exception as err:
				msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
						f", Can't delete the record from the DB")
				_log.fatal(msg)
		else:
			_log.info(f" No updates needed for the state time of {process_name}::"
						f"{configObj.domain}::{configObj.resolution}")
		# ---- Add the intermediate file to the DB table
		record_pars["time"] = f"'{state_time}'"
		# Create a string of the keys
		keys_str = ', '.join(record_pars.keys())
		# Create a string of the values
		values_str = ', '.join(record_pars.values())
		insert_query = f"INSERT INTO state ({keys_str}) VALUES ({values_str})"
		try:
			db_class.write_query(insert_query)
		except Exception as err:
			msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
					f", Can't add the record ::{insert_query}:: to the inter_files")
			_log.fatal(msg)

	return


# -----------------------------------------
def check_lock_process(configObj):
	from hfrnet.utils_funcs.utility import current_datetime
	from hfrnet.utils_funcs.constsHFR import process_time

	_log.info(" Check if process is already running ")
	_log.info(f" Check for Domain = {configObj.domain}:: and resolution ="
							f" {configObj.resolution}.")
	# Connect to the configuration database

	with db_manager(configObj.dbObject, configObj.config_dbname) as db_class:
		# Build & execute query
		sqlquery = (f"SELECT exe_time, process_running FROM lock_process WHERE domain = "
					f"'{configObj.domain}' AND resolution = '{configObj.resolution}' ")

		try:
			results = db_class.get_query(sqlquery)
			nRows = len(next(iter(results.values())))
			ct = current_datetime()

			if nRows > 0:
				ct_temp = results['exe_time'][0]
				process_stime = ct_temp.replace(tzinfo=timezone.utc)

				db_locked = check_lock(results)
				if db_locked:
					_log.fatal(f"Process of Domain = {configObj.domain}:: and resolution ="
							f" {configObj.resolution} already running.  Can't run")
					return True
				else:
					_log.info(f" Locking process for "
								f"Domain = {configObj.domain}:: and resolution ="
								f" {configObj.resolution}.")

					update_query = (f"UPDATE lock_process SET exe_time = '{ct}', process_running = true  "
									f"WHERE domain = '{configObj.domain}' "
									f"AND resolution = '{configObj.resolution}'")
					try:
						db_class.write_query(update_query)
						return False
					except Exception as err:
						msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
								f", Can't update the lock_process for "
								f"{configObj.domain}::{configObj.resolution}")
						_log.fatal(msg)
						return True
			else:
				_log.info(f" Adding process Locking for "
							f"Domain = {configObj.domain}:: and resolution ="
							f" {configObj.resolution}")

				lock_query = (f"INSERT into lock_process (domain, resolution, exe_time, process_running) "
							f"values ('{configObj.domain}', '{configObj.resolution}',"
							f"'{ct}', true )")
				try:
					db_class.write_query(lock_query)
					return False
				except Exception as err:
					msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
							f", Can't update the lock_process for "
							f"{configObj.domain}::{configObj.resolution}")
					_log.fatal(msg)
					return True
		except Exception as err:
			msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
					f", The lock_process does not exist in the database "
					f"The process is terminated")
			_log.fatal(msg)
			return True

def clear_state_table(configObj):
	# Connect to the configuration database

	with db_manager(configObj.dbObject) as db_class:
		#------- check the table
		sqlquery = ('SELECT COUNT(*) FROM state ')

		results = db_class.get_query(sqlquery)
		nRows = len(next(iter(results.values())))
		_log.info(f"===>>> state table before clearing,{nRows}")

		# Build & execute query
		sqlquery = ('DELETE FROM state ')

		db_class.write_query(sqlquery)
		_log.info("===>>> state table is cleared")
		#------- check the table
		sqlquery = ('SELECT COUNT(*) FROM state ')

		results = db_class.get_query(sqlquery)
		nRows = len(next(iter(results.values())))
		_log.info(f"===>>> state table after clearing,{nRows}")


	return 

def record_output_files(configObj, file_name, process_name, s3_dir_name):
	"""
	MariaDB [hfradar]> select * from inter_files where stime > '2023-01-01 20:00:00' and res like '6km';
	+----+--------+-----+---------+---------------------+---------------------------------------+----------------------------------------------------------+
	| id | domain | res | process     | stime               | name                                  | dir                                                      |
	+----+--------+-----+---------+---------------------+---------------------------------------+----------------------------------------------------------+
	| 11 | ushi   | 6km | rtv_inter   | 2023-01-01 23:00:00 | rtv_ushi_6km_uwls_2023_01_01_2300.mat | /data/smcd12/ASSISTT_DATA/HFRnet/SFTP/hfrtv/USHI/2023_01 |
	| 15 | ushi   | 6km | rtv_inter   | 2023-01-01 22:00:00 | rtv_ushi_6km_uwls_2023_01_01_2200.mat | /data/smcd12/ASSISTT_DATA/HFRnet/SFTP/hfrtv/USHI/2023_01 |
	| 20 | ushi   | 6km | month_total | 2023-01-01 21:00:00 | rtv_ushi_6km_uwls_2023_01_01_2100.mat | /data/smcd12/ASSISTT_DATA/HFRnet/SFTP/hfrtv/USHI/2023_01 |
	+----+--------+-----+---------+---------------------+---------------------------------------+----------------------------------------------------------+
	month aver--->rtv_inter
	ann aver --> month_total
	select * from inter_files where stime > '2023-01-01 20:00:00' and res like '6km';
	select count(*) from inter_files;
	"""
	from hfrnet.utils_funcs.utility import get_file_stime

	stime = get_file_stime(file_name)
	record_pars = {
		"domain": f"'{configObj.domain}'",
		"res": f"'{configObj.resolution}'",
		"process": f"'{process_name}'",
		"stime": f"'{stime}'"
	}
	record_pars_str = ''.join([f"{key} = {value} AND " for key, value in record_pars.items()])
	# rtv-ushi-6km-uwls_v1r0_hfr_intermediate_s202504171300000_e202504171300000_c202504181545556.nc
	record_pars_str = record_pars_str[:-5] # to remove the last 5 = len(' AND ')

	with db_manager(configObj.dbObject, configObj.radial_dbname) as db_class:	
		# check if the record exists
		sqlquery = ('SELECT COUNT(*) '
					f"FROM inter_files WHERE {record_pars_str}")
		results = db_class.get_query(sqlquery)
		nRows = len(next(iter(results.values())))
		if nRows > 0:
			# if exists, the delete it
			delete_query = f"DELETE FROM inter_files WHERE {record_pars_str}"
			_log.info(f" Updating the inter_files record for {record_pars_str}")
			try:
				db_class.write_query(delete_query)
			except Exception as err:
				msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
						f", Can't delete the record from the DB")
				_log.fatal(msg)
		# ---- Add the intermediate file to the DB table
		record_pars["name"] = f"'{file_name}'" ;
		dir_path = get_s3_directory_path(datetime.strptime(stime, constsHFR.DATETIME_FORMAT), s3_dir_name, configObj)
		record_pars["dir"] = f"'{configObj.output_intermed_s3_loc}/{dir_path}'"
		# Create a string of the keys
		keys_str = ', '.join(record_pars.keys())
		# Create a string of the values
		values_str = ', '.join(record_pars.values())
		insert_query = f"INSERT INTO inter_files ({keys_str}) VALUES ({values_str})"
		try:
			db_class.write_query(insert_query)
		except Exception as err:
			msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
					f", Can't add the record ::{insert_query}:: to the inter_files")
			_log.fatal(msg)


	return

def create_db_table_inter_files(configObj):
	"""
	Creates the inter_files table in the "hfradar" 

	"""
	_log.info(f" === CREATE TABLE IF NOT EXISTS inter_files == ")

	with db_manager(configObj.dbObject, configObj.radial_dbname) as db_class:
		# Create a new table
		create_table_query = """
				CREATE TABLE IF NOT EXISTS inter_files (
					id INT AUTO_INCREMENT PRIMARY KEY,
					domain VARCHAR(255) NOT NULL,
					res VARCHAR(255) NOT NULL,
					process VARCHAR(255) NOT NULL,
					stime timestamp NOT NULL,
					name VARCHAR(255) NOT NULL,
					dir VARCHAR(255) NOT NULL
				)"""
		try:
			db_class.write_query(create_table_query)
		except Exception as err:
			msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
					f", Can't create inter_files ::{create_table_query}::")
			_log.fatal(msg)

def create_db_table_lock_process(configObj):
	"""
	Creates the lock_process table in the "rtvproc" 

	"""
	_log.info(f" === CREATE TABLE IF NOT EXISTS lock_process == ")
	with db_manager(configObj.dbObject, configObj.config_dbname) as db_class:
		# Create a new table
		create_table_query = """
			CREATE TABLE IF NOT EXISTS lock_process 
			( id INT AUTO_INCREMENT PRIMARY KEY, 
			exe_time timestamp NOT NULL, process_running INT NOT NULL,  
			domain VARCHAR(255) NOT NULL, 
			resolution VARCHAR(255) NOT NULL)
			"""
		try:
			db_class.write_query(create_table_query)
		except Exception as err:
			msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
					f", Can't create lock_process ::{create_table_query}::")
			_log.fatal(msg)


def update_db_lock(configObj):
        """
           update the database to keep it locked
        """

        from hfrnet.utils_funcs.utility import current_datetime
        
        ct = current_datetime()
        with db_manager(configObj.dbObject, configObj.config_dbname) as db_class:
                
                update_query = (f"UPDATE lock_process SET exe_time = '{ct}', process_running = true "
                                f"WHERE domain = '{configObj.domain}' "
                                f"AND resolution = '{configObj.resolution}'")
                try:
                        db_class.write_query(update_query)
                        return False
                except Exception as err:
                        msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
                               f", Can't update the lock_process for "
                               f"{configObj.domain}::{configObj.resolution}")
                        
def clear_db_lock(configObj):
        """
           Unlocks the database after the running is complete
        """

        with db_manager(configObj.dbObject, configObj.config_dbname) as db_class:
                update_query = (f"UPDATE lock_process SET process_running = false "
                                f"WHERE domain = '{configObj.domain}' "
                                f"AND resolution = '{configObj.resolution}'")
                try:
                        db_class.write_query(update_query)
                        return False
                except Exception as err:
                        msg = (f" ---- FATAL ERROR:Unexpected {err=}, {type(err)=}"
                               f", Can't unlock by setting the process_running = false for "
                               f"{configObj.domain}::{configObj.resolution}")
                        _log.error(msg)


def check_time_len_db(check_time, configObj):
        """
           Update the timestamp for db_lock if it has been longer than the set time limit (constsHFR.process_time)
           Return updated timestamp if db has been updated, else the same time
        """
        from hfrnet.utils_funcs.utility import current_datetime
        
        time_diff = current_datetime() - check_time
        if time_diff > constsHFR.process_time:
                update_db_lock(configObj)
                return current_datetime()
        else:
                return check_time
