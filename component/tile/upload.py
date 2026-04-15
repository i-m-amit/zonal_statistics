import logging
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import ipyleaflet as ipl
import solara
from solara.alias import rv
from sepal_ui.sepalwidgets.file_input import FileInputComponent
from component.scripts.geospatial import (
    is_raster_file,
    is_vector_file,
    get_file_info,
    #save_uploaded_file,
)
from component.scripts.tiling import prepare_for_tiles
from component.model import app_state
from component.widget.map import ZsMap

logger = logging.getLogger('zs.upload')





@solara.component # type: ignore
def RasterMapWatcher(zsmap: ZsMap):
    """Watches for optimized raster and adds it to map. Must stay mounted."""

    def add_optimized_raster_to_map():
        optimized_path = app_state.optimized_raster_path.value
        status = app_state.raster_optimization_status.value

        if (
            optimized_path
            and status == "adding_to_map"
        ):
            zsmap.add_raster(
                optimized_path, layer_name="Layer", key="clas"
            )
            app_state.raster_optimization_status.value = "finished"

    solara.use_effect(# type: ignore
        add_optimized_raster_to_map,
        [
            app_state.optimized_raster_path.value,
            app_state.raster_optimization_status.value,
        ],
    )


@solara.component # type: ignore
def VectorMapWatcher(zsmap: ZsMap):
    """Watches for zone vector and adds it to map. Must stay mounted."""

    def add_zone_vector_to_map():
        zone_path = app_state.zone_file_path.value

        if zone_path and not app_state.zone_added_to_map.value:
            try:
                zsmap.add_layer(
                    zone_path,
                    key="zones"
                )
                app_state.zone_added_to_map.value = True
            except Exception as e:
                logger.error(f"Error adding zone layer: {e}")
                app_state.zone_file_error.value = str(e)

    solara.use_effect(  # type: ignore
        add_zone_vector_to_map,
        [app_state.zone_file_path.value],
    )


@solara.component # type: ignore
def CurrentFileDisplay(zsmap: ZsMap):
    """Display the currently selected file with option to clear it."""

    def clear_file():
        """Clear the current file and reset related state."""
        # Remove map layers first
        if zsmap:
            zsmap.remove_layer("clas", none_ok=True)
            if zsmap.zone_layer:
                try:
                    zsmap.remove_layer(zsmap.zone_layer)
                except Exception:
                    pass
                zsmap.zone_layer = None

        # Clear all file-related state
        app_state.reset_state()

        # Reset workflow step
        if app_state.current_step.value:
            if app_state.current_step.value > 1:
                app_state.current_step.value = 1

    if app_state.uploaded_file_info.value is None or app_state.file_path.value is None:
        return

    file_info = app_state.uploaded_file_info.value
    file_path = app_state.file_path.value
    file_name = Path(file_path).name
    optimization_status = app_state.raster_optimization_status.value
    is_loading = optimization_status in ("running", "adding_to_map")

    with solara.Card(classes=["mb-4"]):

        with solara.Row(justify="space-between", style={"align-items": "center"}):
            with solara.Column(gap="0px"):
                solara.HTML(
                    tag="div",
                    unsafe_innerHTML=f"<strong>Current File:</strong> {file_name}",
                    style="font-size: 14px;",
                )
                file_type = file_info.get("file_type", "unknown").title()
                size_mb = file_info.get("size_mb", 0)
                solara.HTML(
                    tag="div",
                    unsafe_innerHTML=f"Type: {file_type} | Size: {size_mb:.1f} MB",
                    style="font-size: 12px; color: #666; margin-top: 4px;",
                )

            solara.Button(
                label="",
                icon_name="mdi-close",
                on_click=clear_file,
                color="error",
                text=True,
                icon=True,
            )
        (
            solara.v.ProgressLinear(indeterminate=is_loading, classes=["my-2"]) # type: ignore
            if is_loading
            else None
        )


