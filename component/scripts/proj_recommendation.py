"""
Advanced Projection Recommender and WKT generation.
Inspired by Projection Wizard.
"""

from typing import List, Optional, Dict
import numpy as np
import pyproj
from pyproj import CRS, Geod
from math import radians, degrees, sin, sqrt, asin, cos, log
from component.scripts.proj_util import projection_template, Projection, Bounds

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
    def __init__(self, bounds: Bounds, preferred_distortion: str = "equal-area"):
        self.bounds = bounds
        self.projections: List[Projection] = self._init_projections()

    def _init_projections(self) -> List[Projection]:
        return projection_template

    # ======================
    # METRICS CALCULATION
    # ======================
    def compute_metrics(self, proj: Projection) -> DistortionMetrics:
        """Tissot's indicatrix calculation."""
        try:
            params = self._calculate_parameters()
            proj4_str = proj.proj4_template.format(**params)
            proj_obj = pyproj.Proj(proj4_str)

            # Better sampling grid - avoid edges and poles
            lons = np.linspace(self.bounds.min_lon + 0.1, self.bounds.max_lon - 0.1, 7)
            lats = np.linspace(self.bounds.min_lat + 0.1, self.bounds.max_lat - 0.1, 7)

            angle_dists, dist_dists, k_s, h_s = [], [], [], []
            geod = Geod(ellps="WGS84")
            total_weight = 0
            weighted_area_dist = 0

            for lat in lats:
                weight = cos(radians(lat))
                for lon in lons:
                    if abs(lat) > 89:  # Skip near poles
                        continue

                    # Base point
                    x, y = proj_obj(lon, lat)

                    # North displacement (1km)
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
                    weighted_area_dist += abs(area_scale - 1.0) * weight
                    total_weight += weight

                    # Angular distortion in degrees
                    if h + k > 1e-8:
                        angle_dists.append(degrees(2 * asin(abs(h - k) / (h + k))))

                    # Distance distortion
                    dist_dists.append(abs((h + k) / 2 - 1.0))

            if total_weight == 0:
                return DistortionMetrics(float("inf"))

            avg_h, avg_k = np.mean(h_s), np.mean(k_s)

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
            return DistortionMetrics(float("inf"))

    def _calculate_parameters(self) -> dict:
        """Calculate projection parameters"""
        b = self.bounds
        central_meridian = round((b.min_lon + b.max_lon) / 2, 4)
        lat_0 = round((b.min_lat + b.max_lat) / 2, 4)

        # The one-sixth rule for standard parallels
        lat_diff = b.max_lat - b.min_lat
        one_sixth = lat_diff / 6.0

        lat_1 = round(b.min_lat + one_sixth, 4)
        lat_2 = round(b.max_lat - one_sixth, 4)

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
            params = self._calculate_parameters()  # default safe params
            proj4_str = proj.proj4_template.format(**params)
            crs = CRS.from_proj4(proj4_str)
            return crs.to_wkt(pretty=True)
        except Exception as e:
            return f"ERROR generating WKT for {proj.name}: {str(e)}"

    # ======================
    # MAIN RECOMMENDATION
    # ======================
    def recommond_projections(
        self,
        preferred_distortion: str = "Balanced",
    ) -> Optional[List[Dict]]:
        """Main projection  recommendation engine"""

        extent = self._classify_extent()
        shape = self._classify_shape()
        lat_zone = self._classify_latitude_zone()
        is_small_area = self.bounds.lon_span <= 6.0 and self.bounds.lat_span <= 6.0
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
            return []
        params = self._calculate_parameters()

        # Score using airy's criterion based metrics
        results = []
        for proj in candidates:
            proj4_str = proj.proj4_template.format(**params)
            m = self.compute_metrics(proj)
            score = self._calculate_airys_based_score(
                m.avg_h, m.avg_k, preferred_distortion=preferred_distortion
            )
            results.append(
                {
                    "name": proj.name,
                    "proj4": proj4_str,
                    "score": round(score, 6),
                    "area_distortion": m.avg_area_distortion,
                    "angle_distortion": m.avg_angular_distortion,
                    "distance_distortion": m.avg_distance_distortion,
                }
            )

        # Return best projections and score
        return sorted(results, key=lambda x: x["score"])

    # ======================
    # CLASSIFICATION HELPERS
    # ======================
    def _classify_extent(self) -> str:
        """Classify extent based on the scale of the map"""

        delta_lon = self.bounds.lon_span
        # Calculate the scale using the sine difference (area-based scale)
        sin_diff = abs(
            sin(radians(self.bounds.max_lat)) - sin(radians(self.bounds.min_lat))
        )
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

    def _classify_shape(self) -> str:

        # Calculate the height-to-width ratio adjusted for earth's curveture
        # This determines if the area is 'tall' or wide in real world
        ratio = self.bounds.lat_span / max(self.bounds.lon_span, 1e-9)

        # adjust for earth's curveture as the centre of the bounding box
        center_lat = (self.bounds.min_lat + self.bounds.max_lat) / 2
        adjusted_ratio = ratio / cos(radians(center_lat))

        if adjusted_ratio > 1.25:
            return "north-south"
        elif adjusted_ratio < 0.8:
            return "east-west"
        else:
            return "square"

    def _classify_latitude_zone(self) -> str:
        center_lat = (self.bounds.min_lat + self.bounds.max_lat) / 2
        max_abs = max(abs(self.bounds.min_lat), abs(self.bounds.max_lat))

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
