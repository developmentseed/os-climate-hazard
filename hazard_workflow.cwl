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
        CEDA_FTP_USERNAME: $(inputs.ceda_ftp_username)
        CEDA_FTP_URL: $(inputs.ceda_ftp_url)
        CEDA_FTP_PASSWORD: $(inputs.ceda_ftp_password)

inputs:
  ceda_ftp_username:
    type: string
    default: ""
  ceda_ftp_password:
    type: string
    default: ""
  ceda_ftp_url:
    type: string
    default: ""
  source_dataset: string
  gcm_list: string
  scenario_list: string
  central_year_list: string
  central_year_historical: int
  window_years: int
  indicator:
    type: string
    default: "days_tas_above_indicator"
  store:
    type: string
    default: "./indicator"

outputs:
  indicator-results:
    type: Directory
    outputBinding:
      glob: "./indicator"

baseCommand: os_climate_hazard

arguments:
  - valueFrom: $(inputs.indicator)
  - prefix: --store
    valueFrom: $(inputs.store)
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
