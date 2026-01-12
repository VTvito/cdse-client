# GitHub Repository Setup

Copy and paste these settings into your GitHub repository.

## Repository Description

```
Python client for Copernicus Data Space Ecosystem (CDSE) - Modern replacement for sentinelsat with support for Sentinel-1/2/3/5P data
```

## Website URL

```
https://vtvito.github.io/cdse-client/
```

## Topics (GitHub Tags)

Add these topics to your repository (Settings → General → Topics):

```
copernicus
sentinel
satellite-imagery
earth-observation
remote-sensing
sentinel-2
sentinel-1
cdse
stac
geospatial
python
eo-data
earth-engine
satellite-data
copernicus-data
sentinelsat
data-download
gis
geospatial-analysis
open-data
```

## Social Media Description

**For Twitter/X, LinkedIn, etc.:**

🛰️ Just released cdse-client v0.3.0 - A modern Python library for downloading Copernicus Sentinel satellite data!

✨ Features:
• Drop-in replacement for sentinelsat
• Support for Sentinel-1/2/3/5P
• STAC API search
• Async downloads
• Processing utilities (NDVI, crop, stack)
• CLI tools

🔗 https://github.com/VTvito/cdse-client
📦 pip install cdse-client

#Python #RemoteSensing #EarthObservation #Copernicus #GIS

---

## README Badge Suggestions

Add these badges to the top of your README.md (after the existing badges):

```markdown
[![Downloads](https://static.pepy.tech/badge/cdse-client)](https://pepy.tech/project/cdse-client)
[![Downloads/Month](https://static.pepy.tech/badge/cdse-client/month)](https://pepy.tech/project/cdse-client)
[![GitHub stars](https://img.shields.io/github/stars/VTvito/cdse-client?style=social)](https://github.com/VTvito/cdse-client/stargazers)
[![Documentation Status](https://readthedocs.org/projects/cdse-client/badge/?version=latest)](https://cdse-client.readthedocs.io/en/latest/?badge=latest)
```

---

## How to Set These Up

### 1. Repository Description & Website
1. Go to https://github.com/VTvito/cdse-client
2. Click **Settings** (gear icon at top right of the repo page)
3. Under **General** → **Description**, paste the description
4. Under **Website**, paste: `https://vtvito.github.io/cdse-client/`
5. Click **Save changes**

### 2. Topics
1. On the main repository page, click **Add topics** (next to About)
2. Copy the topics list above and paste them one by one
3. Press Enter after each topic

### 3. Enable GitHub Pages
1. Go to **Settings** → **Pages**
2. Under **Source**, select **GitHub Actions**
3. Save

### 4. Enable Discussions (Optional but Recommended)
1. Go to **Settings** → **General**
2. Scroll to **Features**
3. Check ✅ **Discussions**
4. This allows users to ask questions and share use cases

---

## Marketing Checklist

- [ ] Post on Twitter/X with hashtags
- [ ] Post on LinkedIn (tag Copernicus, ESA)
- [ ] Submit to:
  - [ ] [PyPI Trending](https://pypi.org/project/cdse-client/)
  - [ ] [awesome-python](https://github.com/vinta/awesome-python) (create PR)
  - [ ] [awesome-geospatial](https://github.com/sacridini/Awesome-Geospatial) (create PR)
  - [ ] [awesome-earthobservation-code](https://github.com/acgeospatial/awesome-earthobservation-code)
  - [ ] Reddit r/Python, r/gis, r/eo
- [ ] Write blog post or tutorial
- [ ] Create YouTube demo video
- [ ] Add example notebooks to repository

---

## SEO Keywords for PyPI

Already in pyproject.toml, but here's the full list for reference:

```python
keywords = [
    "copernicus",
    "sentinel",
    "satellite",
    "remote-sensing",
    "earth-observation",
    "CDSE",
    "STAC",
    "sentinelsat"
]
```

---

## GitHub Release Notes Template (for v0.3.0)

```markdown
# 🚀 cdse-client v0.3.0

First production release of cdse-client - a modern Python client for Copernicus Data Space Ecosystem.

## 🎯 Overview

`cdse-client` is a drop-in replacement for the deprecated `sentinelsat` library, providing access to Sentinel-1/2/3/5P satellite data through the new CDSE infrastructure.

## ✨ Features

- **Search & Download**: STAC API search with flexible filters (bbox, date, cloud cover, etc.)
- **Collections**: Support for Sentinel-1 GRD, Sentinel-2 L1C/L2A, Sentinel-3 OLCI/SLSTR, Sentinel-5P L2
- **Export Formats**: DataFrame, GeoJSON, GeoDataFrame (sentinelsat compatible)
- **Processing**: Band extraction, cropping, stacking, NDVI calculation, preview generation
- **Async Support**: High-performance concurrent downloads with aiohttp
- **CLI Tools**: Command-line interface for search and download operations
- **Geocoding**: Search by city name with built-in bbox lookup
- **Type Safety**: Full type hints and py.typed marker

## 📦 Installation

```bash
pip install cdse-client              # Core functionality
pip install cdse-client[all]         # Everything included
```

## 🔧 Quick Start

```python
from cdse import CDSEClient

client = CDSEClient(client_id="...", client_secret="...")

# Search Sentinel-2 data
products = client.search(
    bbox=[9.0, 45.0, 9.5, 45.5],
    start_date="2024-01-01",
    end_date="2024-01-31",
    collection="sentinel-2-l2a",
    cloud_cover_max=20
)

# Download
for product in products:
    client.download(product)
```

## 📚 Documentation

- **Docs**: https://vtvito.github.io/cdse-client/
- **PyPI**: https://pypi.org/project/cdse-client/
- **GitHub**: https://github.com/VTvito/cdse-client

## 🙏 Acknowledgments

This library provides unofficial client access to:
- Copernicus Data Space Ecosystem (CDSE)
- European Space Agency (ESA) data
- European Commission Copernicus Programme

Data is provided under free, full, and open data policy.

## 📄 License

MIT License - See [LICENSE](LICENSE)

---

**Full Changelog**: https://github.com/VTvito/cdse-client/compare/v0.1.0...v0.3.0
```

---

## Example Use Cases for README/Docs

Add these examples to show practical applications:

### 🌾 Agriculture Monitoring
```python
# Monitor crop health with NDVI
from cdse import CDSEClient
from cdse.processing import calculate_ndvi, crop_and_stack

client = CDSEClient()
products = client.search_by_city("Mantova, Italia", collection="sentinel-2-l2a")

for product in products[:1]:
    client.download(product)
    # Extract and process bands
    result = crop_and_stack(
        product.name + ".zip",
        bbox=[...],
        bands=["B08", "B04"]  # NIR and Red
    )
    ndvi = calculate_ndvi(nir_path="B08.tif", red_path="B04.tif")
```

### 🌊 Water Body Detection
```python
# Track water bodies over time
products = client.search(
    bbox=[12.0, 45.0, 13.0, 46.0],
    collection="sentinel-2-l2a",
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

### 🏙️ Urban Growth Analysis
```python
# Monitor urban expansion
products = client.search_by_city(
    "Milano, Italia",
    collection="sentinel-2-l2a",
    buffer_km=20
)

df = client.to_dataframe(products)
df.sort_values('datetime').to_csv('milano_imagery.csv')
```

