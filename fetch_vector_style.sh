#!/usr/bin/env bash
# Scarica gli asset dello stile "OpenTopoMap vector" (layer + sprite) in
# vector_style/, serviti poi da app.py (/vector-style.json + /vector-style/*).
# Stack aperto: der-stefan/OpenTopoMap, licenza CC-BY-SA.
set -euo pipefail
cd "$(dirname "$0")"

DIR="vector_style"
BASE="https://raw.githubusercontent.com/der-stefan/OpenTopoMap/master/vector/maplibregljs"
mkdir -p "$DIR"

# Obbligatori: i 63 layer + lo sprite base.
REQUIRED="otm_layers.json otm_sprite.json otm_sprite.png"
# Opzionali: sprite retina (potrebbero non esistere).
OPTIONAL="otm_sprite@2x.json otm_sprite@2x.png"

get() {
  local f="$1" required="$2"
  if curl -fsSL "$BASE/$f" -o "$DIR/$f.tmp"; then
    mv "$DIR/$f.tmp" "$DIR/$f"
    echo "  ok   $f"
  else
    rm -f "$DIR/$f.tmp"
    if [ "$required" = "1" ]; then
      echo "  FAIL $f (obbligatorio)" >&2
      exit 1
    fi
    echo "  skip $f (assente)"
  fi
}

echo "Scarico lo stile OTM in $DIR/ ..."
for f in $REQUIRED; do get "$f" 1; done
for f in $OPTIONAL; do get "$f" 0; done

echo "Done. Stile pronto: /vector-style.json + sprite su /vector-style/otm_sprite"
