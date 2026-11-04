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
# bring the clone up to date BEFORE copying (edits made on GitHub, e.g. the coffee link, would otherwise reject the push)
if [ -n "$(git -C "$DEST" status --porcelain)" ]; then
  echo "The clone at $DEST has uncommitted changes. Commit or discard them (git -C \"$DEST\" status), then re-run."; exit 1
fi
if ! git -C "$DEST" pull -q --rebase; then
  echo "git pull failed in $DEST (see above). Fix that, then re-run."; exit 1
fi
# files edited on GitHub since the last publish would be overwritten by the NAS copy: stop and say which
LAST="$(git -C "$DEST" log -1 --format=%H --grep='^Publish ' || true)"
if [ -n "$LAST" ]; then
  REMOTE_EDITS="$(git -C "$DEST" diff --name-only "$LAST" HEAD -- . ':!CNAME' ':!.nojekyll')"
  if [ -n "$REMOTE_EDITS" ] && [ "${FORCE:-0}" != "1" ]; then
    echo "These files were changed on GitHub since the last publish and would be overwritten:"
    echo "$REMOTE_EDITS" | sed 's/^/  /'
    echo "Copy those edits into the NAS folder ($SRC) first, then re-run with FORCE=1."; exit 1
  fi
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
du -sh --exclude=.git . | sed 's/^/size: /'
git add -A
git commit -q -m "Publish $(date +%F)" && echo "committed" || echo "nothing new to commit"
git push -q -u origin HEAD && echo "pushed — live in a minute or two" || { echo "push failed — try: git -C \"$DEST\" pull --rebase && git -C \"$DEST\" push"; exit 1; }
