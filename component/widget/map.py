import logging

from sepal_ui.mapping import SepalMap
from sepal_ui.sepalwidgets.vue_app import ThemeToggle

logger = logging.getLogger("zsmap.map")


class ZsMap(SepalMap):
    """Zonal statistics Map class to handel map vizualization and interaction."""

    def __init__(self, theme_toggle: ThemeToggle, gee: bool = False):
        super().__init__(fullscreen=True, theme_toggle=theme_toggle, gee=gee)
        self.input_layer = None
        self.zone_layer = None
