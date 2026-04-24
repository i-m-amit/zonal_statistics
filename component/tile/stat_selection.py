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
    ("median", "Median", "Median value (50th percentile)"),
    ("mode", "Mode", "Most frequently occurring value"),
    ("majority", "Majority", "Most common value (categorical)"),
    ("minority", "Minority", "Least common value (categorical)"),
    ("variety", "Variety", "Number of unique values"),
    ("stdev", "Standard Deviation", "Standard deviation"),
    ("variance", "Variance", "Variance of values"),
    ("coefficient_of_variation", "Coefficient of Variation", "Std dev / mean"),
    ("range", "Range", "Difference between max and min"),
    ("quantile", "Quantile", "Value at specified percentile (q)"),
    ("weighted_mean", "Weighted Mean", "Mean weighted by coverage"),
    ("weighted_sum", "Weighted Sum", "Sum weighted by coverage"),
    ("weighted_stdev", "Weighted Std Dev", "Weighted standard deviation"),
    ("weighted_variance", "Weighted Variance", "Weighted variance"),
    ("frac", "Fraction", "Fraction of zone covered by value"),
]

COVERAGE_WEIGHT_OPTIONS = [
    ("fraction", "Fraction"),
    ("none", "None"),
    ("area_cartesian", "Area (Cartesian)"),
    ("area_spherical_m2", "Area (Spherical m²)"),
    ("area_spherical_km2", "Area (Spherical km²)"),
]


