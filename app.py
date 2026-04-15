"""Zonal statsitics and Area tabulation """

import solara
from sepal_ui.logger import setup_logging
from sepal_ui.sepalwidgets.vue_app import MapApp, ThemeToggle
from sepal_ui.solara import (setup_sessions, setup_solara_server,setup_theme_colors, with_sepal_sessions)
from solara.lab.components.theming import theme
from component.model.app_model import AppModel
from component.tile.upload import RasterMapWatcher
from component.tile.upload import UploadTile
from component.tile.projection import ProjectionSelector
from component.widget.map import ZsMap

logger = setup_logging(logger_name="zs")
logger.debug("Zonal statistics app initialized")


setup_solara_server()
@solara.lab.on_kernel_start #type : ignore
def on_kernel_start():
    return setup_sessions()

@solara.component #type : ignore
#@with_sepal_sessions(module_name="area_tabulation")
def Page():
    """ZS app using MapApp layout"""
    app_model = AppModel()
    current_dialog, set_current = solara.use_state(1) #type : ignore

    setup_theme_colors()
    theme_toggle = ThemeToggle()
    theme_toggle.observe(lambda e: setattr(theme, "dark", e["new"]),"dark")
    zs_map = ZsMap(theme_toggle=theme_toggle)
    RasterMapWatcher(zs_map)

    steps_data = [
        {
            "id": 1,
            "name": "1. Upload Map",
            "icon": "mdi-upload",
            "display": "dialog",
            "content": UploadTile(zs_map),
            "width": 800,
            "actions": [
                {
                    "label": "Cancel",
                    "cancel": True,
                    "close": True,
                },
                {"label": "Next", "next": 2},
            ],
        },
        {
            "id": 2,
            "name": "2. Select Projection",
            "icon": "mdi-google-maps",
            "display": "dialog",
            "content": ProjectionSelector(),
            "width": 800,
            "actions": [
                {
                    "label": "Back",
                    "next": 1,
                    "cancel": True,
                },
                {"label": "Next", "next": 3},
            ],
        },
        {
            "id": 3,
            "name": "3. Select Statistics",
            "icon": "mdi-chart-line",
            "display": "dialog",
            "content":None,
            "width": 800,
            "actions": [
                {
                    "label": "Back",
                    "next": 2,
                    "cancel": True,
                },
                {"label": "Next", "next": 4},
            ],
        },
        {
            "id": 4,
            "name": "4. Exract Statistics",
            "icon": "mdi-calculator",
            "display": "dialog",
            "content": None,
            "width": 800,
            "actions": [
                {
                    "label": "Back",
                    "next": 3,  # Activates step with id=1
                    "cancel": True,
                },
                {"label": "Next", "next": 5},
            ],
        },
        {
            "id": 5,
            "name": "5. Export Results",
            "icon": "mdi-download",
            "display": "dialog",
            "content":None,
            "width": 800,
            "actions": [
                {
                    "label": "Back",
                    "next": 4,  # Activates step with id=1
                    "cancel": True,
                },
                {"label": "Finish", "close": True},  # Closes the dialog
            ],
        },
        {
            "id": 6,
            "name": "Summary",
            "icon": "mdi-database",
            "display": "step",
            "content": [],
            "right_panel_action": "toggle",
        },
    ]

    # Right panel configuration
    right_panel_config = {
        "title": "Zonal Stats",
        "icon": "mdi-tools",
        "width": 450,
        "description": "Progress tracking, statistics, and application tools.",
        "toggle_icon": "mdi-chevron-left",
    }

    # Right panel content sections
    right_panel_content = [
        {
            "title": "Progress & Summary",
            "icon": "mdi-progress-check",
            "content": [],
            "description": "Track your progress.",
        },
        {
            "title": "Tools & Settings",
            "icon": "mdi-cog",
            "content": [],
            "divider": True,
            "description": "Application tools, error management, and reset functionality.",
        },
    ]

    # Create the MapApp with the shared map instance
    MapApp.element( #type : ignore
        app_title="Zonal Statistics and Area tabulation",
        app_icon="mdi-map-marker-radius",
        main_map=[zs_map],
        steps_data=steps_data,
        initial_step=1,  # Start with About dialog
        theme_toggle=[theme_toggle],
        dialog_width=800,
        right_panel_config=right_panel_config,
        right_panel_content=right_panel_content,
        repo_url="https://github.com/your-repo/sbae-tool",
        docs_url="https://your-docs-url.com/sbae",
        model=app_model,
    )


# Routes for the application
routes = [
    solara.Route(path="/", component=Page, label="SBAE Tool"),
]
