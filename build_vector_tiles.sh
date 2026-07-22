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
#   tilemaker   — https://github.com/systemed/tilemaker  (apt: tilemaker, o build)
#   osmium      — apt install osmium-tool
#   wget, git, python3 (già presenti)
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
for tool in tilemaker osmium wget git python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "MANCA: $tool — installalo prima."; exit 1; }
done

# --- 1. Bbox dal config reale (55x55 km attorno al centro monitorato) ---------
# Riusa core.config (AREA_LAT/LON) così resta in sync col resto del server.
# BOX_HALF_KM = mezzo lato del quadrato vettoriale (27.5 -> lato 55 km): margine
# ~8.5 km oltre il cerchio (raggio 19), così il giunto raster/vettoriale è lontano.
read -r WEST SOUTH EAST NORTH <<EOF
$(BOX_HALF_KM="${BOX_HALF_KM:-27.5}" python3 - <<'PY'
import math, os
from core.config import AREA_LAT, AREA_LON
half = float(os.environ["BOX_HALF_KM"])
dlat = half / 111.0
dlon = half / (111.0 * math.cos(math.radians(AREA_LAT)))
print(f"{AREA_LON-dlon:.6f} {AREA_LAT-dlat:.6f} {AREA_LON+dlon:.6f} {AREA_LAT+dlat:.6f}")
PY
)
EOF
echo "GrappaSafe — build tile vettoriali"
echo "  bbox 55x55: W=$WEST S=$SOUTH E=$EAST N=$NORTH"

# --- 2. Config Tilemaker di OpenTopoMap (schema Shortbread-OTM + stile) --------
# Cloniamo shallow il repo OTM solo per prendere vector/tilemaker/*.
OTM_DIR="$WORK/OpenTopoMap"
if [ ! -d "$OTM_DIR/.git" ]; then
  echo "  clono la config vettoriale di OpenTopoMap..."
  git clone --depth 1 https://github.com/der-stefan/OpenTopoMap.git "$OTM_DIR"
else
  git -C "$OTM_DIR" pull --ff-only || true
fi
TM_DIR="$OTM_DIR/vector/tilemaker"
TM_CONFIG="$TM_DIR/tilemaker-config-otm.json"
TM_LUA="$TM_DIR/process-otm.lua"
[ -f "$TM_CONFIG" ] && [ -f "$TM_LUA" ] || {
  echo "Config OTM non trovata in $TM_DIR — struttura repo cambiata? Controlla."; exit 1; }

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
  --output "$MBTILES" \
  --store "$WORK/tilemaker.store.d" --shard-stores

echo "Done. mbtiles: $MBTILES"
echo "Prossimo: incremento 2 (curve di livello + hillshade dal DEM in tiles/)."
