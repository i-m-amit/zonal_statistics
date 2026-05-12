import logging
import ipyleaflet as ipl
from sepal_ui.mapping import SepalMap
from sepal_ui.sepalwidgets.vue_app import ThemeToggle

logger = logging.getLogger("zsmap.map")


class ZsMap(SepalMap):
    """Zonal statistics Map class to handel map vizualization and interaction."""

    def __init__(self, theme_toggle: ThemeToggle, gee: bool = False):
        super().__init__(fullscreen=True, theme_toggle=theme_toggle, gee=gee)
        self.input_layer = None
        self.zone_layer = None

    def add_layer(self, layer: ipl.Layer, hover: bool = False, key: str = "") -> None:
        """Override SepalMap.add_layer to preserve dynamic style_callback for GeoJSON layers."""
        if isinstance(layer, ipl.GeoJSON) and getattr(layer, "style_callback", None):
            # If style_callback is set, skip SepalMap’s default styling
            super().add(layer)
            return

        # Otherwise, fall back to SepalMap’s normal behaviour
        super().add(layer)
        return  # explicit None
