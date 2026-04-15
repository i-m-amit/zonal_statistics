# core/zonal_processor.py

import tempfile
from pathlib import Path

import exactextract
import geopandas as gdf
import pandas as pd

from state import (
    progress,
    raster_bytes,
    results,
    selected_indicators,
    status,
    vector_files,
)
from utils.file_handlers import save_vector_files


def run():
    if not raster_bytes.value or not vector_files.value:
        status.set("Missing raster or vector")
        return
    status.set("Calculating...")
    progress.set(0.3)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # save raster
            raster_path = tmp / "raster.tif"
            raster_path.write_bytes(raster_bytes.value)
            progress.set(0.5)

            # save and detect vector
            vector_path = save_vector_files(vector_files.value, tmp)
            progress.set(0.7)
            gdf_ = gdf.read_file(vector_path)
            status.set(f"Computing stats for {len(gdf_)} zones...")
            df = exactextract.exact_extract(
                str(raster_path),
                gdf_,
                selected_indicators.value,
                output="pandas",
                include_cols=gdf_.columns.drop("geometry", errors="ignore").tolist(),
                max_cells_in_memory=50_000_000,
            )
            assert isinstance(df, pd.DataFrame)
            # clean column names
            df.columns = [
                col.replace("(", "").replace(")", "").replace(" ", "_")
                for col in df.columns
            ]

            results.set(df)
            status.set("Completed")
            progress.set(1.0)

    except Exception as e:
        status.set(f"error: {str(e)}")
        results.set(None)
        progress.set(0.0)
