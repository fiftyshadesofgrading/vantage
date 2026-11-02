#!/usr/bin/env python3
"""
make_analysis.py — small, uniform working copies of every image, for analysis tools
(AI vision, quick previews, feature matching). Originals are never touched.

    python tools/make_analysis.py                 # art/library + art/originals → art/analysis (1568 px JPEG)
    python tools/make_analysis.py --size 1024     # smaller
    python tools/make_analysis.py --sheets        # also contact sheets (6×5 grids) per folder for fast triage
    python tools/make_analysis.py --clean         # delete art/analysis (it's all disposable)

Re-runs skip images that are already done and up to date. 1568 px on the long edge is
about the largest size vision models use without downscaling again; a typical copy is
300–600 KB instead of 10–500 MB. Needs Pillow:  pip install pillow
"""
import argparse, os, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIRS = [ROOT / "art" / "library", ROOT / "art" / "originals", ROOT / "art" / "inbox"]
OUT = ROOT / "art" / "analysis"
EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".jp2", ".webp"}

try:
    from PIL import Image, ImageOps, ImageDraw
    Image.MAX_IMAGE_PIXELS = 800_000_000
except ImportError:
    sys.exit("Needs Pillow:  pip install pillow   (for .jp2 files Pillow also needs OpenJPEG, which the normal wheels include)")


def to_rgb(im):
    im = ImageOps.exif_transpose(im)
    if im.mode in ("I;16", "I;16B", "I;16L", "I"):
        im = im.point(lambda v: v / 256).convert("L")
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); return bg
    return im.convert("RGB") if im.mode != "RGB" else im


def shrink(src: Path, dest: Path, size: int, quality: int):
    with Image.open(src) as im:
        if im.format == "JPEG":
            im.draft("RGB", (size, size))      # decode at reduced scale — much faster on huge JPEGs
        im = to_rgb(im)
        im.thumbnail((size, size), Image.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "JPEG", quality=quality, optimize=True, progressive=True)
        return im.size


def contact_sheets(folder: Path, cols=6, rows=5, cell=300):
    imgs = sorted(p for p in folder.glob("*.jpg") if not p.name.startswith("_sheet"))
    per = cols * rows
    for n in range(0, len(imgs), per):
        sheet = Image.new("RGB", (cols * cell, rows * (cell + 22)), (245, 240, 230))
        d = ImageDraw.Draw(sheet)
        for i, p in enumerate(imgs[n:n + per]):
            with Image.open(p) as im:
                im.thumbnail((cell - 8, cell - 8))
                x, y = (i % cols) * cell, (i // cols) * (cell + 22)
                sheet.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
                d.text((x + 4, y + cell + 4), f"{n + i + 1}. {p.stem[:44]}", fill=(30, 30, 30))
        sheet.save(folder / f"_sheet{n // per + 1:02d}.jpg", quality=85)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--size", type=int, default=1568, help="long edge in px (default 1568)")
    ap.add_argument("--quality", type=int, default=85)
    ap.add_argument("--sheets", action="store_true", help="also write contact sheets per folder")
    ap.add_argument("--clean", action="store_true", help="delete art/analysis and stop")
    a = ap.parse_args()
    if a.clean:
        shutil.rmtree(OUT, ignore_errors=True); print(f"removed {OUT.relative_to(ROOT)}"); return
    files = [p for d in SRC_DIRS if d.exists() for p in d.rglob("*")
             if p.suffix.lower() in EXTS and "_thumbs" not in p.parts and "_rejects" not in p.parts and not p.name.endswith(".part")]
    print(f"{len(files)} source images")
    done = skipped = failed = 0; t0 = time.time(); folders = set()
    for i, src in enumerate(files, 1):
        rel = src.relative_to(ROOT / "art")
        dest = (OUT / rel).with_suffix(".jpg")
        folders.add(dest.parent)
        if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
            skipped += 1; continue
        try:
            w, h = shrink(src, dest, a.size, a.quality)
            done += 1
            print(f"[{i}/{len(files)}] {rel}  →  {w}×{h}  {dest.stat().st_size / 1e3:.0f} KB")
        except Exception as e:
            failed += 1; print(f"[{i}/{len(files)}] ✗ {rel}: {type(e).__name__}: {e}")
    if a.sheets:
        for f in sorted(folders):
            if f.exists():
                contact_sheets(f)
        print(f"contact sheets written in {len(folders)} folders")
    total = sum(p.stat().st_size for p in OUT.rglob("*.jpg")) if OUT.exists() else 0
    print(f"\n{done} made, {skipped} already current, {failed} failed — art/analysis is {total / 1e6:.0f} MB ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
