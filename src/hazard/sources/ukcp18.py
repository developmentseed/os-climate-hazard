import io
import logging
import os
import re
from contextlib import contextmanager
from typing import Dict, Generator, List, Optional

import fsspec
import rasterio
import xarray as xr
from rasterio import CRS

from hazard.protocols import OpenDataset

_UKCP18_2_2km_ROTATED_POLES = """
GEOGCRS["Rotated_pole",
    BASEGEOGCRS["unknown",
        DATUM["unnamed",
            ELLIPSOID["Sphere",6371229,0,
                LENGTHUNIT["metre",1,
                    ID["EPSG",9001]]]],
        PRIMEM["Greenwich",0,
            ANGLEUNIT["degree",0.0174532925199433,
                ID["EPSG",9122]]]],
    DERIVINGCONVERSION["Pole rotation (netCDF CF convention)",
        METHOD["Pole rotation (netCDF CF convention)"],
        PARAMETER["Grid north pole latitude (netCDF CF convention)",37.5,
            ANGLEUNIT["degree",0.0174532925199433,
                ID["EPSG",9122]]],
        PARAMETER["Grid north pole longitude (netCDF CF convention)",177.5,
            ANGLEUNIT["degree",0.0174532925199433,
                ID["EPSG",9122]]],
        PARAMETER["North pole grid longitude (netCDF CF convention)",0,
            ANGLEUNIT["degree",0.0174532925199433,
                ID["EPSG",9122]]]],
    CS[ellipsoidal,2],
        AXIS["latitude",north,
            ORDER[1],
            ANGLEUNIT["degree",0.0174532925199433,
                ID["EPSG",9122]]],
        AXIS["longitude",east,
            ORDER[2],
            ANGLEUNIT["degree",0.0174532925199433,
                ID["EPSG",9122]]]]
            """
