#!/usr/bin/env python3
"""
fetch_map_tiles.py — Scarica le tile raster OpenTopoMap per il cerchio monitorato.

Le tile vengono servite dal nostro server (mount /map-tiles) e scaricate una
volta sola dall'app mobile, che poi le usa OFFLINE. Così gli utenti non
colpiscono mai OpenTopoMap: il fetch avviene qui, una volta, in modo controllato.

Sorgente:  OpenTopoMap ({a,b,c}.tile.opentopomap.org), zoom max 17.
Area:      cerchio AREA_LAT/AREA_LON/AREA_RADIUS_KM (da core.config, via env).
Output:    map_tiles/{z}/{x}/{y}.png  +  map_tiles/manifest.json

Uso:  python fetch_map_tiles.py
      Idempotente: salta le tile già presenti. Da lanciare sul VPS, off-peak.

Nota policy: OpenTopoMap è un servizio di volontari con fair-use severo. Questo
script è sequenziale, con User-Agent identificativo e una pausa fra le richieste.
NON parallelizzare e NON rilanciarlo a vuoto.
"""

import json
import math
import os
import time
import urllib.error
import urllib.request

from core.config import AREA_LAT, AREA_LON, AREA_RADIUS_KM

MIN_ZOOM = 12
MAX_ZOOM = 16
TILE_SIZE = 256
MARGIN_KM = 2.0          # allarga il clip di un margine per non tagliare i bordi
SLEEP_S = 0.2            # pausa fra i download (rispetto della policy OTM)
SUBDOMAINS = ("a", "b", "c")
USER_AGENT = "GrappaSafe/1.0 (+https://grappasafe.borant.eu; offline tile prefetch)"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "map_tiles")


def deg2num(lat, lon, z):
    lat_r = math.radians(lat)
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def num2deg(x, y, z):
    """Angolo NW della tile (x, y). Con x+0.5, y+0.5 si ottiene il centro."""
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def tiles_in_circle(z):
    """Enumera le (x, y) al livello z il cui centro cade nel cerchio + margine."""
    lat, lon, r = AREA_LAT, AREA_LON, AREA_RADIUS_KM + MARGIN_KM
    dlat = r / 111.0
    dlon = r / (111.0 * math.cos(math.radians(lat)))
    x0, y1 = deg2num(lat - dlat, lon - dlon, z)   # SW → x minima, y massima
    x1, y0 = deg2num(lat + dlat, lon + dlon, z)   # NE → x massima, y minima
    for x in range(min(x0, x1), max(x0, x1) + 1):
        for y in range(min(y0, y1), max(y0, y1) + 1):
            clat, clon = num2deg(x + 0.5, y + 0.5, z)
            if haversine_km(lat, lon, clat, clon) <= r:
                yield x, y


def download(z, x, y):
    dest_dir = os.path.join(OUT_DIR, str(z), str(x))
    dest = os.path.join(dest_dir, f"{y}.png")
    if os.path.exists(dest):
        return "skip"
    os.makedirs(dest_dir, exist_ok=True)
    sub = SUBDOMAINS[(x + y) % len(SUBDOMAINS)]
    url = f"https://{sub}.tile.opentopomap.org/{z}/{x}/{y}.png"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            with open(dest, "wb") as f:
                f.write(data)
            return "ok"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "missing"
            time.sleep(1.0 + attempt)
        except Exception:
            time.sleep(1.0 + attempt)
    return "fail"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plan = {z: list(tiles_in_circle(z)) for z in range(MIN_ZOOM, MAX_ZOOM + 1)}
    total = sum(len(v) for v in plan.values())
    print(f"GrappaSafe — fetch tile OpenTopoMap")
    print(f"  area: {AREA_RADIUS_KM} km attorno a {AREA_LAT:.5f},{AREA_LON:.5f}")
    print(f"  zoom: {MIN_ZOOM}-{MAX_ZOOM}  tile da scaricare: {total}")

    manifest_tiles = []
    done = ok = 0
    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        for x, y in plan[z]:
            res = download(z, x, y)
            done += 1
            if res in ("ok", "skip", "missing"):
                if res != "missing":
                    manifest_tiles.append([z, x, y])
                if res == "ok":
                    ok += 1
                    time.sleep(SLEEP_S)
            if done % 200 == 0:
                print(f"  {done}/{total}  (scaricate ora: {ok})")

    manifest = {
        "area": {"lat": AREA_LAT, "lon": AREA_LON, "radius_km": AREA_RADIUS_KM},
        "min_zoom": MIN_ZOOM,
        "max_zoom": MAX_ZOOM,
        "tile_size": TILE_SIZE,
        "count": len(manifest_tiles),
        "tiles": manifest_tiles,
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f)
    print(f"Done. Tile disponibili: {len(manifest_tiles)}  (nuove: {ok})")


if __name__ == "__main__":
    main()
