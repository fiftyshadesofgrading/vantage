#!/usr/bin/env bash
# publish.sh — copy the public parts of Vantage into the GitHub Pages clone and push.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$HOME/sites/vantage}"
[ -d "$DEST/.git" ] || { echo "No git clone at $DEST"; exit 1; }
rsync -a --delete \
  --exclude '.git/' --exclude 'CNAME' --exclude '.nojekyll' \
  --exclude 'art/library/' --exclude 'art/originals/' --exclude 'art/analysis/' --exclude 'art/inbox/' \
  --exclude 'art/full/' --exclude 'art/web/' --exclude 'art/thumbs/' \
  --exclude 'harvest/' --exclude '__pycache__/' --exclude '*.part' \
  "$SRC/" "$DEST/"
printf '{\n "generated": null,\n "items": {}\n}\n' > "$DEST/data/local.json"
touch "$DEST/.nojekyll"
cd "$DEST"
du -sh --exclude=.git . | sed 's/^/size: /'
git add -A
git commit -q -m "Publish $(date +%F)" && echo "committed" || echo "nothing new to commit"
git push -q -u origin main && echo "pushed — live in a minute or two"
