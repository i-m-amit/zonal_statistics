from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class Projection:
    name: str
    proj4_template: str
    distortion_type: str
    suitable_extent: List[str]
    suitable_shape: List[str]
    suitable_latitude: List[str]
    description: str = ""
    parameters: Dict = field(default_factory=dict)


projection_template = [
    # Worls equal area
    Projection(
        name="Equal Earth",
        proj4_template="+proj=eqearth +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="equal-area",
        suitable_extent=["world"],
        suitable_shape=["east-west", "square"],
        suitable_latitude=["any"],
        description="Modern, aesthetically pleasing equal-area projection (highly recommended)",
    ),
    Projection(
        name="Mollweide",
        proj4_template="+proj=moll +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="equal-area",
        suitable_extent=["world"],
        suitable_shape=["east-west"],
        suitable_latitude=["equator", "mid-latitudes"],
    ),
    Projection(
        name="Hammer",
        proj4_template="+proj=hammer +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="equal-area",
        suitable_extent=["world"],
        suitable_shape=["east-west"],
        suitable_latitude=["any"],
    ),
    Projection(
        name="Eckert IV",
        proj4_template="+proj=eck4 +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="equal-area",
        suitable_extent=["world"],
        suitable_shape=["east-west"],
        suitable_latitude=["any"],
    ),
    # World compromise
    Projection(
        name="Winkel Tripel",
        proj4_template="+proj=wintri +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="compromise",
        suitable_extent=["world"],
        suitable_shape=["east-west"],
        suitable_latitude=["any"],
        description="National Geographic's favorite compromise projection",
    ),
    Projection(
        name="Robinson",
        proj4_template="+proj=robin +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="compromise",
        suitable_extent=["world"],
        suitable_shape=["east-west"],
        suitable_latitude=["any"],
    ),
    Projection(
        name="Natural Earth",
        proj4_template="+proj=natearth +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="compromise",
        suitable_extent=["world"],
        suitable_shape=["any"],
        suitable_latitude=["any"],
    ),
    # Regional /Large scale
    #
    Projection(
        name="Lambert Azimuthal Equal Area",
        proj4_template="+proj=laea +lat_0={lat_0} +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="equal-area",
        suitable_extent=["hemisphere", "continental"],
        suitable_shape=["square"],
        suitable_latitude=["any"],
    ),
    Projection(
        name="Albers Equal-Area Conic",
        proj4_template="+proj=aea +lat_1={lat_1} +lat_2={lat_2} +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="equal-area",
        suitable_extent=["continental"],
        suitable_shape=["east-west"],
        suitable_latitude=["mid-latitudes"],
    ),
    Projection(
        name="Lambert Conformal Conic",
        proj4_template="+proj=lcc +lat_1={lat_1} +lat_2={lat_2} +lat_0={lat_0} +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="conformal",
        suitable_extent=["continental"],
        suitable_shape=["east-west", "square"],
        suitable_latitude=["mid-latitudes"],
    ),
    # Cassini for Tall areas (N-S extent)
    Projection(
        name="Cassini",
        proj4_template="+proj=cass +lat_0={lat_0} +lon_0={central_meridian} +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="equidistant",
        suitable_extent=["continental"],
        suitable_shape=["north-south"],
        suitable_latitude=["any"],
    ),
    # Transverse Mercator for very large scale N-S strips
    Projection(
        name="Transverse Mercator",
        proj4_template="+proj=tmerc +lat_0={lat_0} +lon_0={central_meridian} +k=0.9996 +x_0=500000 +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="conformal",
        suitable_extent=["continental"],
        suitable_shape=["north-south"],
        suitable_latitude=["any"],
    ),
    Projection(
        name="Universal Transverse Mercator",
        proj4_template="+proj=utm +zone={zone} +{hemisphere} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="conformal",
        suitable_extent=["continental"],
        suitable_shape=["north-south"],
        suitable_latitude=["mid-latitudes"],
    ),
    # --- AZIMUTHAL (Square/Hemisphere) ---
    Projection(
        name="Lambert Azimuthal Equal Area",
        proj4_template="+proj=laea +lat_0={lat_0} +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="equal-area",
        suitable_extent=["hemisphere", "continental"],
        suitable_shape=["square"],
        suitable_latitude=["any"],
    ),
    Projection(
        name="Azimuthal Equidistant",
        proj4_template="+proj=aeqd +lat_0={lat_0} +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="equidistant",
        suitable_extent=["hemisphere", "continental"],
        suitable_shape=["square"],
        suitable_latitude=["any"],
    ),
    # --- POLAR & EQUATORIAL SPECIALS ---
    Projection(
        name="Polar Stereographic",
        proj4_template="+proj=stere +lat_0={lat_0} +lon_0={central_meridian} +k=0.994 +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="conformal",
        suitable_extent=["continental"],
        suitable_shape=["any"],
        suitable_latitude=["pole"],
    ),
    Projection(
        name="Equidistant Cylindrical",
        proj4_template="+proj=eqc +lat_ts={lat_1} +lat_0=0 +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
        distortion_type="equidistant",
        suitable_extent=["continental"],
        suitable_shape=["any"],
        suitable_latitude=["equator"],
    ),
]