_BRITISH_NATIONAL_GRID = "EPSG:27700"
_WGS84 = "EPSG:4326"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Ukcp18(OpenDataset):
    def __init__(
        self,
        dataset_member_id: str = "01",
        dataset_frequency: str = "day",
        dataset_version: str = "latest",
        collection: str = "land-rcm",
        domain: str = "uk",
        resolution: str = "12km",
    ):
        self._fs = fsspec.filesystem(
            protocol="ftp",
            host=os.environ["CEDA_FTP_URL"],
            username=os.environ["CEDA_FTP_USERNAME"],
            password=os.environ["CEDA_FTP_PASSWORD"],
        )
        self.quantities: Dict[str, Dict[str, str]] = {
            "tas": {"name": "Daily average temperature"}
        }

        # Refer to https://www.metoffice.gov.uk/binaries/content/assets/metofficegovuk/pdf/research/ukcp/ukcp18-guidance-data-availability-access-and-formats.pdf on what these values refer to # noqa
        self._dataset_member_id = dataset_member_id
        self._dataset_frequency = dataset_frequency
        self._dataset_version = dataset_version

        self._collection = collection
        self._domain = domain
        self._resolution = resolution

    def gcms(self) -> List[str]:
        return list("ukcp18")

    @contextmanager
    def open_dataset_year(
        self,
        gcm: str = "ukcp18",
        scenario: str = "rcp85",
        quantity: str = "tas",
        year: int = 1981,
        chunks=None,
        catalog_url: Optional[str] = None,
        collection_id: Optional[str] = None,  # type: ignore
    ) -> Generator[xr.Dataset, None, None]:
        files_available_for_quantity: List[str] = (
            self._get_files_available_for_quantity_and_year(
                gcm, scenario, quantity, year
            )
        )

        if not files_available_for_quantity:
            raise Exception(
                f"No UKCP18 files available for: gcm:{gcm}, scenario:{scenario}, quantity:{quantity}, year:{year}"
            )

        all_data_from_files = self._combine_all_files_data(files_available_for_quantity)
        only_data_for_year = all_data_from_files.sel(time=str(year))
        reprojected = self._reproject_quantity(only_data_for_year, quantity)
        converted_to_kelvin = self._convert_to_kelvin(reprojected, quantity)

        yield converted_to_kelvin

    def _combine_all_files_data(
        self, files_available_for_quantity: List[str]
    ) -> xr.Dataset:
        datasets = []
        for file in files_available_for_quantity:
            with self._fs.open(file, "rb") as f:
                with io.BytesIO(f.read()) as file_in_memory:
                    file_in_memory.seek(0)
                    datasets.append(xr.open_dataset(file_in_memory).load())
        return xr.combine_by_coords(datasets, combine_attrs="override")  # type: ignore[return-value]

    def _get_files_available_for_quantity_and_year(
        self, gcm: str, scenario: str, quantity: str, year: int
    ) -> List[str]:
        ftp_url = (
            f"/badc/{gcm}/data/{self._collection}/{self._domain}/{self._resolution}/{scenario}/{self._dataset_member_id}/{quantity}"
            f"/{self._dataset_frequency}/{self._dataset_version}/"
        )
        all_files = self._fs.ls(ftp_url, detail=False)
        files_that_contain_year = []
        start_end_date_regex = re.compile(r"_(\d{8})-(\d{8})\.nc")
        for file in all_files:
            matches = start_end_date_regex.search(file)
            if matches:
                start_date = int(matches.group(1)[:4])
                end_date = int(matches.group(2)[:4])
                if start_date <= year <= end_date:
                    files_that_contain_year.append(f"{ftp_url}{file}")
        return files_that_contain_year

    def _prepare_data_array(
        self, data_array: xr.DataArray, crs: str | CRS, drop_vars: List[str]
    ) -> xr.DataArray:
        squeezed = data_array.squeeze()
        dropped_vars = squeezed.drop_vars(drop_vars, errors="ignore")
        dropped_vars.attrs.pop("grid_mapping", None)
        return dropped_vars.rio.write_crs(crs)

    def _reproject_and_rename_coordinates(
        self,
        data_array: xr.DataArray,
        target_crs: str,
        to_rename_to_lon: str,
        to_rename_to_lat: str,
    ) -> xr.DataArray:
        reprojected = data_array.rio.reproject(target_crs)
        return reprojected.rename({to_rename_to_lon: "lon", to_rename_to_lat: "lat"})

    def _reproject_quantity(self, dataset: xr.Dataset, quantity: str) -> xr.Dataset:
        if self._domain == "uk" and self._resolution in ["5km", "12km", "60km"]:
            prepped_data_array = self._prepare_data_array(
                dataset[quantity],
                _BRITISH_NATIONAL_GRID,
                ["latitude", "longitude", "grid_latitude", "grid_longitude"],
            )
            dataset[quantity] = self._reproject_and_rename_coordinates(
                prepped_data_array, _WGS84, "x", "y"
            )
        elif self._domain == "uk" and self._resolution == "2.2km":
            prepped_data_array = self._prepare_data_array(
                dataset[quantity],
                rasterio.CRS.from_wkt(_UKCP18_2_2km_ROTATED_POLES),
                drop_vars=["latitude", "longitude"],
            )
            prepped_data_array.rio.set_spatial_dims(
                "grid_longitude", "grid_latitude", inplace=True
            )
            dataset[quantity] = self._reproject_and_rename_coordinates(
                prepped_data_array, _WGS84, "x", "y"
            )
        elif self._domain == "global" and self._resolution == "60km":
            prepped_data_array = self._prepare_data_array(dataset[quantity], _WGS84, [])
            dataset[quantity] = prepped_data_array.rename(
                {"longitude": "lon", "latitude": "lat"}
            )
        else:
            logger.warning(
                "Didn't find a matching domain and resolution for reprojecting the dataset, returning it untouched"
            )
        return dataset

    def _convert_to_kelvin(self, dataset: xr.Dataset, quantity: str) -> xr.Dataset:
        quantity_data = dataset[quantity]
        converted = quantity_data + 273.15
        converted.attrs["units"] = "K"
        converted.attrs["label_units"] = "K"
        converted.attrs["plot_label"] = "Mean air temperature at 1.5m (K)"
        dataset[quantity] = converted
        return dataset
