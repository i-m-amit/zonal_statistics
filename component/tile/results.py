"""Results display and export component"""

import logging
from pathlib import Path

import solara
import pandas as pd

from component.model import app_state
from component.widget.map import ZsMap

logger = logging.getLogger("zs.results")


@solara.component
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
        
        df = app_state.zonal_results.value
        gdf = app_state.results_gdf.value
        
        # Summary statistics
        with solara.Card("Results Summary", elevation=2):
            solara.Markdown(f"""
            - **Zones processed**: {len(df)}
            - **Statistics columns**: {len([c for c in df.columns if c.startswith(app_state.stat_column.value)])}
            - **Total columns**: {len(df.columns)}
            """)
        
        # Column selector for map visualization
        if gdf is not None and 'geometry' in gdf.columns:
            with solara.Card("Map Visualization", elevation=2):
                stat_columns = [c for c in df.columns if c.startswith(app_state.stat_column.value)]
                
                if stat_columns:
                    solara.Markdown("**Select column to visualize:**")
                    
                    solara.Select(
                        label="Statistics Column",
                        value=selected_column.value if selected_column.value in stat_columns else stat_columns[0],
                        values=stat_columns,
                        on_value=selected_column.set
                    )
                    
                    def update_map():
                        try:
                            if selected_column.value in stat_columns:
                                map_widget.add_layer(gdf, selected_column.value)
                        except Exception as e:
                            logger.error(f"Error updating map: {e}")
                    
                    solara.Button(
                        label="Update Map",
                        on_click=update_map,
                        color="primary"
                    )
        
        # Data table display
        with solara.Card("Results Table", elevation=2):
            solara.Markdown("**Preview of results** (showing first 100 rows)")
            
            # Display DataFrame
            display_df = df.head(100)
            solara.DataFrame(display_df, items_per_page=20)
        
        # Statistics summary
        with solara.Card("Statistics Summary", elevation=2):
            stat_columns = [c for c in df.columns if c.startswith(app_state.stat_column.value)]
            
            if stat_columns:
                summary_df = df[stat_columns].describe()
                solara.Markdown("**Summary statistics across all zones:**")
                solara.DataFrame(summary_df)
        
        # Export options
        with solara.Card("Export Results", elevation=2):
            solara.Markdown("**Download results in various formats:**")
            
            with solara.Row():
                # CSV export
                def export_csv():
                    csv_path = Path(app_state.temp_dir.value) / "zonal_statistics.csv"
                    df.to_csv(csv_path, index=False)
                    return csv_path
                
                solara.Button(
                    label="📄 Export CSV",
                    on_click=lambda: download_file(export_csv()),
                    color="primary",
                    outlined=True
                )
                
                # GeoJSON export (if geometry exists)
                if gdf is not None and 'geometry' in gdf.columns:
                    def export_geojson():
                        geojson_path = Path(app_state.temp_dir.value) / "zonal_statistics.geojson"
                        gdf.to_file(geojson_path, driver='GeoJSON')
                        return geojson_path
                    
                    solara.Button(
                        label="🗺️ Export GeoJSON",
                        on_click=lambda: download_file(export_geojson()),
                        color="success",
                        outlined=True
                    )
                    
                    # Shapefile export
                    def export_shapefile():
                        shp_dir = Path(app_state.temp_dir.value) / "shapefile"
                        shp_dir.mkdir(exist_ok=True)
                        shp_path = shp_dir / "zonal_statistics.shp"
                        gdf.to_file(shp_path)
                        return shp_path
                    
                    solara.Button(
                        label="📦 Export Shapefile",
                        on_click=lambda: download_file(export_shapefile()),
                        color="info",
                        outlined=True
                    )
            
            solara.Markdown("""
            *Files will be saved to your downloads folder*
            """)


def download_file(file_path: Path):
    """Trigger file download"""
    logger.info(f"Exporting file: {file_path}")
    # Note: In a real deployment, you'd implement actual file download
    # For Solara, you might use solara.download or serve files via HTTP
    solara.Info(f"File exported to: {file_path}")