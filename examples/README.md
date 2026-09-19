# Examples

End-to-end workflows by persona. Each script runs with no arguments (the defaults are a real
place and date), writes to `./output/<example>/`, and reuses its downloads on a second run.
The [use-cases page](https://vtvito.github.io/cdse-client/use-cases/) explains each one and
its limits.

| Example | Persona | What you get | Install |
|---|---|---|---|
| [`agri_ndvi_timeseries.py`](agri_ndvi_timeseries.py) | Agronomist | Cloud-screened NDVI curve for one field over a season (CSV + plot) | `pip install "cdse-client[processing]" matplotlib` |
| [`wildfire_dnbr.py`](wildfire_dnbr.py) | Civil protection / GIS analyst | dNBR and burn-severity GeoTIFFs, severity map with hectares per class, before/after previews | `pip install "cdse-client[processing]"` |
| [`s1_pre_post_pairs.py`](s1_pre_post_pairs.py) | Emergency analyst (floods) | Sentinel-1 GRD pairs from the same track before and after an event (CSV + GeoJSON), optional download | `pip install "cdse-client[geo]"` |
| [`city_before_after.py`](city_before_after.py) | Journalist, educator, planner | True-colour views of a city at two dates, side by side, plus an optional NDVI/NDWI change map | `pip install "cdse-client[processing]" matplotlib` |
| [`s5p_no2_monthly.py`](s5p_no2_monthly.py) | Air-quality analyst | Monthly mean tropospheric NO2 GeoTIFF and map from Sentinel-5P | `pip install "cdse-client[processing]" xarray netCDF4` |

These scripts were tested offline with synthetic products, not yet against the live API.
Most of them download full products (about 1 GB each for Sentinel-1 and Sentinel-2), so read
the "Where the library stops" section of each script's docstring before running it.

## Basics

- `quickstart_search_download.py`: search + download (sync)
- `async_download.py`: async search + concurrent downloads
- `processing_preview.py`: generate a preview image

All examples expect `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET` to be set.
