from dataclasses import dataclass
from typing import Tuple, Optional, List
import numpy as np
import pyproj
from pyproj.crs.crs import CRS
from math import degrees, radians, sqrt, sin, cos, asin, floor

@dataclass
class Projection:
    name: str
    proj4_template: str
    distortion_type: str
    suitable_extent: str
    suitable_shape: str
    suitable_latitude: str  # New: pole, equator, mid-latitudes, any
    parameters: dict

@dataclass
class DistortionMetrics:
    avg_area_distortion: float
    avg_angular_distortion: float
    avg_distance_distortion: float

class ProjectionSelector:
    def __init__(self):
        self.projections = [
            # Equal-area projections
            Projection(
                name="Mollweide",
                proj4_template="+proj=moll +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="equal-area",
                suitable_extent="world",
                suitable_shape="east-west",
                suitable_latitude="equator|mid-latitudes",
                parameters={"standard_parallels": None, "central_meridian": 0}
            ),
            Projection(
                name="Sinusoidal",
                proj4_template="+proj=sinu +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="equal-area",
                suitable_extent="world",
                suitable_shape="east-west",
                suitable_latitude="equator|mid-latitudes",
                parameters={"standard_parallels": None, "central_meridian": 0}
            ),
            Projection(
                name="Eckert IV",
                proj4_template="+proj=eck4 +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="equal-area",
                suitable_extent="world",
                suitable_shape="east-west",
                suitable_latitude="equator|mid-latitudes",
                parameters={"standard_parallels": None, "central_meridian": 0}
            ),
            Projection(
                name="Albers Equal-Area Conic",
                proj4_template="+proj=aea +lat_1={lat_1} +lat_2={lat_2} +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="equal-area",
                suitable_extent="continental",
                suitable_shape="east-west",
                suitable_latitude="mid-latitudes",
                parameters={"standard_parallels": [29.5, 45.5], "central_meridian": 0}
            ),
            Projection(
                name="Oblique Lambert Azimuthal Equal-Area",
                proj4_template="+proj=laea +lat_0={lat_0} +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="equal-area",
                suitable_extent="continental|hemisphere",
                suitable_shape="square",
                suitable_latitude="any",  # Suitable for all latitudes
                parameters={"standard_parallels": None, "central_meridian": 0, "lat_0": 0}
            ),
            Projection(
                name="Hammer-Aitoff",
                proj4_template="+proj=hammer +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="equal-area",
                suitable_extent="world",
                suitable_shape="east-west",
                suitable_latitude="equator|mid-latitudes",
                parameters={"standard_parallels": None, "central_meridian": 0}
            ),
            Projection(
                name="Cylindrical Equal-Area",
                proj4_template="+proj=cea +lon_0={central_meridian} +lat_ts={lat_0} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="equal-area",
                suitable_extent="continental",
                suitable_shape="east-west",
                suitable_latitude="equator",
                parameters={"standard_parallels": None, "central_meridian": 0, "lat_0": 0}
            ),
            Projection(
                name="Transverse Cylindrical Equal-Area",
                proj4_template="+proj=tcea +lon_0={central_meridian} +lat_ts={lat_0} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="equal-area",
                suitable_extent="continental",
                suitable_shape="north-south",
                suitable_latitude="mid-latitudes",
                parameters={"standard_parallels": None, "central_meridian": 0, "lat_0": 0}
            ),
            # Conformal projections
            Projection(
                name="Universal Transverse Mercator",
                proj4_template="+proj=utm +zone={zone} +{hemisphere} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="conformal",
                suitable_extent="continental",
                suitable_shape="north-south",
                suitable_latitude="mid-latitudes",  # UTM is not used near poles
                parameters={"zone": 1, "hemisphere": "north"}
            ),
            Projection(
                name="Transverse Mercator",
                proj4_template="+proj=tmerc +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="conformal",
                suitable_extent="continental",
                suitable_shape="north-south",
                suitable_latitude="mid-latitudes",
                parameters={"standard_parallels": None, "central_meridian": 0}
            ),
            Projection(
                name="Lambert Conformal Conic",
                proj4_template="+proj=lcc +lat_1={lat_1} +lat_2={lat_2} +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="conformal",
                suitable_extent="continental",
                suitable_shape="east-west",
                suitable_latitude="mid-latitudes",
                parameters={"standard_parallels": [33, 45], "central_meridian": 0}
            ),
            # Other projections
            Projection(
                name="Robinson",
                proj4_template="+proj=robin +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="compromise",
                suitable_extent="world",
                suitable_shape="east-west",
                suitable_latitude="equator|mid-latitudes",
                parameters={"standard_parallels": None, "central_meridian": 0}
            ),
            Projection(
                name="Azimuthal Equidistant",
                proj4_template="+proj=aeqd +lat_0={lat_0} +lon_0={central_meridian} +ellps=WGS84 +datum=WGS84 +no_defs",
                distortion_type="equidistant",
                suitable_extent="hemisphere",
                suitable_shape="square",
                suitable_latitude="pole",
                parameters={"standard_parallels": None, "central_meridian": 0, "lat_0": 0}
            ),
        ]

    def calculate_utm_parameters(self, central_meridian: float, central_latitude: float) -> dict:
        """Calculate UTM zone and hemisphere based on central meridian and latitude."""
        zone = int(floor((central_meridian + 180) / 6) + 1)
        hemisphere = "north" if central_latitude >= 0 else "south"
        return {"zone": zone, "hemisphere": hemisphere}

    def classify_extent_and_shape(self, min_lon: float, max_lon: float, min_lat: float, max_lat: float) -> Tuple[str, str]:
        """Classify geographic extent and shape based on bounding box."""
        lon_span = max_lon - min_lon
        lat_span = max_lat - min_lat

        if lon_span > 240 or lat_span > 120:
            extent = "world"
        elif lon_span > 60 or lat_span > 30:
            extent = "hemisphere"
        else:
            extent = "continental"

        aspect_ratio = lon_span / lat_span if lat_span != 0 else float('inf')
        if aspect_ratio > 1.5:
            shape = "east-west"
        elif aspect_ratio < 0.67:
            shape = "north-south"
        else:
            shape = "square"

        return extent, shape

    def classify_latitude_zone(self, min_lat: float, max_lat: float, extent: str) -> str:
        """Classify latitude zone based on central latitude and extent."""
        central_latitude = (min_lat + max_lat) / 2
        max_abs_latitude = max(abs(min_lat), abs(max_lat))

        # Center at pole
        if abs(central_latitude) > 70 or (max_abs_latitude > 85 and extent == "continental"):
            return "pole"
        # Center along equator
        elif abs(central_latitude) <= 15 or (extent == "hemisphere" and max_abs_latitude <= 23.43665):
            return "equator"
        # Center away from pole or equator
        else:
            return "mid-latitudes"

    def calculate_parameters(self, min_lon: float, max_lon: float, min_lat: float, max_lat: float) -> dict:
        """Calculate projection parameters."""
        central_meridian = round((min_lon + max_lon) / 2, 2)
        lat_0 = round((min_lat + max_lat) / 2, 2)
        lat_span = max_lat - min_lat
        lat_1 = round(min_lat + lat_span / 6, 2)
        lat_2 = round(max_lat - lat_span / 6, 2)

        params = {
            "central_meridian": central_meridian,
            "lat_0": lat_0,
            "lat_1": lat_1,
            "lat_2": lat_2
        }

        # Add UTM-specific parameters
        utm_params = self.calculate_utm_parameters(central_meridian, lat_0)
        params.update(utm_params)

        return params

    def get_wkt(self, proj: Projection) -> str:
        """Convert PROJ.4 template to WKT using pyproj."""
        try:
            proj4_str = proj.proj4_template.format(**proj.parameters)
            crs = CRS.from_proj4(proj4_str)
            return crs.to_wkt(pretty=True)
        except Exception as e:
            return f"Error generating WKT for {proj.name}: {str(e)}"

    def compute_tissot_metrics(self, proj: Projection, min_lon: float, max_lon: float, min_lat: float, max_lat: float) -> DistortionMetrics:
        """Compute Tissot's indicatrix metrics for a projection over the bounding box using WGS84 ellipsoid."""
        try:
            proj4_str = proj.proj4_template.format(**proj.parameters)
            projector = pyproj.Proj(proj4_str)
            geod = pyproj.Geod(ellps="WGS84")

            lon_points = np.linspace(min_lon, max_lon, 5)
            lat_points = np.linspace(min_lat, max_lat, 5)
            area_distortions = []
            angular_distortions = []
            distance_distortions = []

            for lon in lon_points:
                for lat in lat_points:
                    lon_rad, lat_rad = radians(lon), radians(lat)
                    delta_deg = 0.0001
                    delta_rad = radians(delta_deg)

                    x, y = projector(lon, lat)
                    lon_n, lat_n, _ = geod.fwd(lon, lat, 0, delta_deg * 111319.9)
                    x_n, y_n = projector(lon_n, lat_n)
                    lon_e, lat_e, _ = geod.fwd(lon, lat, 90, delta_deg * 111319.9 * cos(lat_rad))
                    x_e, y_e = projector(lon_e, lat_e)

                    h = sqrt((x_n - x)**2 + (y_n - y)**2) / (delta_deg * 111319.9)
                    k = sqrt((x_e - x)**2 + (y_e - y)**2) / (delta_deg * 111319.9 * cos(lat_rad))

                    area_scale = h * k
                    area_distortion = abs(area_scale - 1) if proj.distortion_type != "equal-area" else 0.0

                    angular_distortion = 0.0
                    if h + k > 1e-10:
                        angular_distortion = degrees(2 * asin(abs(h - k) / (h + k)))

                    distance_scale = (h + k) / 2
                    distance_distortion = abs(distance_scale - 1)

                    area_distortions.append(area_distortion)
                    angular_distortions.append(angular_distortion)
                    distance_distortions.append(distance_distortion)

            return DistortionMetrics(
                avg_area_distortion=float(np.mean(area_distortions)),
                avg_angular_distortion=float(np.mean(angular_distortions)),
                avg_distance_distortion=float(np.mean(distance_distortions))
            )

        except Exception as e:
            print(f"Error computing Tissot metrics for {proj.name}: {e}")
            return DistortionMetrics(float('inf'), float('inf'), float('inf'))

    def select_projection(self, min_lon: float, max_lon: float, min_lat: float, max_lat: float,
                         distortion_type: str) -> Optional[Projection]:
        """Select a projection based on bounding box, distortion type, shape, latitude, and Tissot's indicatrix."""
        extent, shape = self.classify_extent_and_shape(min_lon, max_lon, min_lat, max_lat)
        latitude_zone = self.classify_latitude_zone(min_lat, max_lat, extent)
        params = self.calculate_parameters(min_lon, max_lon, min_lat, max_lat)

        # First try: match distortion type, extent, shape, and latitude zone
        candidates = [
            proj for proj in self.projections
            if proj.distortion_type.lower() == distortion_type.lower() and
               extent in proj.suitable_extent.split('|') and
               proj.suitable_shape == shape and
               (latitude_zone in proj.suitable_latitude.split('|') or proj.suitable_latitude == "any")
        ]

        # Second try: match distortion type, extent, and latitude zone, relax shape
        if not candidates:
            candidates = [
                proj for proj in self.projections
                if proj.distortion_type.lower() == distortion_type.lower() and
                   extent in proj.suitable_extent.split('|') and
                   (latitude_zone in proj.suitable_latitude.split('|') or proj.suitable_latitude == "any")
            ]

        # Third try: include world projections, match distortion type and latitude zone
        if not candidates:
            candidates = [
                proj for proj in self.projections
                if proj.distortion_type.lower() == distortion_type.lower() and
                   (extent in proj.suitable_extent.split('|') or proj.suitable_extent == "world") and
                   (latitude_zone in proj.suitable_latitude.split('|') or proj.suitable_latitude == "any")
            ]

        # Filter out conic projections if they risk pole opening
        candidates = [
            proj for proj in candidates
            if not (proj.name.endswith("Conic") and max(abs(min_lat), abs(max_lat)) > 85)
        ]

        if not candidates:
            return None

        for proj in candidates:
            proj.parameters.update(params)
            proj.proj4_template = proj.proj4_template

        scored_projections = []
        for proj in candidates:
            metrics = self.compute_tissot_metrics(proj, min_lon, max_lon, min_lat, max_lat)
            score = metrics.avg_area_distortion if distortion_type.lower() == "equal-area" else \
                    metrics.avg_angular_distortion if distortion_type.lower() == "conformal" else \
                    metrics.avg_distance_distortion if distortion_type.lower() == "equidistant" else \
                    (metrics.avg_area_distortion + metrics.avg_angular_distortion + metrics.avg_distance_distortion) / 3
            tiebreaker = metrics.avg_angular_distortion if distortion_type.lower() == "equal-area" else 0.0
            penalty = 1000 if proj.suitable_extent == "world" and extent == "continental" else 0
            total_score = score + tiebreaker + penalty
            scored_projections.append((proj, total_score, metrics))

        if scored_projections:
            selected = min(scored_projections, key=lambda x: x[1])
            return selected[0]
        return None