@solara.component # type: ignore
def UploadTile(zsmap: ZsMap):
    """Step 1: File Upload Dialog."""
    is_loading = solara.use_reactive(False)

    has_file = (
        app_state.uploaded_file_info.value is not None
        and app_state.file_path.value is not None
    )

    has_zone = (
        app_state.zone_file_info.value is not None
        and app_state.zone_file_path.value is not None
    )

    def prepare_raster_worker(file_path):
        """Worker function for raster tiling in separate thread."""

        def worker():
            original_file_path = file_path
            app_state.raster_optimization_status.value = "running"
            app_state.raster_optimization_error.value = None
            app_state.optimized_raster_path.value = None
            try:
                prep = prepare_for_tiles(file_path, warp_to_3857=True)

                # Check if file was cleared/changed during processing
                if app_state.file_path.value != original_file_path:
                    logger.debug("File changed during optimization, discarding result")
                    return None

                app_state.optimized_raster_path.value = prep["path"]
                app_state.raster_optimization_status.value = "adding_to_map"
                return prep
            except Exception as e:
                # Only set error if file is still the same
                if app_state.file_path.value == original_file_path:
                    app_state.raster_optimization_status.value = "error"
                    app_state.raster_optimization_error.value = str(e)
                raise

        return worker

    # Thread for raster preparation - only starts if no optimized path exists
    raster_prep_result = solara.use_thread(
        (
            prepare_raster_worker(app_state.file_path.value)
            if (
                has_file
                and is_raster_file(app_state.file_path.value or "")
                and not app_state.optimized_raster_path.value
            )
            else lambda: None
        ),
        dependencies=[app_state.file_path.value],
        intrusive_cancel=False,
    )

    with solara.Column():
        with solara.Card():
            solara.HTML(
                tag="h3",
                unsafe_innerHTML="1. Upload Input Layer (Raster)",
                style="margin-bottom: 16px; font-size: 18px;",
            )
            RasterUploadSection(is_loading=is_loading)

            if has_file:
                # Show raster preparation status
                if is_raster_file(app_state.file_path.value or ""):
                    if raster_prep_result.state == solara.ResultState.RUNNING:
                        solara.Info(
                            "⏳ Optimizing raster for display... This may take a few moments for large files."
                        )
                        solara.ProgressLinear(value=True)
                    elif raster_prep_result.state == solara.ResultState.ERROR:
                        solara.Error(f"Error optimizing raster: {raster_prep_result.error}")
                    elif raster_prep_result.state == solara.ResultState.FINISHED:
                        solara.Success(
                            "✅ Input layer uploaded and optimized successfully!"
                        )
                else:
                    solara.Success("✅ Classification layer uploaded successfully!")
        
        with solara.Card():
            solara.HTML(
                tag="h3",
                unsafe_innerHTML="2. Upload Zone Layer (Vector)",
                style="margin-bottom: 16px; font-size: 18px;",
            )
            ZoneUploadSection()
            if has_zone:
                solara.Success("✅ Zone layer uploaded successfully!")

        # Show summary if both files are uploaded
        if has_file and has_zone:
            with solara.Card(classes=["mt-4"]):
                solara.Success(
                    "✅ Both layers uploaded! You can proceed to the next step for zonal statistics."
                )


@solara.component
def RasterUploadSection(is_loading: solara.Reactive[bool]):
    """Simplified File Upload Section - No area computation"""

    # Local preview state (stores file path too)
    selected_file_path: solara.Reactive[Optional[str]] = solara.use_reactive(None)
    selected_file_info_preview: solara.Reactive[Optional[Dict]] = solara.use_reactive(None)
    is_valid_file = solara.use_reactive(False)

    def reset_all_state():
        """Reset all application state including map."""
        app_state.reset_raster_only()
        app_state.processing_status.value = ""
        selected_file_path.value = None
        selected_file_info_preview.value = None
        is_valid_file.value = False

    def handle_file_selection(file_path: Optional[str]):
        """When user selects a file"""
        if not file_path:
            reset_all_state()
            return
        app_state.uploaded_file_info.value = None
        app_state.file_error.value = None

        try:
            file_info_dict = get_file_info(file_path)

            if file_info_dict.get("error"):
                app_state.file_error.value = file_info_dict["error"]
                selected_file_path.value = None
                selected_file_info_preview.value = None
                is_valid_file.value = False
                return

            # Only set local preview state, NOT global app_state yet
            selected_file_path.value = file_path
            selected_file_info_preview.value = file_info_dict
            is_valid_file.value = True
            app_state.file_error.value = None

        except Exception as e:
            app_state.file_error.value = str(e)
            selected_file_path.value = None
            selected_file_info_preview.value = None
    


    def confirm_file_upload():
        """When user clicks 'Use This File'"""
        if not selected_file_info_preview.value or not selected_file_path.value:
            return

        app_state.file_error.value = None

        try:
            is_loading.value = True
            
            # Now update global state
            app_state.file_path.value = selected_file_path.value
            app_state.uploaded_file_info.value = selected_file_info_preview.value
            
        except Exception as e:
            app_state.file_error.value = str(e)
        finally:
            is_loading.value = False
    
    FileUploadInstructions()
    FileInputComponent(on_value=handle_file_selection)


    if app_state.file_error.value:
        ErrorAlert(app_state.file_error.value)

    # Preview - shows when file is selected but not yet confirmed
    if selected_file_info_preview.value and not app_state.uploaded_file_info.value:
        FilePreview(selected_file_info_preview.value)

    # Use This File Button - only show when file is selected but not uploaded
    if selected_file_info_preview.value and not app_state.uploaded_file_info.value:
        solara.Button(
            "Use This File",
            on_click=confirm_file_upload,
            color="primary",
            block=True,
            disabled=not selected_file_info_preview.value,
            loading=is_loading.value,
        )


