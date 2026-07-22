#!/usr/bin/env bash
#
# build_vector_tiles.sh — Genera le tile VETTORIALI dell'area monitorata,
# riproducendo lo stack OpenTopoMap-vector (Tilemaker + schema Shortbread-OTM)
# ristretto al nostro bbox. Da lanciare sul VPS, off-peak.
#
# Diverso da fetch_map_tiles.py (che SCARICA PNG raster già renderizzati da OTM):
# qui le tile si GENERANO da dati OSM grezzi. Servono tool esterni (vedi sotto).
#
# Output:
#   vector_tiles/area.mbtiles     — tile vettoriali (.pbf) dell'area, schema OTM
#   (servite poi da FastAPI su /vector-tiles/{z}/{x}/{y}.pbf, vedi app.py)
#
# INCREMENTO 1 di 4: solo la base OSM vettoriale. Curve di livello + hillshade
# (dal DEM SRTM in tiles/) e glyphs/sprite/stile arrivano negli incrementi 2-3.
#
# --- Dipendenze sul VPS (una tantum) -----------------------------------------
#   tilemaker   — RECENTE, buildato da sorgente. La versione apt è troppo vecchia
#                 per la config/lua di OpenTopoMap (mancano Holds() e
#                 --shard-stores). https://github.com/systemed/tilemaker#compiling
#   osmium      — apt install osmium-tool
#   wget, python3 (già presenti)
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

WORK="$SCRIPT_DIR/vector_build"       # scratch: estratti OSM, config, store
OUT="$SCRIPT_DIR/vector_tiles"        # output servito
mkdir -p "$WORK" "$OUT"

# Estratto regionale: nord-est Italia copre Grappa (Veneto/Trentino). ~200 MB,
# non l'intera Europa. Aggiornalo cambiando l'URL se serve.
GEOFABRIK_URL="https://download.geofabrik.de/europe/italy/nord-est-latest.osm.pbf"
REGION_PBF="$WORK/nord-est-latest.osm.pbf"
AREA_PBF="$WORK/area.osm.pbf"
MBTILES="$OUT/area.mbtiles"

# --- 0. Preflight -------------------------------------------------------------
for tool in tilemaker osmium wget python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "MANCA: $tool — installalo prima."; exit 1; }
done

# --- 1. Bbox dal config reale (55x55 km attorno al centro monitorato) ---------
# Riusa core.config (AREA_LAT/LON) così resta in sync col resto del server.
# BOX_HALF_KM = mezzo lato del quadrato vettoriale (27.5 -> lato 55 km): margine
# ~8.5 km oltre il cerchio (raggio 19), così il giunto raster/vettoriale è lontano.
BBOX="$(BOX_HALF_KM="${BOX_HALF_KM:-27.5}" python3 -c '
import math, os
from core.config import AREA_LAT, AREA_LON
half = float(os.environ["BOX_HALF_KM"])
dlat = half / 111.0
dlon = half / (111.0 * math.cos(math.radians(AREA_LAT)))
print(f"{AREA_LON-dlon:.6f} {AREA_LAT-dlat:.6f} {AREA_LON+dlon:.6f} {AREA_LAT+dlat:.6f}")
')"
[ -n "$BBOX" ] || { echo "ERRORE: calcolo bbox fallito (python3 / core.config non importabile?)."; exit 1; }
read -r WEST SOUTH EAST NORTH <<< "$BBOX"
echo "GrappaSafe — build tile vettoriali"
echo "  bbox 55x55: W=$WEST S=$SOUTH E=$EAST N=$NORTH"

# --- 2. Config Tilemaker di OpenTopoMap (schema Shortbread-OTM) ----------------
# Scarico solo i due file (config + lua) da raw GitHub: niente clone del repo
# intero (grosso). La config OTM referenzia 3 shapefile esterni (oceano/coste +
# admin points) che qui NON servono: siamo inland (Grappa), quelle layer sarebbero
# vuote e mancherebbero -> tilemaker fallirebbe all'avvio. Le rimuovo dalla config
# così gira col solo .osm.pbf, senza scaricare ~1 GB di poligoni marini.
TM_BASE="https://raw.githubusercontent.com/der-stefan/OpenTopoMap/master/vector/tilemaker"
TM_LUA="$WORK/process-otm.lua"
TM_CONFIG_ORIG="$WORK/tilemaker-config-otm.json"
TM_CONFIG="$WORK/tilemaker-config-inland.json"
echo "  scarico config Tilemaker OTM..."
wget -qO "$TM_LUA"         "$TM_BASE/process-otm.lua"
wget -qO "$TM_CONFIG_ORIG" "$TM_BASE/tilemaker-config-otm.json"
[ -s "$TM_LUA" ] && [ -s "$TM_CONFIG_ORIG" ] || { echo "ERRORE: download config OTM fallito."; exit 1; }

python3 - "$TM_CONFIG_ORIG" "$TM_CONFIG" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
cfg = json.load(open(src))
layers = cfg.get("layers", {})
removed = [n for n, l in layers.items()
           if isinstance(l, dict) and str(l.get("source", "")).endswith(".shp")]
for n in removed:
    del layers[n]
json.dump(cfg, open(dst, "w"))
print("  layer shapefile rimosse (inland):", ", ".join(removed) or "nessuna")
PY

# --- 3. Scarica l'estratto regionale (idempotente) ----------------------------
if [ ! -f "$REGION_PBF" ]; then
  echo "  scarico $GEOFABRIK_URL ..."
  wget -q --show-progress -O "$REGION_PBF" "$GEOFABRIK_URL"
fi

# --- 4. Ritaglia il bbox: molto piu' veloce che tilemakerare tutta la regione -
echo "  osmium extract del bbox..."
osmium extract -b "$WEST,$SOUTH,$EAST,$NORTH" "$REGION_PBF" -o "$AREA_PBF" --overwrite

# --- 5. Genera le vector tile con la config OTM -------------------------------
echo "  tilemaker (schema OTM) -> $MBTILES ..."
rm -f "$MBTILES"
tilemaker \
  --config "$TM_CONFIG" \
  --process "$TM_LUA" \
  --input "$AREA_PBF" \
  --output "$MBTILES"

echo "Done. mbtiles: $MBTILES"
echo "Prossimo: incremento 2 (curve di livello + hillshade dal DEM in tiles/)."
