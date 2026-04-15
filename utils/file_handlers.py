# utils/file_handlers.py

import zipfile
from pathlib import Path


def save_vector_files(files, tmpdir: Path):
    """Handles .zip(shapefile), .geojson, .gpkg"""
    if len(files) == 1:
        f = files[0]
        data = f.data
        name = f.name.lower()

        if name.endswith(".zip"):
            zip_path = tmpdir / "vector.zip"
            zip_path.write_bytes(data)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(tmpdir)
            shp = next(tmpdir.rglob("*.shp"), None)
            if not shp:
                raise ValueError("No .shp found in zip or it is corrupted")
            return shp
        ext = ".geojson" if name.endswith(".geojson") else ".gpkg"
        path = tmpdir / f"vector{ext}"
        path.write_bytes(data)
        return path
    else:
        # aux files for .shp
        for f in files:
            (tmpdir / f.name).write_bytes(f.data)
        return next(tmpdir.rglob("*.shp"))