@solara.component #type: ignore
def StatsSelectionTile():
    """Panel for configuring and running zonal statistics"""

    # Local state
    is_processing = solara.use_reactive(False)
    quantile_value = solara.use_reactive(0.5)
    show_quantile_config = solara.use_reactive(False)
    
    # Operation arguments state
    coverage_weight = solara.use_reactive("fraction")
    default_value = solara.use_reactive("")
    default_weight = solara.use_reactive("")
    min_coverage_frac = solara.use_reactive(0.0)
    show_operation_args = solara.use_reactive(False)

    with solara.Card(elevation=1, margin=0):
        with solara.Row(justify="space-around", style={"align-items": "center"}):
            
            # 1. Raster Status
            if app_state.file_path.value:
                solara.Success("Raster",  text=True, style={"padding": "0px"})
            else:
                solara.Error("No raster", text=True, style={"padding": "0px"})

            # 2. CRS Status
            if app_state.target_crs.value:
                solara.Success(f"CRS: {app_state.target_crs.value}", text=True)
            else:
                solara.Warning("Raster CRS", text=True)
    
            # 3. Vector Status
            if app_state.zone_file_path.value:
                count = app_state.zone_file_info.value.get('feature_count', 0)
                solara.Info(f"{count} Zones",  text=True)
            else:
                solara.Info("Full Extent",  text=True)

        # Statistics selection
        with solara.Card("Select Statistics", elevation=2):
            solara.Markdown("""
            Choose which statistics to calculate for each zone.
            Multiple statistics can be selected.
            """)

            # Multi-select for statistics
            stat_options = [f"{name} - {desc}" for _, name, desc in AVAILABLE_STATISTICS]
            stat_keys = [key for key, _, _ in AVAILABLE_STATISTICS]
            
            # Map current selected stats to display format
            current_selected = []
            for stat in app_state.selected_stats.value:
                # Find the matching stat in AVAILABLE_STATISTICS
                for i, (key, name, desc) in enumerate(AVAILABLE_STATISTICS):
                    if key == stat:
                        current_selected.append(stat_options[i])
                        break
            
            def on_stats_change(new_selection):
                # Map back from display format to stat keys
                selected_stats = []
                for display_val in new_selection:
                    for i, option in enumerate(stat_options):
                        if option == display_val:
                            selected_stats.append(stat_keys[i])
                            break
                app_state.selected_stats.value = selected_stats
            
            solara.SelectMultiple(
                label="Statistics to calculate",
                all_values=stat_options,
                values=current_selected,
                on_value=on_stats_change,
                dense=False
            )

            # Quantile configuration (show when quantile is selected)
            if "quantile" in app_state.selected_stats.value:
                with solara.Column(style={"margin-top": "16px", "padding": "12px", "background-color": "#f5f5f5", "border-radius": "4px"}):
                    solara.Markdown("**Quantile Configuration**")
                    
                    solara.SliderFloat(
                        label=f"Percentile (q = {quantile_value.value:.2f})",
                        value=quantile_value.value,
                        on_value=quantile_value.set,
                        min=0.0,
                        max=1.0,
                        step=0.01
                    )
                    
                    solara.Markdown(f"*Will calculate the {quantile_value.value*100:.0f}th percentile value*")

        # Operation Arguments Panel
        with solara.Card("Operation Arguments (Advanced)", elevation=2):
            with solara.Column():
                solara.Button(
                    label="⚙️ Configure Operation Arguments" if not show_operation_args.value else "⚙️ Hide Operation Arguments",
                    on_click=lambda: show_operation_args.set(not show_operation_args.value),
                    text=True,
                    outlined=True
                )
                
                if show_operation_args.value:
                    solara.Markdown("""
                    These arguments will be applied to all selected statistics operations.
                    Arguments will be appended as: `stat(min_coverage_frac=X, coverage_weight=Y, ...)`
                    """)
                    
                    # Coverage weight selection
                    solara.Select(
                        label="Coverage Weight",
                        values=[name for _, name in COVERAGE_WEIGHT_OPTIONS],
                        value=next(name for key, name in COVERAGE_WEIGHT_OPTIONS if key == coverage_weight.value),
                        on_value=lambda v: coverage_weight.set(
                            next(key for key, name in COVERAGE_WEIGHT_OPTIONS if name == v)
                        )
                    )
                    
                    # Min coverage fraction
                    solara.SliderFloat(
                        label=f"Minimum Coverage Fraction: {min_coverage_frac.value:.2f}",
                        value=min_coverage_frac.value,
                        on_value=min_coverage_frac.set,
                        min=0.0,
                        max=1.0,
                        step=0.01
                    )
                    
                    # Default value
                    solara.InputInt(
                        label="Default Value (optional, for missing data)",
                        value=default_value.value,
                        on_value=default_value.set,
                        optional = True,
                        continuous_update=False,
                    )
                    
                    # Default weight
                    solara.InputFloat(
                        label="Default Weight (optional)",
                        value=default_weight.value,
                        on_value=default_weight.set,
                        continuous_update=False,
                        optional = True,
                    )
                    
                    # Preview of generated arguments
                    args_preview = []
                    if min_coverage_frac.value > 0:
                        args_preview.append(f"min_coverage_frac={min_coverage_frac.value}")
                    if coverage_weight.value != "fraction":
                        args_preview.append(f"coverage_weight={coverage_weight.value}")
                    if default_value.value:
                        args_preview.append(f"default_value={default_value.value}")
                    if default_weight.value:
                        args_preview.append(f"default_weight={default_weight.value}")
                    
                    if args_preview:
                        preview_str = ", ".join(args_preview)
                        solara.Info(f"Arguments preview: `({preview_str})`")
                        solara.Markdown(f"*Example: `mean({preview_str})`*")

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
                    # Build operation arguments
                    operation_args = {}
                    if show_operation_args.value:
                        if min_coverage_frac.value > 0:
                            operation_args['min_coverage_frac'] = min_coverage_frac.value
                        if coverage_weight.value != "fraction":
                            operation_args['coverage_weight'] = coverage_weight.value
                        if default_value.value:
                            try:
                                operation_args['default_value'] = int(default_value.value)
                            except ValueError:
                                operation_args['default_value'] = default_value.value
                        if default_weight.value:
                            try:
                                operation_args['default_weight'] = float(default_weight.value)
                            except ValueError:
                                operation_args['default_weight'] = default_weight.value
                    
                    # Handle quantile special case
                    quantile_args = {}
                    if "quantile" in app_state.selected_stats.value:
                        quantile_args['q'] = quantile_value.value
                    
                    result_gdf = run_zonal_statistics(
                        raster_path=app_state.file_path.value,
                        vector_path=app_state.zone_file_path.value,
                        target_crs=app_state.target_crs.value,
                        statistics=app_state.selected_stats.value,
                        column_prefix=app_state.stat_column.value,
                        operation_args=operation_args,
                        quantile_args=quantile_args
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