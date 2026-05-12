"""Results display and export component"""

import logging
from pathlib import Path

import geopandas as gpd
import solara
import pandas as pd
from ipyleaflet import GeoJSON
from component.model import app_state
from component.widget.map import ZsMap
from component.scripts.geospatial import gdf_to_geojson_layer

logger = logging.getLogger("zs.results")


EXPORT_DIR: Path = Path.home() / "module_results" / "zonal_statistics"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def export_csv(df: pd.DataFrame) -> Path:
    csv_path: Path = EXPORT_DIR / "zonal_statistics.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


def export_geojson(gdf: gpd.GeoDataFrame) -> Path:
    geojson_path: Path = EXPORT_DIR / "zonal_statistics.geojson"
    gdf.to_file(geojson_path, driver="GeoJSON")
    return geojson_path


def export_shapefile(gdf: gpd.GeoDataFrame) -> Path:
    shp_dir: Path = EXPORT_DIR / "shapefile"
    shp_dir.mkdir(parents=True, exist_ok=True)
    shp_path: Path = shp_dir / "zonal_statistics.shp"
    gdf.to_file(shp_path)
    return shp_path


def download_file(file_path: Path) -> None:
    """Trigger file download"""
    logger.info(f"Exporting file: {file_path}")
    # For Solara, use solara.download or serve files via HTTP to download direct to your local computer
    solara.Info(f"File exported to: {file_path}")


@solara.component  # type: ignore
def ResultsTile(map_widget: ZsMap):
    """Panel for displaying and exporting results"""

    # Local state for column selection
    selected_column = solara.use_reactive("mean")

    with solara.Column(gap="20px"):
        if app_state.zonal_results.value is None:
            with solara.Info("No results available"):
                solara.Markdown("""
                Run zonal statistics from the **Zonal Statistics** tab to generate results.
                """)
            return

        if isinstance(app_state.results_gdf_modified.value, gpd.GeoDataFrame):
            gdf = app_state.results_gdf_modified.value
        else:
            gdf = app_state.results_gdf.value

        if isinstance(gdf, gpd.GeoDataFrame):
            df = pd.DataFrame(gdf.drop(columns="geometry"))
        else:
            df = None

        # Column selector for map visualization
        if gdf is not None and "geometry" in gdf.columns and df is not None:
            with solara.Card("Map Visualization", elevation=2):
                stat_columns = [
                    c for c in df.columns if c.startswith(app_state.stat_column.value)
                ]

                if stat_columns:
                    solara.Markdown("**Select column to visualize:**")

                    solara.Select(
                        label="Statistics Column",
                        value=selected_column.value
                        if selected_column.value in stat_columns
                        else stat_columns[0],
                        values=stat_columns,
                        on_value=selected_column.set,
                    )

                    def update_map():
                        try:
                            if selected_column.value not in stat_columns:
                                return

                            logger.info(
                                f"Updating map with column: {selected_column.value}"
                            )

                            # Remove previous zonal layer first
                            for lyr in list(map_widget.layers):
                                if (
                                    isinstance(lyr, GeoJSON)
                                    and getattr(lyr, "name", None) == "Zonal Results"
                                ):
                                    map_widget.remove_layer(lyr)

                            # Create and add the new layer (do NOT add it again here)
                            layer = gdf_to_geojson_layer(
                                gdf=gdf,
                                column=selected_column.value,
                                layer_name="Zonal Results",
                            )

                            map_widget.add_layer(layer)

                        except Exception as e:
                            logger.error(f"Error updating map: {e}", exc_info=True)
                            solara.Error(f"Failed to update map: {e}")

                    solara.Button(
                        label="Update Map", on_click=update_map, color="primary"
                    )

            # Data table display
        if df is not None:
            with solara.Card("Results Table", elevation=2):
                solara.Markdown("**Preview of results** (showing first 100 rows)")

                # Display DataFrame
                display_df = df.head(100)
                solara.DataFrame(display_df, items_per_page=20)

            # Statistics summary
            with solara.Card("Statistics Summary", elevation=2):
                stat_columns = [
                    c for c in df.columns if c.startswith(app_state.stat_column.value)
                ]

                if stat_columns:
                    summary_df = df[stat_columns].describe()
                    solara.Markdown("**Summary statistics across all zones:**")
                    solara.DataFrame(summary_df)

            # Export options
            with solara.Card("Export Results", elevation=2):
                solara.Markdown("**Download results in various formats:**")

                with solara.Row():
                    if df is not None:
                        solara.Button(
                            label="📄 Export CSV",
                            on_click=lambda: download_file(export_csv(df)),
                            color="primary",
                            outlined=True,
                        )

                    # GeoJSON export (if geometry exists)
                    if gdf is not None and "geometry" in gdf.columns:
                        solara.Button(
                            label="🗺️ Export GeoJSON",
                            on_click=lambda: download_file(export_geojson(gdf)),
                            color="success",
                            outlined=True,
                        )

                        # Shapefile export

                        solara.Button(
                            label="📦 Export Shapefile",
                            on_click=lambda: download_file(export_shapefile(gdf)),
                            color="info",
                            outlined=True,
                        )

                solara.Markdown("""
                *Files will be saved to your downloads folder*
                """)
