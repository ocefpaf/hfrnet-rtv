# HFRNet
HFRNet is a python package designed to process radial velocities measured by HF-RADAR to total solutions and other derived products.

[[_TOC_]]

## Important Resources
- __[Google Drive](https://drive.google.com/drive/folders/12joE1XzYbQWOT3Yez3ye7HmyPhhYnNPF)__
- __[Algorithm Support Document](https://docs.google.com/document/d/1QUiUwgeGr3LINf9lBWBIfja_m__yLKfTMWHam_f_Ooo/edit?tab=t.0#heading=h.gjdgxs)__
- __[Code Update Summary](https://docs.google.com/spreadsheets/d/1LFEU2PCXZDM0KcnGfjPqYXrtLYVtOh98xbwcV25BseE/edit?usp=sharing)__
- __[ASSISTT Delivery Schedule](https://docs.google.com/spreadsheets/d/107vHNeHh7s_z-1HO9KGt1te7pxqu-h7eMuOyrDKvQd8/edit?pli=1#gid=1641027802)__
- __[R2O Team Lookup](https://docs.google.com/spreadsheets/d/1u42Lu2QawJOKzCguXlfWYdcWOYyotDFGkkXkeyXCJCk/edit#gid=616569363)__

## Code Base Requirements
- Uses gitLFS: Yes
- Uses submodules: Yes

## Configuration Management

* Configuration Item: [NCCFCM-16623](https://jira.nesdis-hq.noaa.gov/jira/secure/insight/assets/NCCFCM-16623)

### System Requirements
- Unit Name: HFRNet
- Clock Time: ~5 min (depends on the process)
- Max Memory: ~15 GB
- CPU Usage: 1 CPU

### Library Packages Required
#### Needed in the Run Time Environment
- __Python__: see `conda_environment.yaml

#### Needed in the Compiled Time Environment
- N/A

### Extra Files Needed
- N/A

## Compiling the Code
- N/A


## Running the Code
Find the current Production rules in folder `test_data/` of the code base.

### HFRNet:

#### Config Yaml
```yaml
processing:
   domain: ushi
   resolution: 6km
   batch_processing: false
time:
   start_date: '202301040000000'
   end_date:   '202301040000000'
production:
   site: PLAIT
   environment: INT
   version: v1r0
directory:
   algorithm_dir: /home/WORKING_DIR/hfrnet
            #--- Do not edit this. It must be done in order for AO to move anything outside the AO sys
            #--- default path is /workflow/data/
   log: /workflow/data/logs
   #-- removing sending the output to AO to move it the s3 bucket, the algo is doing it
   output: /home/WORKING_DIR/output
   radial_local_dir: /home/WORKING_DIR/input/radials
   interm_local_dir: /home/WORKING_DIR/input/intermediate
   output_s3_bucket: s3://arn:aws:s3:us-east-1:560271376700:accesspoint/nccf-dev-pg-results-ao
   output_intermed_s3_bucket: s3://arn:aws:s3:us-east-1:560271376700:accesspoint/nccf-dev-pg-results-ao
   
databases:
   run_env: 'ao' # 'aws' 'rhw' 'ao'
   user: 'hfrnet'
   host: 'nesdis-nccfdev5006-hfrnet-db.cluster-cggwesdxhbs9.us-east-1.rds.amazonaws.com'
   port: 3306
   password: 'token'
   ssl_ca: '/tmp/us-east-1-bundle.pem' #'/home/ec2-user/environment/us-east-1-bundle.pem'
   region:  'us-east-1'
   config_dbname: 'rtvproc'
   radial_dbname: 'hfradar'
```

#### Input Files Needed
| File Type | Desired Location in Working Directory |
| --- | --- |
| .ruv | $radial_local_dir |
| .nc | $interm_local_dir |


#### Output Files Produced
All output files will be printed to the output.txt file, which is just a dump of the output handoff object from the AIM.  This handoff object gives every output file a "Label" which is what we are describing here.
| File Type | File Token Label | Type of Output<br>(Primary, Intermediate, Diagnostic) |
| --- | --- | --- |
| output netCDF files | | Primary |
| log  |  | Diagnostic |
| intermediate netCDF files|  | Intermediate |


#### Run on AO
##### Step 1: 
Create a Tag in the gitlab with all the changes. Make sure the field `version: "1.0.41"` of the the production rules yaml has the same value as the Tag you created, e.g., 1.0.41.

##### Step 2:
Submit a run request here:

https://nesdis-nccfdev5006-pg-ao-user.s3.amazonaws.com/index.html

Create an account if necessary. In the request page, update the configuration in the second text box, e.g., change the `request_name`, `sa_name` `run_start_time` and `run_end_time` as needed
```yaml
{
 "request_name": "ushi_6km",
 "sa_name": "HFRNet-ushi-6km",
 "version": "1.0.41",
 "run_mode": "RT",
 "run_start_time": "2025-05-01T14:30:00",
 "run_end_time": "2025-05-01T19:00:00"
}
```

And this is the example production rule for `ushi-6km`
```yaml
production_rule:
  sa_name: "HFRNet-ushi-6km"
  description: "Integrated Ocean Observing System (IOOS)"
  sa_id: "IOOS-HFRNet-ushi-6km"
  version: "1.0.41"
  runtime:
    resources:
      cpu: "1"
      memory: "2Gi"
      shm: "0Ki"
    command: ["/bin/bash", "-c", "cd hfrnet/packages  && python -m hfrnet.run_rtv ../test_data/config_hfr.yml -dom ushi -res 6km"]
    retry:
      limit: 2
      backoff: 5min
  #HFRNet will run every 30 minutes and will check for any updated radial files and run processes as necessary
  cron:
    schedule: "*/30 * * * *"
    default_search:
      ordered: False
      wait_for_file_interval: 30min
      maximum_observation_gap_interval: 30min

  outputs:
  - catalog_name: HFRNet
    copy_location: hfrnet/output
    file_pattern:
      regex: 'rtv-(?P<domain>\w+)-(?P<resolution>\w+)-(?P<product_name>[\w-]+)_v1r0_hfr_s(?P<start>\d{15})_e(?P<end>\d{15})_c(?P<create>\d{15}).nc'
    search:
      type: "system.temporal"
      temporal_search_boundaries:
        left_offset: -20min
        right_offset: 15min
    metadata:
      create:
        format: '%Y%m%d%H%M%S%f'
        type: datetime
        value:
          regex: 'rtv-(?P<domain>\w+)-(?P<resolution>\w+)-(?P<product_name>[\w-]+)_v1r0_hfr_s(?P<start>\d{15})_e(?P<end>\d{15})_c(?P<create>\d{15}).nc'
          from: "filename"
      end:
        format: '%Y%m%d%H%M%S%f'
        type: datetime
        value:
          from: "filename"
          regex: 'rtv-(?P<domain>\w+)-(?P<resolution>\w+)-(?P<product_name>[\w-]+)_v1r0_hfr_s(?P<start>\d{15})_e(?P<end>\d{15})_c(?P<create>\d{15}).nc'
      start:
        type: datetime
        format: '%Y%m%d%H%M%S%f'
        value:
          from: "filename"
          regex: 'rtv-(?P<domain>\w+)-(?P<resolution>\w+)-(?P<product_name>[\w-]+)_v1r0_hfr_s(?P<start>\d{15})_e(?P<end>\d{15})_c(?P<create>\d{15}).nc'
      domain:
        type: string
        value:
          from: "filename"
          regex: 'rtv-(?P<domain>\w+)-(?P<resolution>\w+)-(?P<product_name>[\w-]+)_v1r0_hfr_s(?P<start>\d{15})_e(?P<end>\d{15})_c(?P<create>\d{15}).nc'
      resolution:
        type: string
        value:
          from: "filename"
          regex: 'rtv-(?P<domain>\w+)-(?P<resolution>\w+)-(?P<product_name>[\w-]+)_v1r0_hfr_s(?P<start>\d{15})_e(?P<end>\d{15})_c(?P<create>\d{15}).nc'
      product_name:
        type: string
        value:
          from: "filename"
          regex: 'rtv-(?P<domain>\w+)-(?P<resolution>\w+)-(?P<product_name>[\w-]+)_v1r0_hfr_s(?P<start>\d{15})_e(?P<end>\d{15})_c(?P<create>\d{15}).nc'
```

## Dependencies
### Upstream
- NCCF radial files ingest team

### Downstream
- N/A

## Appendix
- N/A
