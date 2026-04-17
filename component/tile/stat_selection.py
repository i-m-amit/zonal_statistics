"""Zonal statistics configuration and execution component"""

import logging

import solara

from component.model import app_state
from component.scripts.processor import run_zonal_statistics

logger = logging.getLogger("zs.zonal_stats")


AVAILABLE_STATISTICS = [
    ("mean", "Mean", "Average value within each zone"),
    ("sum", "Sum", "Total sum of all values"),
    ("count", "Count", "Number of pixels/cells"),
    ("min", "Minimum", "Minimum value"),
    ("max", "Maximum", "Maximum value"),
    ("median", "Median", "Median value"),
    ("std", "Standard Deviation", "Standard deviation"),
    ("variance", "Variance", "Variance"),
    ("coefficient_of_variation", "Coefficient of Variation", "Std dev / mean"),
    ("majority", "Majority", "Most common value (categorical)"),
    ("minority", "Minority", "Least common value (categorical)"),
    ("variety", "Variety", "Number of unique values"),
]


@solara.component #type: ignore
def StatsSelectionTile():
    """Panel for configuring and running zonal statistics"""

    # Local state
    is_processing = solara.use_reactive(False)

    with solara.Column(gap="20px"):
        # Prerequisites check
        with solara.Card("Prerequisites", elevation=2):
            has_raster = app_state.file_path.value is not None
            has_crs = app_state.target_crs.value is not None

            if has_raster:
                solara.Success("✓ Raster data loaded")
            else:
                solara.Error("✗ Raster data required")

            if has_crs:
                solara.Success(f"✓ Target CRS set: {app_state.target_crs.value}")
            else:
                solara.Warning("⚠ Target CRS not set (will use raster CRS)")

            if app_state.zone_file_path.value:
                solara.Info(f"✓ Vector data loaded ({app_state.zone_file_info.value['feature_count']} zones)")
            else:
                solara.Info("ℹ No vector data (will use full raster extent)")

        # Statistics selection
        with solara.Card("Select Statistics", elevation=2):
            solara.Markdown("""
            Choose which statistics to calculate for each zone.
            Multiple statistics can be selected.
            """)

            # Create checkboxes for each statistic
            for stat_key, stat_name, stat_desc in AVAILABLE_STATISTICS:
                is_selected = stat_key in app_state.selected_stats.value

                def toggle_stat(stat=stat_key, selected=is_selected):
                    current = app_state.selected_stats.value.copy()
                    if selected:
                        # Remove
                        if stat in current:
                            current.remove(stat)
                    else:
                        # Add
                        if stat not in current:
                            current.append(stat)
                    app_state.selected_stats.value = current

                with solara.Row(style={"align-items": "center"}):
                    solara.Checkbox(
                        label=stat_name,
                        value=is_selected,
                        on_value=lambda v, s=stat_key: toggle_stat(s, not v)
                    )
                    solara.Markdown(f"*{stat_desc}*", style={"font-size": "0.9em", "color": "#666"})

        # Processing options
        with solara.Card("Processing Options", elevation=2):
            solara.Markdown("**Column name for output statistics**")
            solara.InputText(
                label="Statistics column prefix",
                value=app_state.stat_column.value,
                on_value=lambda v: app_state.stat_column.set(v),
                continuous_update=False
            )

            solara.Markdown("""
            Statistics will be saved as columns like: `{prefix}_mean`, `{prefix}_sum`, etc.
            """)

        # Run button
        with solara.Card("Execute", elevation=2):
            can_run = (
                app_state.file_path.value is not None and
                len(app_state.selected_stats.value) > 0 and
                not is_processing.value
            )

            def run_processing():
                is_processing.value = True
                app_state.is_ee_processing.value = True
                app_state.clear_errors()
                app_state.clear_warnings()

                try:
                    result_gdf = run_zonal_statistics(
                        raster_path=app_state.file_path.value,
                        vector_path=app_state.zone_file_path.value,
                        target_crs=app_state.target_crs.value,
                        statistics=app_state.selected_stats.value,
                        column_prefix=app_state.stat_column.value
                    )

                    app_state.results_gdf.value = result_gdf
                    app_state.zonal_results.value = result_gdf.drop(columns=['geometry']) if 'geometry' in result_gdf.columns else result_gdf

                    logger.info(f"Zonal statistics completed. {len(result_gdf)} zones processed.")

                except Exception as e:
                    app_state.add_error(f"Processing error: {str(e)}")
                    logger.error(f"Zonal statistics error: {e}", exc_info=True)

                finally:
                    is_processing.value = False
                    app_state.is_ee_processing.value = False

            solara.Button(
                label="🔄 Run Zonal Statistics" if not is_processing.value else "⏳ Processing...",
                on_click=run_processing,
                disabled=not can_run,
                color="success",
                block=True
            )

            if not can_run and app_state.file_path.value:
                solara.Warning("Please select at least one statistic to calculate")

        # Progress indicator
        if app_state.is_ee_processing.value:
            with solara.Card("Processing Status"):
                solara.ProgressLinear(value=True)  # Indeterminate progress
                if app_state.ee_processing_status.value:
                    solara.Markdown(f"**Status**: {app_state.ee_processing_status.value}")

        # Results preview
        if app_state.zonal_results.value is not None:
            with solara.Success("Processing Complete!"):
                df = app_state.zonal_results.value
                solara.Markdown(f"""
                Successfully processed **{len(df)}** zones with **{len(df.columns)}** statistics columns.

                Go to the **Results** tab to view and download the full results.
                """)
