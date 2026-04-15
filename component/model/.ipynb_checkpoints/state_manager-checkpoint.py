"""Contains reactive state management for the app"""

import os
import shutil
import tempfile
from typing import Dict, List, Optional, Any

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
        # UI
        # -----------------------------
        self.current_step: solara.Reactive[Optional[int]] = solara.reactive(1)

        # -----------------------------
        # Errors & status
        # -----------------------------
        self.file_error: solara.Reactive[Optional[str]] = solara.reactive(None)
        self.error_messages: solara.Reactive[List[str]] = solara.reactive([])
        self.processing_status: solara.Reactive[str] = solara.reactive("")

        # -----------------------------
        # Temp directory
        # -----------------------------
        self.temp_dir: solara.Reactive[str] = solara.reactive(tempfile.mkdtemp())

        # -----------------------------
        # Zonal stats ()
        # -----------------------------
        self.zonal_result: solara.Reactive[Optional[pd.DataFrame]] = solara.reactive(
            None
        )

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

        self.zonal_result.value = None
        # Reset zone state
        self.zone_file_path.value = None
        self.zone_file_info.value = None
        self.zone_file_error.value = None
        self.zone_added_to_map.value = False

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
# Singleton instance
app_state = AppState()