@solara.component  # type: ignore
def ZoneUploadSection():
    """File upload component for vector zone layer."""
    selected_file_path: solara.Reactive[Optional[str]] = solara.use_reactive(None)
    selected_file_info_preview: solara.Reactive[Optional[Dict]] = solara.use_reactive(None)
    is_valid_file: solara.Reactive[bool] = solara.use_reactive(False)

    def handle_file_selection(file_path):
        """Handle file selection for zones."""
        if not file_path:
            selected_file_path.value = None
            selected_file_info_preview.value = None
            is_valid_file.value = False
            return

        app_state.zone_file_error.value = None

        try:
            file_info_dict = get_file_info(file_path)

            if file_info_dict.get("error"):
                app_state.zone_file_error.value = file_info_dict["error"]
                selected_file_path.value = None
                selected_file_info_preview.value = None
                is_valid_file.value = False
                return

            # Check if it's a vector file
            if file_info_dict.get("file_type") != "vector":
                app_state.zone_file_error.value = "Please select a vector file (Shapefile, GeoJSON, or GeoPackage)"
                selected_file_path.value = None
                selected_file_info_preview.value = None
                is_valid_file.value = False
                return

            # If valid, update app state directly (no confirmation needed for zones)
            app_state.zone_file_path.value = file_path
            app_state.zone_file_info.value = file_info_dict
            app_state.zone_added_to_map.value = False
            is_valid_file.value = True
            app_state.zone_file_error.value = None

        except Exception as e:
            app_state.zone_file_error.value = str(e)
            selected_file_path.value = None
            selected_file_info_preview.value = None
            is_valid_file.value = False

    solara.Markdown(
        """
    Upload your zone boundaries as a vector file:
    - **Shapefile** (.shp)
    - **GeoJSON** (.geojson, .json)
    - **GeoPackage** (.gpkg)
    """
    )

    FileInputComponent(on_value=handle_file_selection)

    if app_state.zone_file_error.value:
        ErrorAlert(app_state.zone_file_error.value)


@solara.component # type: ignore
def UploadInstructions():
    solara.Markdown("Upload the categorical raster to calculate the statistics")


@solara.component # type: ignore
def FileUploadInstructions():
    """Instructions for file upload formats."""
    solara.Markdown(
        """
    Upload your input raster one of these formats:
    - **Raster**: GeoTIFF (.tif), ERDAS Imagine (.img)
    """
    )


@solara.component # type: ignore
def ErrorAlert(error_message: str):
    """Error alert component."""
    with rv.Alert(type="error", text=True):
        solara.Markdown(f"**Error:** {error_message}")


@solara.component # type: ignore
def SuccessAlert(file_info: Dict[str, Any]):
    """Success alert component showing file information."""
    with rv.Alert(type="success", text=True):
        solara.Markdown(
            f"""
        **File uploaded successfully!**
        - Type: {file_info.get("file_type", "unknown").title()}
        - Size: {file_info.get("size_mb", 0):.1f} MB
        - Features: {file_info.get("feature_count", 0):,}
        - CRS: {file_info.get("crs", "Not specified")}
        """
        )


@solara.component # type: ignore
def FilePreview(file_info: Dict[str, Any]):
    """Preview component showing file information before confirmation."""
    with rv.Alert(type="info", text=True):
        with solara.Column(gap="4px"):
            solara.Text(
                "File selected:", style="font-weight: bold; margin-bottom: 4px;"
            )
            solara.Text(f"Type: {file_info.get('file_type', 'unknown').title()}")
            solara.Text(f"Size: {file_info.get('size_mb', 0):.1f} MB")
            solara.Text(f"Features: {file_info.get('feature_count', 0):,}")
            solara.Text(f"CRS: {file_info.get('crs', 'Not specified')}")