"""Zonal statistics processor using exactextract"""

import logging
from typing import List, Optional

import geopandas as gpd
import rasterio
from exactextract import exact_extract
import pandas as pd
import numpy as np

logger = logging.getLogger("zonal_stats_app.processor")

__all__ = ["run_zonal_statistics"]

def run_zonal_statistics(
    raster_path: str,
    vector_path: Optional[str],
    target_crs: Optional[str],
    statistics: List[str],
    column_prefix: str = "value"
) -> gpd.GeoDataFrame:
    """
    Run zonal statistics using exactextract

    Args:
        raster_path: Path to raster file
        vector_path: Path to vector file (optional)
        target_crs: Target CRS for reprojection (optional)
        statistics: List of statistics to calculate
        column_prefix: Prefix for output columns

    Returns:
        GeoDataFrame with statistics results
    """

    logger.info(f"Starting zonal statistics: {raster_path}")
    logger.info(f"Statistics: {statistics}")

    # Load raster
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        raster_bounds = src.bounds
        logger.info(f"Raster CRS: {raster_crs}, Shape: {src.shape}")

    # Load or create vector
    if vector_path:
        logger.info(f"Loading vector from: {vector_path}")
        gdf = gpd.read_file(vector_path)
        logger.info(f"Loaded {len(gdf)} features")
    else:
        # Create a single polygon covering the raster extent
        logger.info("No vector provided, using raster extent")
        from shapely.geometry import box
        geom = box(raster_bounds.left, raster_bounds.bottom,
                   raster_bounds.right, raster_bounds.top)
        gdf = gpd.GeoDataFrame([{"id": 1, "geometry": geom}], crs=raster_crs)
        logger.info("Created single zone from raster extent")

    # Reproject vector if needed
    if target_crs:
        logger.info(f"Reprojecting to: {target_crs}")
        gdf = gdf.to_crs(target_crs)
        # Also need to reproject raster - we'll handle this in exactextract
    elif gdf.crs != raster_crs:
        logger.info(f"Reprojecting vector from {gdf.crs} to {raster_crs}")
        gdf = gdf.to_crs(raster_crs)

    #Column names to keep
    if not gdf.empty:
        column_names = list(gdf.drop(columns='geometry').columns)
    # Map statistics names to exactextract format
    stat_mapping = {
        'mean': 'mean',
        'sum': 'sum',
        'count': 'count',
        'min': 'min',
        'max': 'max',
        'median': 'median',
        'std': 'stdev',
        'variance': 'variance',
        'coefficient_of_variation': 'coefficient_of_variation',
        'majority': 'majority',
        'minority': 'minority',
        'variety': 'variety',
    }

    # Build stats list for exactextract
    exact_stats = []
    for stat in statistics:
        if stat in stat_mapping:
            exact_stats.append(stat_mapping[stat])
        else:
            logger.warning(f"Unknown statistic: {stat}")

    logger.info(f"Running exactextract with stats: {exact_stats}")

    try:
        # Run exact_extract
        # exactextract returns a list of dictionaries, one per feature
        results = exact_extract(
            raster_path,
            gdf,
            exact_stats,
            include_cols=column_names,  # Include original columns
            output='pandas'
        )

        logger.info(f"exactextract completed, {len(results)} zones processed")

        # Create output GeoDataFrame
        # Merge results with original geometries
        result_gdf = gdf.copy()

        # Add statistics columns
        for stat in exact_stats:
            if stat in results.columns:
                result_gdf[f"{column_prefix}_{stat}"] = results[stat].values

        # Add zone IDs if not present
        if 'zone_id' not in result_gdf.columns:
            result_gdf['zone_id'] = range(len(result_gdf))

        logger.info(f"Results shape: {result_gdf.shape}")
        logger.info(f"Columns: {result_gdf.columns.tolist()}")

        return result_gdf

    except Exception as e:
        logger.error(f"Error in exact_extract: {e}", exc_info=True)
        raise Exception(f"Zonal statistics failed: {str(e)}")
