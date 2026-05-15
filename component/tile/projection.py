"""Projection selection component"""

import logging
from typing import Optional

import solara
from pyproj import CRS
from pyproj.exceptions import CRSError

from component.model import app_state
from component.scripts.proj_recommendation import ProjectionRecommender
from component.scripts.geospatial import get_bounds_in_wgs84
from component.widget.projection_checkbox import ProjectionRadioList

logger = logging.getLogger("zs.projection")


def validate_epsg(epsg_code: str) -> Optional[str]:
    """Validate EPSG code and return CRS string or error"""
    try:
        epsg_int = int(epsg_code)
        CRS.from_epsg(epsg_int)
        return f"EPSG:{epsg_int}"
    except (ValueError, CRSError) as e:
        logger.debug("Invalid EPSG %r: %s", epsg_code, e)
        return None


def validate_wkt(wkt_string: str) -> Optional[str]:
    """Validate WKT string and return it if valid or None"""
    try:
        crs = CRS.from_wkt(wkt_string)
        return crs.to_wkt(pretty=True)
    except CRSError as e:
        logger.debug("Invalid WKT: %s", e)
        return None


@solara.component  # type: ignore
def ProjectionSelector():
    """Component for selecting and managing projections"""

    # Local state for inputs
    epsg_input = solara.use_reactive("")
    wkt_input = solara.use_reactive("")
    validation_message = solara.use_reactive("")

    def update_proj_method(v):
        """updsate the proj method and Clear feedback whenever the user switches input methods"""
        app_state.proj_method.set(v)
        validation_message.value = ""
        epsg_input.value = ""
        wkt_input.value = ""

    def apply_epsg():
        validation_message.value = ""
        crs_string = validate_epsg(epsg_input.value)
        if crs_string:
            app_state.target_crs.value = crs_string
            validation_message.value = f"✓ Valid EPSG code: {crs_string}"
            logger.info("Target CRS set via EPSG: %s", crs_string)
        else:
            validation_message.value = "✗ Invalid EPSG code"

    def apply_wkt():
        validation_message.value = ""
        crs_string = validate_wkt(wkt_input.value)
        if crs_string:
            app_state.target_crs.value = crs_string
            validation_message.value = "✓ Valid WKT string"
            logger.info("Target CRS set via WKT")
        else:
            validation_message.value = "✗ Invalid WKT string"

    def use_raster_crs():
        if app_state.uploaded_file_info.value:
            crs = app_state.uploaded_file_info.value.get("crs")
            app_state.target_crs.value = crs
            validation_message.value = f"✓ Using raster CRS: {crs}"
            logger.info("Target CRS set from raster: %s", crs)

    def use_vector_crs():
        if app_state.zone_file_info.value:
            crs = app_state.zone_file_info.value.get("crs")
            app_state.target_crs.value = crs
            validation_message.value = f"✓ Using zone CRS: {crs}"
            logger.info("Target CRS set from zone vector: %s", crs)

    with solara.Column(gap="10px"):
        # Projection selection mode
        with solara.Card("Target Projection", elevation=2):
            solara.Markdown(
                """Choose the target coordinate reference system for processing. Data will be reprojected to this CRS before zonal statistics calculation."""
            )

            # Radio button for selection mode
            solara.Select(
                label="Input Method",
                value=app_state.proj_method.value,
                values=["EPSG", "WKT", "Get recommendation"],
                on_value=update_proj_method,
            )

            if app_state.proj_method.value == "EPSG":
                # EPSG input
                with solara.Column():
                    solara.Markdown("**Enter EPSG Code**")

                    solara.InputText(
                        label="EPSG Code",
                        value=epsg_input.value,
                        on_value=epsg_input.set,
                        continuous_update=False,
                    )

                    solara.Button(
                        label="Apply EPSG",
                        on_click=apply_epsg,
                        color="primary",
                        disabled=not epsg_input.value,
                    )

            elif app_state.proj_method.value == "WKT":
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

                    solara.Button(
                        label="Apply WKT",
                        on_click=apply_wkt,
                        color="primary",
                        disabled=not wkt_input.value,
                    )
            else:
                with solara.Column():
                    solara.Select(
                        label="Distortion type",
                        values=["Equal-area", "Conformal", "Equidistant", "Compromise"],
                        value=app_state.distortion.value,
                        on_value=app_state.distortion.set,
                        disabled=app_state.proj_method.value != "Get recommendation",
                    )
                    if app_state.uploaded_file_info.value:
                        recommender = ProjectionRecommender(
                            get_bounds_in_wgs84(app_state.uploaded_file_info.value)
                        )
                        recommended_projs = recommender.recommond_projections(
                            app_state.distortion.value
                        )
                        if recommended_projs:
                            ProjectionRadioList(recommended_projs)
                        else:
                            solara.Warning("No projections found!.")
                    else:
                        solara.Warning(
                            "Load an input raster first to get projection recommendations."
                        )

            # Validation message
            if validation_message.value:
                if "✓" in validation_message.value:
                    solara.Success(validation_message.value)
                else:
                    solara.Error(validation_message.value)

        # Quick actions
        with solara.Card("Quick Actions", elevation=2):
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
                    solara.Markdown(f"```{app_state.target_crs.value}```")
                except Exception as e:
                    solara.Markdown(f"Error {e} in **{app_state.target_crs.value}**")
