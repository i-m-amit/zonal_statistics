from typing import Optional, Dict, List
import solara
from pyproj import CRS
from component.model.state_manager import app_state
@solara.component #type: ignore
def ProjectionRadioList(results: List[Dict], on_select=None):
    """
    Projection list with radio-style checkboxes.
    Apply button only shows when a projection is selected.
    """
    selected_name:solara.Reactive[Optional[str]] = solara.use_reactive(None)

    def handle_select(proj_name: str):
        """Radio behavior: only one can be selected"""
        if selected_name.value == proj_name:
            selected_name.value = None          # Deselect if clicked again
        else:
            selected_name.value = proj_name
            if on_select:
                on_select(proj_name)

    with solara.Card("Projection Recommendations (sorted by score)", elevation=3):
        if not results:
            solara.Warning("No recommendations available.")
            return

        solara.Markdown("**Select the best projection for your area:**")

        for proj in results:
            is_selected = (proj["name"] == selected_name.value)

            with solara.Row(gap="12px", style={"padding": "8px 0"}):
                solara.Checkbox(
                    value=is_selected,
                    on_value=lambda v, name=proj["name"]: handle_select(name),
                )

                with solara.Column(gap="2px"):
                    solara.Markdown(f"**{proj['name']}**")
                    solara.Text(
                        f"Airy's score: {proj['score']:.2e} | "
                        f"□ Area distrotion: {proj.get('area_distortion', 0):.2e} | "
                        f"∠ Angle distortion: {proj.get('angle_distortion', 0):.2e}° | "
                        f"↔ Distance distortion: {proj.get('distance_distortion', 0):.2e}",
                        style="font-size: 0.9em; color: #555;"
                    )

                if is_selected:
                    solara.Text(f"{proj.get("proj4")}", style="color: #4caf50; fontFamily: monospace; margin-left: auto;")

        # === Apply Button - Only show when something is selected ===
        if selected_name.value:
            selected_proj = next((p for p in results if p["name"] == selected_name.value), None)
            if selected_proj:
                with solara.Card("Selected Projection", elevation=2):
                    solara.Markdown(f"**{selected_proj['name']}**")

                    solara.Button(
                        "Use This Projection",
                        on_click=lambda: apply_projection(selected_proj),
                        color="primary",
                        block=True,
                        icon_name="mdi-check"
                    )
        else:
            solara.Info("Please select a projection from the list above.")


def apply_projection(proj: dict):
    """Handle applying the selected projection"""
    try:
        proj4_str = proj.get("proj4")
        if proj4_str:
            crs = CRS.from_proj4(proj4_str)
            wkt = CRS.to_wkt(crs, pretty=True)
            app_state.target_crs.value=wkt
        else:
            print("not a proj4 string")
    except Exception as e:
        solara.Error(f"Failed to generate CRS: {e}")

    solara.Success(f"Applied: **{proj['name']}**")
