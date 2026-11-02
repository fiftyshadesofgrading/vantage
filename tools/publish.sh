#!/usr/bin/env bash
# publish.sh — copy the public parts of Vantage into a git clone of the GitHub Pages repo and push.
#
#   tools/publish.sh                      # uses ~/sites/vantage
#   tools/publish.sh /path/to/clone
#
# Leaves out the heavy / private stuff: harvested library, originals, analysis copies,
# local high-res derivatives and the harvest folder. Images then load from Commons and
# the museums (the app does that automatically when data/local.json is empty).
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$HOME/sites/vantage}"
if [ ! -d "$DEST/.git" ]; then
  echo "No git clone at $DEST. First:  git clone git@github.com:fiftyshadesofgrading/vantage.git \"$DEST\""; exit 1
fi
rsync -a --delete \
  --exclude '.git/' --exclude 'CNAME' --exclude '.nojekyll' \
  --exclude 'art/library/' --exclude 'art/originals/' --exclude 'art/analysis/' --exclude 'art/inbox/' \
  --exclude 'art/full/' --exclude 'art/web/' --exclude 'art/thumbs/' \
  --exclude 'harvest/' --exclude '__pycache__/' --exclude '*.part' --exclude '*.png~' \
  "$SRC/" "$DEST/"
printf '{\n "generated": null,\n "items": {}\n}\n' > "$DEST/data/local.json"   # public site: no local copies
touch "$DEST/.nojekyll"                                                          # serve files as-is (no Jekyll)
cd "$DEST"
git pull -q --rebase 2>/dev/null || true          # pick up anything GitHub committed (e.g. CNAME)
du -sh --exclude=.git . | sed 's/^/size: /'
git add -A
git commit -q -m "Publish $(date +%F)" && echo "committed" || echo "nothing new to commit"
git push -q -u origin HEAD && echo "pushed — live in a minute or two"
