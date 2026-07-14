#!/usr/bin/env bash
# fetch_tiles.sh — Scarica le tile SRTM1 per l'area Grappa.
#
# Sorgente: AWS elevation-tiles-prod (Tilezen/Mapzen, pubblico, no auth)
# Formato:  HGT gzippato → decompresso in tiles/
# Tile:     N45E011.hgt + N45E012.hgt  (~26MB ciascuna)
#
# Uso: ./fetch_tiles.sh
#      Idempotente: salta i file già presenti.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TILE_DIR="$SCRIPT_DIR/tiles"
BASE_URL="https://elevation-tiles-prod.s3.amazonaws.com/skadi"

mkdir -p "$TILE_DIR"

download_tile() {
    local name="$1"        # es. N45E011
    local lat_dir="$2"     # es. N45
    local dest="$TILE_DIR/${name}.hgt"

    if [ -f "$dest" ]; then
        echo "  [skip] ${name}.hgt già presente"
        return
    fi

    local url="${BASE_URL}/${lat_dir}/${name}.hgt.gz"
    echo "  [download] ${name}.hgt.gz ..."
    curl -fsSL "$url" | gunzip > "$dest"
    local size
    size=$(du -sh "$dest" | cut -f1)
    echo "  [ok] ${name}.hgt  ($size)"
}

echo "GrappaSafe — fetch tile SRTM1 (area Grappa)"
download_tile "N45E011" "N45"
download_tile "N45E012" "N45"
echo "Done."
