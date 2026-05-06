from typing import Optional, Dict, List
import solara
from pyproj import CRS
from pyproj.exceptions import CRSError
from component.model.state_manager import app_state
import logging

logger = logging.getLogger("zs.projection_radio_list")

@solara.component  # type: ignore
def ProjectionRadioList(results: List[Dict], on_select=None):
    """
    Projection list with radio-style checkboxes.
    Apply button only shows when a projection is selected.
    """
    selected_name: solara.Reactive[Optional[str]] = solara.use_reactive(None)
    apply_error: solara.Reactive[Optional[str]] = solara.use_reactive(None)
    apply_success: solara.Reactive[Optional[str]] = solara.use_reactive(None)


    def handle_select(proj_name: str):
        """Radio behavior: only one can be selected"""
        if selected_name.value == proj_name:
            selected_name.value = None  # Deselect if clicked again
        else:
            selected_name.value = proj_name
            if on_select:
                on_select(proj_name)
    
    def apply_projection(proj: Optional[Dict]):
        """Validate and commit the selected projection to app_state."""
        apply_error.value = None
        apply_success.value =None

        if proj:
 
            proj4_str = proj.get("proj4")
            if not proj4_str:
                apply_error.value = f"No PROJ4 string available for {proj.get('name')}"
                logger.warning("Projection has no proj4 string: %s", proj)
                return
     
            try:
                crs = CRS.from_proj4(proj4_str)
                wkt = crs.to_wkt(pretty=True)
                app_state.target_crs.value = wkt
                apply_success.value = f"Applied: {proj['name']}"
                logger.info("Applied projection: %s", proj["name"])
            except CRSError as e:
                apply_error.value = f"Failed to parse projection: {e}"
                logger.error("CRSError applying projection %s: %s", proj.get("name"), e)



    with solara.Card():
        if not results:
            solara.Warning("No recommendations available.")
            return

        solara.Markdown("Recommended projection/s sorted by score:")

        for proj in results:
            is_selected = proj["name"] == selected_name.value
            proj4_str = proj.get("proj4")

            with solara.Row(gap="12px", style={"padding": "8px 0"}):
                solara.Checkbox(
                    value=is_selected,
                    on_value=lambda v, name=proj["name"]: handle_select(name),
                )
                #TODO: need to format the text for the distrotion metrics
                with solara.Column(gap="2px"):
                    solara.Markdown(f"**{proj['name']}**")
                    solara.Text(
                        f"Airy's score: {proj['score']:.2e}|"
                        f"\u25a1 distrotion: {proj.get('area_distortion', 0):.2e}|"
                        f"\u2220 distortion: {proj.get('angle_distortion', 0):.2e}°|"
                        f"\u2194 distortion: {proj.get('distance_distortion', 0):.2e}",
                        style="font-size: 0.9em; color: #555;",
                    )

                    if is_selected and proj4_str:
                        solara.Text(proj4_str,
                        style="color: #4caf50; fontFamily: monospace; margin-left: auto;",
                    )

        # === Apply Button - Only show when something is selected ===
        selected_proj = next(
            (p for p in results if p["name"] == selected_name.value), None
        )

        solara.Button(
                "Use This Projection",
                on_click=lambda: apply_projection(selected_proj),
                color="primary",
                block=True,
                icon_name="mdi-check",
                disabled=not selected_proj
            )

        if apply_error.value:
            solara.Error(apply_error.value)
        if apply_success.value:
            solara.Success(apply_success.value)
