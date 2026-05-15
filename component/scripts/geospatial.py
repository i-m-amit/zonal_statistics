import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
import geopandas as gpd
import matplotlib.cm as cm
import matplotlib.colors as colors
import rasterio
from ipyleaflet import GeoJSON
from pyproj import Transformer

from component.scripts.proj_util import Bounds
import logging

logger = logging.getLogger("zs.geospatial_utils")


def is_raster_file(file_path: str) -> bool:
    raster_extensions = {
        ".tif",
        ".tiff",
        ".img",
        ".vrt",
        ".asc",
        ".grd",
        ".ecw",
        ".jp2",
        ".sid",
    }
    return Path(file_path).suffix.lower() in raster_extensions


def is_vector_file(file_path: str) -> bool:
    vector_extensions = {
        ".shp",  # Shapefile
        ".geojson",  # GeoJSON
        ".json",  # JSON (may contain GeoJSON)
        ".gpkg",  # GeoPackage
        ".kml",  # Keyhole Markup Language
        ".kmz",  # Compressed KML
        ".gml",  # Geography Markup Language
        ".gpx",  # GPS Exchange Format
        ".fgb",  # FlatGeobuf
        ".csv",  # CSV (with geometry column)
        ".tab",  # MapInfo TAB
        ".mif",  # MapInfo Interchange Format
        ".dwg",  # AutoCAD DWG
        ".sqlite",  # SpatiaLite
        ".db",  # SpatiaLite (alternate extension)
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
                info.update(
                    {
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
                    }
                )
        elif is_vector_file(file_path):
            gdf = gpd.read_file(file_path)
            info.update(
                {
                    "file_type": "vector",
                    "crs": str(gdf.crs) if gdf.crs else None,
                    "bounds": list(gdf.total_bounds),
                    "feature_count": len(gdf),
                    "geometry_type": gdf.geom_type.unique().tolist(),
                    "columns": gdf.columns.drop("geometry").tolist(),
                }
            )
        else:
            info["error"] = f"Unsupported file type: {path.suffix}"

    except Exception as e:
        info["error"] = str(e)

    return info


def get_bounds_in_wgs84(file_info: Dict) -> Bounds:
    """Takes a bound and crs and returns bounds in WGS84"""
    crs_str = file_info.get("crs")
    _bounds = file_info.get("bounds")
    if crs_str and _bounds:
        if "4326" not in crs_str:
            transformer = Transformer.from_crs(crs_str, "EPSG:4326", always_xy=True)
            lon_min, lat_min = transformer.transform(_bounds[0], _bounds[1])
            lon_max, lat_max = transformer.transform(_bounds[2], _bounds[3])
        else:
            lon_min, lat_min, lon_max, lat_max = (
                _bounds[0],
                _bounds[1],
                _bounds[2],
                _bounds[3],
            )
        return Bounds(
            min_lon=lon_min, max_lon=lon_max, min_lat=lat_min, max_lat=lat_max
        )
    else:
        return Bounds(min_lon=-180, max_lon=180, min_lat=-90, max_lat=90)


def gdf_to_geojson_layer(
    gdf: gpd.GeoDataFrame,
    column: Optional[str] = None,
    layer_name: str = "Vector",
    cmap_name: str = "inferno",
    fill_opacity: float = 0.75,
) -> GeoJSON:
    """
    Convert GeoDataFrame to ipyleaflet GeoJSON layer.

    Parameters:
        gdf: GeoDataFrame
        column: Column to use for coloring and hover info.
                If None → simple uniform styling (no coloring).
        layer_name: Name of the layer to display
        cmap_name: matplotlib cmap
        fill_opacity: transperency
    """

    # Reproject if needed
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Select columns for GeoJSON
    if column and column in gdf.columns:
        geojson_gdf = gdf[[column, "geometry"]]
    else:
        geojson_gdf = gdf[["geometry"]]
    geojson_str = geojson_gdf.to_json()
    if not geojson_str:
        raise ValueError("GeoDataFrame serialization returned None or empty string")

    geojson_dict = json.loads(geojson_str)

    def style_callback(feature: dict) -> dict:
        if not column:
            return {
                "color": "#333333",
                "weight": 1.5,
                "fillColor": "#1f78b4",
                "fillOpacity": fill_opacity,
            }

        val = feature["properties"].get(column)
        if val is None or pd.isna(val):
            return {
                "color": "#666666",
                "weight": 1,
                "fillColor": "#cccccc",
                "fillOpacity": 0.5,
            }

        try:
            values = gdf[column].dropna().to_numpy()
            vmin, vmax = float(values.min()), float(values.max())
            norm = colors.Normalize(vmin=vmin, vmax=vmax)
            cmap = cm.get_cmap(cmap_name)
            hex_color = colors.to_hex(cmap(norm(float(val))))
        except Exception:
            hex_color = "#21908c"

        return {
            "color": "#333333",
            "weight": 1,
            "fillColor": hex_color,
            "fillOpacity": fill_opacity,
        }

    layer = GeoJSON(
        data=geojson_dict,
        name=layer_name,
        style={"color": "#333", "weight": 1.2},
        style_callback=style_callback,
        hover_style={"weight": 3, "color": "yellow", "fillOpacity": 0.9},
    )

    logger.info(
        f"Created GeoJSON layer '{layer_name}' {'with' if column else 'without'} column coloring"
    )
    return layer
