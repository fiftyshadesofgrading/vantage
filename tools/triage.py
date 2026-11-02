#!/usr/bin/env python3
"""
triage.py — act on harvest/shortlist.tsv and harvest/rejects.tsv

    python3 tools/triage.py shortlist     # copy shortlisted analysis JPEGs to art/analysis/_shortlist/<tier>/ + contact sheets
    python3 tools/triage.py rejects       # MOVE rejected originals (+ sidecars) to art/library/_rejects/ (nothing deleted)
    python3 tools/triage.py restore       # move everything in _rejects back where it came from

Tiers: A = paintings/drawings at a findable place, B = prints, sketchbook pages, maps,
P = historic photographs of named landmarks (best for exact then/now alignment).
"""
import csv, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB, ANA, H = ROOT / "art" / "library", ROOT / "art" / "analysis", ROOT / "harvest"
REJ = LIB / "_rejects"


def rows(name):
    with open(H / name, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def shortlist():
    out = ANA / "_shortlist"; shutil.rmtree(out, ignore_errors=True)
    n = miss = 0
    for i, r in enumerate(rows("shortlist.tsv"), 1):
        src = ANA / "library" / r["region"] / r["source"] / f"{r['file']}.jpg"
        if not src.exists():
            miss += 1; continue
        d = out / r["tier"]; d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, d / f"{i:03d}_{r['region'][:4]}_{r['file'][:60]}.jpg"); n += 1
    print(f"{n} copied to {out.relative_to(ROOT)} ({miss} had no analysis copy)")
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from make_analysis import contact_sheets
        for d in sorted(out.iterdir()):
            contact_sheets(d)
        print("contact sheets: art/analysis/_shortlist/<tier>/_sheetNN.jpg")
    except Exception as e:
        print("contact sheets skipped:", e)


def rejects():
    n = 0
    for r in rows("rejects.tsv"):
        folder = LIB / r["region"] / r["source"]
        for f in folder.glob(f"{r['file']}.*"):
            dest = REJ / r["region"] / r["source"] / f.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), dest); n += 1
        a = ANA / "library" / r["region"] / r["source"] / f"{r['file']}.jpg"
        if a.exists():
            a.unlink()
    print(f"moved {n} files to {REJ.relative_to(ROOT)} — run 'restore' to undo")


def restore():
    n = 0
    for f in REJ.rglob("*"):
        if f.is_file():
            dest = LIB / f.relative_to(REJ); dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), dest); n += 1
    print(f"restored {n} files")


if __name__ == "__main__":
    {"shortlist": shortlist, "rejects": rejects, "restore": restore}.get(
        (sys.argv[1:] or ["?"])[0], lambda: print(__doc__))()
