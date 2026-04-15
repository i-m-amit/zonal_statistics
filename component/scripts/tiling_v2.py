# file: tiling_prepare.py
from __future__ import annotations

import hashlib
import logging
import os
import pathlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, Dict

import rasterio as rio

log = logging.getLogger(__name__)

# ----------------------------
# Configuration
# ----------------------------

@dataclass
class COGConfig:
    block_size: int = 512
    compress: str = "DEFLATE"
    predictor: str = "2"
    level: str = "6"
    threads: str = "ALL_CPUS"


CFG = COGConfig()


# ----------------------------
# Utilities
# ----------------------------

def _hash_for_cache(path: str) -> str:
    st = os.stat(path)
    h = hashlib.sha1()
    h.update(path.encode())
    h.update(str(st.st_size).encode())
    h.update(str(int(st.st_mtime)).encode())
    return h.hexdigest()[:16]


def _gdal_ok() -> bool:
    return all(shutil.which(cmd) for cmd in ["gdalinfo", "gdal_translate", "gdaladdo"])


def _is_categorical(ds: rio.io.DatasetReader) -> bool:
    if ds.count != 1:
        return False

    dtype = ds.dtypes[0]
    if not dtype.startswith(("int", "uint")):
        return False

    # Better heuristic: check colormap or low value range
    try:
        if ds.colormap(1):
            return True
    except Exception:
        pass

    return False


def _has_overviews(ds) -> bool:
    return any(ds.overviews(i + 1) for i in range(ds.count))


def _is_tiled(ds) -> bool:
    try:
        bs = ds.block_shapes
        return bool(bs and all(b[0] > 1 and b[1] > 1 for b in bs))
    except Exception:
        return False


def _needs_reproject(ds, target_epsg: Optional[int]) -> bool:
    if not target_epsg or not ds.crs:
        return False
    try:
        return ds.crs.to_epsg() != target_epsg
    except Exception:
        return True


def _target_overview_levels(width: int, height: int, block: int = 512):
    levels = []
    longest = max(width, height)
    lvl = 2
    while longest / lvl > block:
        levels.append(lvl)
        lvl *= 2
    return levels or [2, 4, 8, 16]


# ----------------------------
# Analysis
# ----------------------------

def analyze_tif(path: str) -> Dict:
    with rio.open(path) as ds:
        return {
            "path": path,
            "crs": str(ds.crs),
            "epsg": ds.crs.to_epsg() if ds.crs else None,
            "width": ds.width,
            "height": ds.height,
            "bands": ds.count,
            "dtype": ds.dtypes[0],
            "tiled": _is_tiled(ds),
            "overviews": [ds.overviews(i + 1) for i in range(ds.count)],
            "categorical_guess": _is_categorical(ds),
        }


# ----------------------------
# GDAL operations
# ----------------------------

def _run(cmd: list[str]):
    log.debug("Running: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        log.error("GDAL command failed:\n%s", e.stderr)
        raise


def _build_overviews_inplace(path: str, categorical: bool):
    resamp = "nearest" if categorical else "average"

    with rio.open(path) as ds:
        levels = _target_overview_levels(ds.width, ds.height)

    try:
        with rio.open(path, "r+") as ds:
            ds.build_overviews(levels, resampling=resamp)
            ds.update_tags(ns="rio_overview", resampling=resamp)
    except Exception:
        if not shutil.which("gdaladdo"):
            raise

        _run([
            "gdaladdo",
            "-r", resamp.upper(),
            "--config", "COMPRESS_OVERVIEW", "DEFLATE",
            "--config", "PREDICTOR_OVERVIEW", "2",
            path,
            *map(str, levels),
        ])


def _translate_to_cog(src: str, dst: str, resampling: str):
    _run([
        "gdal_translate",
        src,
        dst,
        "-of", "COG",
        "-co", f"COMPRESS={CFG.compress}",
        "-co", f"LEVEL={CFG.level}",
        "-co", f"PREDICTOR={CFG.predictor}",
        "-co", f"BLOCKSIZE={CFG.block_size}",
        "-co", f"NUM_THREADS={CFG.threads}",
        "-co", f"RESAMPLING={resampling}",
    ])


def _warp_to_epsg(src: str, dst: str, epsg: int, resampling: str):
    _run([
        "gdalwarp",
        "-overwrite",
        "-t_srs", f"EPSG:{epsg}",
        "-r", resampling,
        "-multi",
        "-wo", f"NUM_THREADS={CFG.threads}",
        "-co", "TILED=YES",
        "-co", f"BLOCKXSIZE={CFG.block_size}",
        "-co", f"BLOCKYSIZE={CFG.block_size}",
        "-co", f"COMPRESS={CFG.compress}",
        "-co", f"PREDICTOR={CFG.predictor}",
        "-co", "BIGTIFF=IF_SAFER",
        src,
        dst,
    ])


# ----------------------------
# Main API
# ----------------------------

def prepare_for_tiles(
    path: str,
    cache_dir: Optional[str] = None,
    warp_to_3857: bool = False,
    force: bool = False,
) -> Dict:

    path = os.path.abspath(path)

    with rio.open(path) as ds:
        rep = {
            **analyze_tif(path),
            "needs_reproj": _needs_reproject(ds, 3857) if warp_to_3857 else False,
            "has_ovr": _has_overviews(ds),
        }

    categorical = rep["categorical_guess"]
    resamp = "NEAREST" if categorical else "AVERAGE"

    good_enough = rep["tiled"] and rep["has_ovr"] and not rep["needs_reproj"]

    if good_enough and not force:
        return {"path": path, "report": rep}

    cache_dir = cache_dir or os.path.join(pathlib.Path.home(), ".cache", "localtiles")
    os.makedirs(cache_dir, exist_ok=True)

    tag = _hash_for_cache(path)
    base = os.path.join(cache_dir, f"{os.path.basename(path)}.{tag}")

    if _gdal_ok():
        out = base + (".3857.cog.tif" if warp_to_3857 else ".cog.tif")

        if warp_to_3857:
            inter = base + ".warp.tif"
            _warp_to_epsg(path, inter, 3857, resamp)
            _translate_to_cog(inter, out, resamp)
            try:
                os.remove(inter)
            except OSError:
                pass
        else:
            _translate_to_cog(path, out, resamp)

        return {"path": out, "report": analyze_tif(out)}

    else:
        dst = base + ".ovr.tif"
        shutil.copy2(path, dst)
        _build_overviews_inplace(dst, categorical)

        return {"path": dst, "report": analyze_tif(dst)}