def main():
    selector = ProjectionSelector()

    try:
        min_lon = float(input("Enter minimum longitude (-180 to 180): "))
        max_lon = float(input("Enter maximum longitude (-180 to 180): "))
        min_lat = float(input("Enter minimum latitude (-90 to 90): "))
        max_lat = float(input("Enter maximum latitude (-90 to 90): "))
        distortion_type = input("Enter distortion type (equal-area, conformal, equidistant, compromise): ").strip()

        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and
                -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            print("Error: Invalid coordinate range.")
            return
        if min_lon >= max_lon or min_lat >= max_lat:
            print("Error: Minimum coordinates must be less than maximum.")
            return
        if distortion_type.lower() not in ["equal-area", "conformal", "equidistant", "compromise"]:
            print("Error: Invalid distortion type.")
            return

        projection = selector.select_projection(min_lon, max_lon, min_lat, max_lat, distortion_type)

        if projection:
            metrics = selector.compute_tissot_metrics(projection, min_lon, max_lon, min_lat, max_lat)
            wkt = selector.get_wkt(projection)
            print("\nRecommended Projection:")
            print(f"Name: {projection.name}")
            print(f"Distortion Type: {projection.distortion_type}")
            print(f"Suitable Extent: {projection.suitable_extent}")
            print(f"Suitable Shape: {projection.suitable_shape}")
            print(f"Suitable Latitude: {projection.suitable_latitude}")
            print(f"WKT Definition:\n{wkt}")
            print(f"Parameters: {projection.parameters}")
            print(f"Distortion Metrics:")
            print(f"  Avg Area Distortion: {metrics.avg_area_distortion:.4f}")
            print(f"  Avg Angular Distortion: {metrics.avg_angular_distortion:.4f} degrees")
            print(f"  Avg Distance Distortion: {metrics.avg_distance_distortion:.4f}")
        else:
            print("No suitable projection found.")

    except ValueError:
        print("Error: Please enter valid numeric values for coordinates.")

if __name__ == "__main__":
    main()
