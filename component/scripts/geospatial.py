import os
import tempfile
from pathlib import Path
from typing import Dict, Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import xy

def is_raster_file(file_path: str) -> bool:
    raster_extensions = {
        '.tif', '.tiff',
        '.img',
        '.vrt',
        '.asc',
        '.grd',
        '.ecw',
        '.jp2',
        '.sid',
    }
    return Path(file_path).suffix.lower() in raster_extensions

def is_vector_file(file_path: str) -> bool:
    vector_extensions = {
        '.shp',            # Shapefile
        '.geojson',        # GeoJSON
        '.json',           # JSON (may contain GeoJSON)
        '.gpkg',           # GeoPackage
        '.kml',            # Keyhole Markup Language
        '.kmz',            # Compressed KML
        '.gml',            # Geography Markup Language
        '.gpx',            # GPS Exchange Format
        '.fgb',            # FlatGeobuf
        '.csv',            # CSV (with geometry column)
        '.tab',            # MapInfo TAB
        '.mif',            # MapInfo Interchange Format
        '.dwg',            # AutoCAD DWG
        '.sqlite',         # SpatiaLite
        '.db',             # SpatiaLite (alternate extension)
    }
    return Path(file_path).suffix.lower() in vector_extensions

def save_uploaded_file(file_info, temp_dir: Optional[str] = None) -> str:
    """Save uploaded file to temporary directory.

    Args:
        file_info: FileInfo object from Solara FileDrop
        temp_dir: Optional temporary directory (created if None)

    Returns:
        Path to saved file
    """
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()

    file_path = os.path.join(temp_dir, file_info["name"])

    with open(file_path, "wb") as f:
        file_info["file_obj"].seek(0)
        f.write(file_info["file_obj"].read())

    return file_path


def get_file_info(file_path: str) -> Dict:
    """Get basic information about a geospatial file.
    Args:
        file_path: Path to file
    Returns:
        Dictionary with file information
    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If path is not a file
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    info = {
        "file_name": path.name,
        "file_type": "unknown",
        "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
        "crs": None,
        "bounds": None,
        "feature_count": 0,
        "error": None,
    }

    try:
        if is_raster_file(file_path):
            with rasterio.open(file_path) as raster:
                info.update({
                    "file_type": "raster",
                    "crs": str(raster.crs) if raster.crs else None,
                    "bounds": list(raster.bounds),
                    "width": raster.width,
                    "height": raster.height,
                    "band_count": raster.count,
                    "dtype": str(raster.dtypes[0]),
                    "nodata": raster.nodata,
                    "resolution": raster.res,
                    "feature_count": raster.width * raster.height,
                })
        elif is_vector_file(file_path):
            gdf = gpd.read_file(file_path)
            info.update({
                "file_type": "vector",
                "crs": str(gdf.crs) if gdf.crs else None,
                "bounds": list(gdf.total_bounds),
                "feature_count": len(gdf),
                "geometry_type": gdf.geom_type.unique().tolist(),
                "columns": gdf.columns.drop("geometry").tolist(),
            })
        else:
            info["error"] = f"Unsupported file type: {path.suffix}"

    except Exception as e:
        info["error"] = str(e)

    return info
