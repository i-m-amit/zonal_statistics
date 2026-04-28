"""
Advanced Projection Recommender and WKT generation.
Inspired by Projection Wizard.
"""

from typing import List, Optional, Dict
import numpy as np
import pyproj
from pyproj import CRS, Geod
from math import radians, degrees, sin, sqrt, asin, cos, log
from component.scripts.proj_util import projection_template, Projection

from dataclasses import dataclass 



@dataclass
class DistortionMetrics:
    avg_area_distortion: float = 0.0
    avg_angular_distortion: float = 0.0
    avg_distance_distortion: float = 0.0
    avg_h: float = 0.0
    avg_k: float = 0.0
    airys_criterion: float = 0.0


class ProjectionRecommender:
    def __init__(self):
        self.projections: List[Projection] = self._init_projections()

    def _init_projections(self) -> List[Projection]:
        return projection_template
    # ======================
    # TISSOT CALCULATION
    # ======================
    def compute_metrics(
        self,
        proj: Projection,
        min_lon: float,
        max_lon: float,
        min_lat: float,
        max_lat: float,
    ) -> DistortionMetrics:
        """Tissot's indicatrix calculation."""
        try:
            params = self._calculate_parameters(min_lon, max_lon, min_lat, max_lat)
            proj4_str = proj.proj4_template.format(**params)
            proj_obj = pyproj.Proj(proj4_str)

            # Better sampling grid - avoid edges and poles
            lons = np.linspace(min_lon + 2, max_lon - 2, 7)
            lats = np.linspace(min_lat + 2, max_lat - 2, 7)

            angle_dists = []
            dist_dists = []
            geod = Geod(ellps="WGS84")
            total_weight = 0
            weighted_area_dist = 0
            k_s = []
            h_s = []

            for lat in lats:
                weight = cos(radians(lat))
                for lon in lons:
                    if abs(lat) > 88:  # Skip near poles
                        continue

                    # Base point
                    x, y = proj_obj(lon, lat)

                    # North displacement (~1km)
                    lon_n, lat_n, _ = geod.fwd(lon, lat, 0, 1000)
                    x_n, y_n = proj_obj(lon_n, lat_n)
                    # East displacement (~1km)
                    lon_e, lat_e, _ = geod.fwd(lon, lat, 90, 1000)
                    x_e, y_e = proj_obj(lon_e, lat_e)

                    # Scale factors h (meridional) and k (parallel)
                    h = sqrt((x_n - x) ** 2 + (y_n - y) ** 2) / 1000.0
                    k = sqrt((x_e - x) ** 2 + (y_e - y) ** 2) / 1000.0
                    h_s.append(h)
                    k_s.append(k)

                    # Area distortion
                    area_scale = h * k
                    area_dist = abs(area_scale - 1.0)
                    weighted_area_dist += area_dist * weight
                    total_weight += weight

                    # Angular distortion in degrees
                    angular_dist = 0.0
                    if h + k > 1e-8:
                        angular_dist = degrees(2 * asin(abs(h - k) / (h + k)))

                    # Distance distortion
                    distance_dist = abs((h + k) / 2 - 1.0)

                    angle_dists.append(angular_dist)
                    dist_dists.append(distance_dist)

            if total_weight == 0:
                return DistortionMetrics(
                    float("inf"),
                    float("inf"),
                    float("inf"),
                    float("inf"),
                    float("inf"),
                    float("inf"),
                )
            avg_h = np.mean(h_s)
            avg_k = np.mean(k_s)

            return DistortionMetrics(
                avg_area_distortion=float(weighted_area_dist / total_weight),
                avg_angular_distortion=float(np.mean(angle_dists)),
                avg_distance_distortion=float(np.mean(dist_dists)),
                avg_h=float(avg_h),
                avg_k=float(avg_k),
                airys_criterion=sqrt(
                    log(max(avg_h, 1e-9)) ** 2 + log(max(avg_k, 1e-9)) ** 2
                ),
            )

        except Exception as e:
            print(f"Tissot calculation failed for {proj.name}: {e}")
            return DistortionMetrics(
                float("inf"),
                float("inf"),
                float("inf"),
                float("inf"),
                float("inf"),
                float("inf"),
            )

    def _calculate_parameters(
        self, min_lon: float, max_lon: float, min_lat: float, max_lat: float
    ) -> dict:
        """Calculate projection parameters"""
        central_meridian = round((min_lon + max_lon) / 2, 4)
        lat_0 = round((min_lat + max_lat) / 2, 4)

        # The one-sixth rule for standard parallels
        lat_diff = max_lat - min_lat
        one_sixth = lat_diff / 6.0

        lat_1 = round(min_lat + one_sixth, 4)
        lat_2 = round(max_lat - one_sixth, 4)

        return {
            "central_meridian": central_meridian,
            "lat_0": lat_0,
            "lat_1": lat_1,
            "lat_2": lat_2,
            "zone": int((central_meridian + 180) // 6) + 1,
            "hemisphere": "north" if lat_0 >= 0 else "south",
        }

    # ======================
    # GET WKT METHOD
    # ======================
    def get_wkt(self, proj: Projection) -> str:
        """Convert Projection object to valid WKT string."""
        try:
            params = self._calculate_parameters(
                -180, 180, -90, 90
            )  # default safe params
            proj4_str = proj.proj4_template.format(**params)
            crs = CRS.from_proj4(proj4_str)
            return crs.to_wkt(pretty=True)
        except Exception as e:
            return f"ERROR generating WKT for {proj.name}: {str(e)}"

    # ======================
    # MAIN RECOMMENDATION
    # ======================
    def select_projection(
        self,
        min_lon: float,
        max_lon: float,
        min_lat: float,
        max_lat: float,
        preferred_distortion: str = "Balanced",
    ) -> Optional[List[tuple[Projection, float]]]:
        """Main projection  recommendation engine"""

        extent = self._classify_extent(min_lon, max_lon, min_lat, max_lat)
        shape = self._classify_shape(min_lon, max_lon, min_lat, max_lat)
        lat_zone = self._classify_latitude_zone(min_lat, max_lat)
        lon_span = abs(max_lon - min_lon)
        lat_span = abs(max_lat - min_lat)
        is_small_area = lon_span <= 8.0 and lat_span <= 8.0
        candidates = []
        for proj in self.projections:
            # extent match
            if extent not in proj.suitable_extent:
                continue
            # shape match

            shape_match = (
                is_small_area
                or shape in proj.suitable_shape
                or "any" in proj.suitable_shape
            )
            lat_match = (
                lat_zone in proj.suitable_latitude or "any" in proj.suitable_latitude
            )
            if shape_match and lat_match:
                if (
                    preferred_distortion.lower() in proj.distortion_type.lower()
                    or preferred_distortion == "balanced"
                ):
                    candidates.append(proj)
        if not candidates and extent != "world":
            candidates = [p for p in self.projections if "any" in p.suitable_extent]

        if not candidates:
            return None

        # Score using airy's criterion based metrics
        results = []
        for proj in candidates:
            metrics = self.compute_metrics(proj, min_lon, max_lon, min_lat, max_lat)
            score = self._calculate_airys_based_score(
                metrics.avg_h, metrics.avg_k, preferred_distortion=preferred_distortion
            )
            results.append((proj, score))

        # Return best projections and score
        return sorted(results, key=lambda x: x[1])

    # ======================
    # CLASSIFICATION HELPERS
    # ======================
    def _classify_extent(
        self, min_lon: float, max_lon: float, min_lat: float, max_lat: float
    ) -> str:
        """Classify extent based on the scale of the map"""
        delta_lon = abs(max_lon - min_lon)
        if delta_lon >= 360:
            delta_lon = 360
        # Calculate the scale using the sine difference (area-based scale)
        sin_diff = abs(sin(radians(max_lat)) - sin(radians(min_lat)))
        if sin_diff < 1e-10:
            sin_diff = 1e-10

        if sin_diff == 0:
            return "continental"
        scale = 720 / (delta_lon * sin_diff)

        if scale < 1.5:
            return "world"
        elif scale < 6.0:
            return "hemisphere"
        else:
            return "continental"

    def _classify_shape(
        self, min_lon: float, max_lon: float, min_lat: float, max_lat: float
    ) -> str:
        lon_span = max_lon - min_lon
        lat_span = max_lat - min_lat

        # Calculate the height-to-width ratio adjusted for earth's curveture
        # This determines if the area is 'tall' or wide in real world
        if lon_span == 0:
            return "north-south"
        ratio = lat_span / lon_span

        # adjust for earth's curveture as the centre of the bounding box
        center_lat = (min_lat + max_lat) / 2
        adjusted_ratio = ratio / cos(radians(center_lat))

        if adjusted_ratio > 1.25:
            return "north-south"
        elif adjusted_ratio < 0.8:
            return "east-west"
        else:
            return "square"

    def _classify_latitude_zone(self, min_lat: float, max_lat: float) -> str:
        center_lat = (min_lat + max_lat) / 2
        max_abs = max(abs(min_lat), abs(max_lat))

        if max_abs > 75 or abs(center_lat) > 70:
            return "pole"
        elif abs(center_lat) < 20:
            return "equator"
        else:
            return "mid-latitudes"

    def _calculate_airys_based_score(
        self, h: float, k: float, preferred_distortion: str = "equal-area"
    ) -> float:
        # Logarithmic error is more mathematically sound than absolute difference
        area_penalty = abs(log(max(h * k, 1e-9)))
        shape_penalty = abs(log(max(h / k, 1e-9)))
        distance_penalty = sqrt((log(max(h, 1e-9)) ** 2 + log(max(k, 1e-9)) ** 2) / 2)
        # Weight the scores based on user input
        if preferred_distortion.lower() == "equal-area":
            return (area_penalty * 0.85) + (shape_penalty * 0.15)

        elif preferred_distortion.lower() == "conformal":
            return (shape_penalty * 0.85) + (area_penalty * 0.15)

        elif preferred_distortion.lower() == "equidistant":
            return distance_penalty

        else:  # 'Balanced' or 'Compromise'
            return (area_penalty + shape_penalty + distance_penalty) / 3
