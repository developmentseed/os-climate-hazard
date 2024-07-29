cwlVersion: v1.2

class: CommandLineTool

hints:
  DockerRequirement:
    dockerPull: public.ecr.aws/c9k5s3u3/os-hazard-indicator:ukcp18compat

requirements:
  ResourceRequirement:
    coresMax: 2
    ramMax: 4096
  NetworkAccess:
    networkAccess: true
  EnvVarRequirement:
      envDef:
        OSC_S3_ACCESS_KEY_DEV: $(inputs.osc_s3_access_key_dev)
        OSC_S3_SECRET_KEY_DEV: $(inputs.osc_s3_secret_key_dev)
        OSC_S3_TOKEN_DEV: $(inputs.osc_s3_token_dev)
        CEDA_FTP_USERNAME: $(inputs.ceda_ftp_username)
        CEDA_FTP_URL: $(inputs.ceda_ftp_url)
        CEDA_FTP_PASSWORD: $(inputs.ceda_ftp_password)

inputs:
  ceda_ftp_username: string
  ceda_ftp_password: string
  ceda_ftp_url: string
  osc_s3_access_key_dev: string
  osc_s3_secret_key_dev: string
  osc_s3_token_dev: string
  source_dataset: string
  gcm_list: string
  scenario_list: string
  central_year_list: string
  central_year_historical: int
  window_years: int

outputs:
  indicator-results:
    type: Directory
    outputBinding:
      glob: "./indicator"

baseCommand: ["os_climate_hazard", "days_tas_above_indicator", "--store", "./indicator"]

arguments:
  - prefix: --source_dataset
    valueFrom: $(inputs.source_dataset)
  - prefix: --gcm_list
    valueFrom: $(inputs.gcm_list)
  - prefix: --scenario_list
    valueFrom: $(inputs.scenario_list)
  - prefix: --central_year_list
    valueFrom: $(inputs.central_year_list)
  - prefix: --central_year_historical
    valueFrom: $(inputs.central_year_historical)
  - prefix: --window_years
    valueFrom: $(inputs.window_years)
