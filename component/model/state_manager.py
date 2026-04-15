"""Contains reactive state management for the app"""

import os
import shutil
import tempfile
from typing import Dict, List, Optional, Any
import geopandas as gpd
import pandas as pd
import solara


class AppState:
    """Centralized state management for area tabulation app using Solara reactive variables."""

    def __init__(self) -> None:
        # -----------------------------
        # File handling
        # -----------------------------
        self.uploaded_file_info: solara.Reactive[Optional[Dict]] = solara.reactive(None)
        self.file_path: solara.Reactive[Optional[str]] = solara.reactive(None)
        self.optimized_raster_path: solara.Reactive[Optional[str]] = solara.reactive(
            None
        )
        self.raster_optimization_error: solara.Reactive[Optional[str]] = (
            solara.reactive(None)
        )
        # Raster optimization status: 'idle', 'running', 'adding_to_map', 'finished', 'error'
        self.raster_optimization_status: solara.Reactive[Optional[str]] = (
            solara.reactive("idle")
        )
        # -----------------------------
        # Zone file state
        # -----------------------------
        self.zone_file_path: solara.Reactive[Optional[str]] = solara.reactive(None)
        self.zone_file_info: solara.Reactive[Optional[Dict[str, Any]]] = solara.reactive(None)
        self.zone_file_error: solara.Reactive[Optional[str]] = solara.reactive(None)
        self.zone_added_to_map: solara.Reactive[bool] = solara.reactive(False)

        # -----------------------------
        # Projection information
        # -----------------------------
        self.raster_crs = solara.reactive(None)
        self.vector_crs: solara.Reactive[Optional[str]] = solara.reactive(None)
        self.target_crs: solara.Reactive[Optional[str]] = solara.reactive(None)
        self.use_epsg = solara.reactive(True)

        # -----------------------------
        # Statistics configuration
        # -----------------------------
        self.selected_stats = solara.reactive([
            "mean", "sum", "count", "min", "max"
        ])
        self.stat_column = solara.reactive("value")

        # -----------------------------
        # UI
        # -----------------------------
        self.current_step: solara.Reactive[Optional[int]] = solara.reactive(1)

        # -----------------------------
        # File Errors & status
        # -----------------------------
        self.file_error: solara.Reactive[Optional[str]] = solara.reactive(None)
        self.error_messages: solara.Reactive[List[str]] = solara.reactive([])
        self.processing_status: solara.Reactive[str] = solara.reactive("")

        # -----------------------------
        # Temp directory
        # -----------------------------
        self.temp_dir: solara.Reactive[str] = solara.reactive(tempfile.mkdtemp())

        # -----------------------------
        # Zonal statsResults
        # -----------------------------
        self.zonal_results = solara.reactive(None)
        self.results_gdf:solara.Reactive[gpd.GeoDataFrame| None] = solara.reactive(None)
        self.selected_map_column = solara.reactive(None)
        # -----------------------------
        # Exact Extract Processing state
        # -----------------------------
        self.is_ee_processing = solara.reactive(False)
        self.ee_processing_status = solara.reactive("")
        self.ee_progress = solara.reactive(0.0)

        # -----------------------------
        # Exact Extract Stat Errors / warnings
        # -----------------------------
        self.ee_errors = solara.reactive([])
        self.ee_warnings = solara.reactive([])
    # -----------------------------
    # Reset state
    # -----------------------------
    def reset_state(self) -> None:
        """Reset all state to initial values."""
        self.uploaded_file_info.value = None
        self.file_path.value = None

        self.file_error.value = None
        self.error_messages.value = []
        self.processing_status.value = ""
        self.raster_optimization_status.value = "idle"
        self.raster_optimization_error.value = None
        self.optimized_raster_path.value = None

        self.zonal_results.value = None
        # Reset zone state
        self.zone_file_path.value = None
        self.zone_file_info.value = None
        self.zone_file_error.value = None
        self.zone_added_to_map.value = False

        #rest proj state
        self.raster_crs.value = None
        self.vector_crs.value = None
        self.target_crs.value = None
        self.use_epsg.value = True

        # Stats config
        self.selected_stats.value = ["mean", "sum", "count", "min", "max"]
        self.stat_column.value = "value"

        # Results
        self.zonal_results.value = None
        self.results_gdf.value = None
        self.selected_map_column.value = None
        # Processing
        self.is_ee_processing.value = False
        self.ee_processing_status.value = ""
        self.ee_progress.value = 0.0

        # Errors
        self.ee_errors.value = []
        self.ee_warnings.value = []

        # Reset workflow
        self.current_step.value = 1

        # Clean temp directory
        if self.temp_dir.value and os.path.exists(self.temp_dir.value):
            try:
                shutil.rmtree(self.temp_dir.value)
            except (OSError, PermissionError):
                pass

        self.temp_dir.value = tempfile.mkdtemp()

    def reset_raster_only(self):
        """Reset only raster-related state"""
        self.file_path.value = None
        self.uploaded_file_info.value = None
        self.file_error.value = None
        self.optimized_raster_path.value = None
        self.raster_optimization_status.value = "idle"
        self.raster_optimization_error.value = None

    def reset_zone_only(self):
        """Reset only zone-related state"""
        self.zone_file_path.value = None
        self.zone_file_info.value = None
        self.zone_file_error.value = None
        self.zone_added_to_map.value = False

    # -----------------------------
    # Errors / warnings
    # -----------------------------
    def add_error(self, error: str) -> None:
        self.ee_errors.value = self.ee_errors.value + [error]

    def add_warning(self, warning: str) -> None:
        self.ee_warnings.value = self.ee_warnings.value + [warning]

    def clear_errors(self) -> None:
        self.ee_errors.value = []

    def clear_warnings(self) -> None:
        self.ee_warnings.value = []




# Singleton instance
app_state = AppState()
