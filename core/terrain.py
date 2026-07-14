"""
Terrain elevation.

Reads SRTM1 tiles (1 arc-second, ~30m) in the binary HGT format, with no
external dependencies. Two tiles cover the monitoring area:

  tiles/N45E011.hgt   (lat 45-46, lon 11-12)
  tiles/N45E012.hgt   (lat 45-46, lon 12-13)

Download them once with ./fetch_tiles.sh.
"""

import math
import struct
from functools import lru_cache
from pathlib import Path
from typing import Optional

# SRTM1 format constants
SAMPLES   = 3601                    # samples per side (0..3600 degrees inclusive)
TILE_SIZE = SAMPLES * SAMPLES * 2   # bytes per tile
NODATA    = -32768                  # "no data" marker in the HGT format

# Tile directory, relative to this file
_TILE_DIR = Path(__file__).parent.parent / "tiles"


def _tile_name(lat_floor: int, lon_floor: int) -> str:
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"{ns}{abs(lat_floor):02d}{ew}{abs(lon_floor):03d}.hgt"


def _load_tile(lat_floor: int, lon_floor: int) -> Optional[bytes]:
    path = _TILE_DIR / _tile_name(lat_floor, lon_floor)
    if not path.exists():
        return None
    data = path.read_bytes()
    if len(data) != TILE_SIZE:
        return None
    return data


# In-memory tiles: only two files for the whole area (~52 MB total).
_tiles: dict[tuple[int, int], Optional[bytes]] = {}


def _get_tile(lat_floor: int, lon_floor: int) -> Optional[bytes]:
    key = (lat_floor, lon_floor)
    if key not in _tiles:
        _tiles[key] = _load_tile(lat_floor, lon_floor)
        if _tiles[key] is None:
            name = _tile_name(lat_floor, lon_floor)
            print(f"  [terrain] WARN: tile {name} not found in {_TILE_DIR}")
    return _tiles[key]


@lru_cache(maxsize=65536)
def get_elevation(lat: float, lon: float) -> Optional[float]:
    """
    Terrain elevation in metres AMSL at (lat, lon).
    Input is rounded to 4 decimals (~11m). Returns None if the tile is
    missing or the point is NODATA.
    """
    lat_r = round(lat, 4)
    lon_r = round(lon, 4)

    lat_floor = math.floor(lat_r)
    lon_floor = math.floor(lon_r)

    tile = _get_tile(lat_floor, lon_floor)
    if tile is None:
        return None

    # Fraction inside the tile (0.0 = SW, 1.0 = NE)
    frac_lat = lat_r - lat_floor   # 0.0 (south) -> 1.0 (north)
    frac_lon = lon_r - lon_floor   # 0.0 (west) -> 1.0 (east)

    # Row 0 is the tile's northernmost latitude
    row = round((1.0 - frac_lat) * (SAMPLES - 1))
    col = round(frac_lon * (SAMPLES - 1))

    row = max(0, min(SAMPLES - 1, row))
    col = max(0, min(SAMPLES - 1, col))

    offset = (row * SAMPLES + col) * 2
    value  = struct.unpack_from(">h", tile, offset)[0]

    return None if value == NODATA else float(value)


def compute_agl(lat: float, lon: float, alt_amsl: float) -> float:
    """
    Height above ground level, in metres.
    Fallback: if the tile is missing, return alt_amsl unchanged so the SM keeps
    working with reduced accuracy.
    """
    elev = get_elevation(lat, lon)
    if elev is None:
        return alt_amsl
    return max(0.0, alt_amsl - elev)


def tiles_ok() -> bool:
    """True if both tiles load correctly."""
    needed = [(45, 11), (45, 12)]
    return all(_get_tile(lat, lon) is not None for lat, lon in needed)
