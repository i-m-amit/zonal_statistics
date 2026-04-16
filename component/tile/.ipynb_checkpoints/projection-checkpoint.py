"""Projection selection component"""

import logging
from typing import Optional

import solara
from pyproj import CRS
from pyproj.exceptions import CRSError

from component.model import app_state

logger = logging.getLogger("zs.projection")


def validate_epsg(epsg_code: str) -> Optional[str]:
    """Validate EPSG code and return CRS string or error"""
    try:
        epsg_int = int(epsg_code)
        crs = CRS.from_epsg(epsg_int)
        return f"EPSG:{epsg_int}"
    except (ValueError, CRSError) as e:
        return None


def validate_wkt(wkt_string: str) -> Optional[str]:
    """Validate WKT string and return it if valid or None"""
    try:
        crs = CRS.from_wkt(wkt_string)
        return crs.to_wkt()
    except CRSError as e:
        return None


@solara.component #type: ignore
def ProjectionSelector():
    """Component for selecting and managing projections"""

    # Local state for inputs
    epsg_input = solara.use_reactive("")
    wkt_input = solara.use_reactive("")
    validation_message = solara.use_reactive("")

    with solara.Column(gap="10px"):
        # Display current file projections
        with solara.Card("Current Projections", elevation=2):
            if app_state.uploaded_file_info.value:
                solara.Info(f"Input CRS: {app_state.uploaded_file_info.value.get('crs')}")
            else:
                solara.Warning("No raster file loaded")

            if app_state.zone_file_info.value:
                solara.Info(f"Zone CRS: {app_state.zone_file_info.value.get('crs')}")
            elif app_state.zone_file_path.value:
                solara.Warning("Vector file has no CRS defined")

        # Projection selection mode
        with solara.Card("Target Projection", elevation=2):
            solara.Markdown("""
            Choose the target coordinate reference system for processing.
            Data will be reprojected to this CRS before zonal statistics calculation.
            """)

            # Radio button for selection mode
            solara.Select(
                label="Input Method",
                value="EPSG" if app_state.use_epsg.value else "WKT",
                values=["EPSG", "WKT"],
                on_value=lambda v: app_state.use_epsg.set(v == "EPSG"),
            )

            if app_state.use_epsg.value:
                # EPSG input
                with solara.Column():
                    solara.Markdown("**Enter EPSG Code**")
                    solara.Markdown(
                        "Common projections: 4326 (WGS84), 3857 (Web Mercator), 32633 (UTM Zone 33N)"
                    )

                    solara.InputText(
                        label="EPSG Code",
                        value=epsg_input.value,
                        on_value=epsg_input.set,
                        continuous_update=False,
                    )

                    def apply_epsg():
                        validation_message.value = ""
                        crs_string = validate_epsg(epsg_input.value)
                        if crs_string:
                            app_state.target_crs.value = crs_string
                            validation_message.value = (
                                f"✓ Valid EPSG code: {crs_string}"
                            )
                        else:
                            validation_message.value = "✗ Invalid EPSG code"

                    solara.Button(
                        label="Apply EPSG",
                        on_click=apply_epsg,
                        color="primary",
                        disabled=not epsg_input.value,
                    )

            else:
                # WKT input
                with solara.Column():
                    solara.Markdown("**Enter WKT String**")
                    solara.Markdown(
                        "Paste the complete WKT definition of your projection"
                    )

                    solara.InputTextArea(
                        label="WKT String",
                        value=wkt_input.value,
                        on_value=wkt_input.set,
                        continuous_update=False,
                        rows=8,
                    )

                    def apply_wkt():
                        validation_message.value = ""
                        crs_string = validate_wkt(wkt_input.value)
                        if crs_string:
                            app_state.target_crs.value = crs_string
                            validation_message.value = "✓ Valid WKT string"
                        else:
                            validation_message.value = "✗ Invalid WKT string"

                    solara.Button(
                        label="Apply WKT",
                        on_click=apply_wkt,
                        color="primary",
                        disabled=not wkt_input.value,
                    )

            # Validation message
            if validation_message.value:
                if "✓" in validation_message.value:
                    solara.Success(validation_message.value)
                else:
                    solara.Error(validation_message.value)

        # Quick actions
        with solara.Card("Quick Actions", elevation=2):

            def use_raster_crs():
                if app_state.uploaded_file_info.value:
                    app_state.target_crs.value = app_state.uploaded_file_info.value.get('crs')
                    validation_message.value = (
                        f"✓ Using raster CRS: {app_state.uploaded_file_info.value.get('crs')}"
                    )

            def use_vector_crs():
                if app_state.zone_file_info.value:
                    app_state.target_crs.value = app_state.zone_file_info.value.get('crs')
                    validation_message.value = (
                        f"✓ Using vector CRS: {app_state.zone_file_info.value.get('crs')}"
                    )

            with solara.Row():
                solara.Button(
                    label="Use Raster CRS",
                    on_click=use_raster_crs,
                    disabled=not app_state.uploaded_file_info.value,
                    outlined=True,
                )

                solara.Button(
                    label="Use Vector CRS",
                    on_click=use_vector_crs,
                    disabled=not app_state.zone_file_info.value,
                    outlined=True,
                )

        # Current target CRS display
        if app_state.target_crs.value:
            with solara.Success("Target CRS set"):
                try:
                    crs = CRS.from_string(app_state.target_crs.value)
                    solara.Markdown(f"""
                    **{app_state.target_crs.value}**

                    {crs.name}
                    """)
                except Exception as e:
                    solara.Markdown(f"Error {e} in **{app_state.target_crs.value}**")
