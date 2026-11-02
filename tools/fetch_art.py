#!/usr/bin/env python3
"""
fetch_art.py — pull the highest-resolution public-domain image for an artwork.

Two ways to use it
------------------
1) Paste any supported link and get the original file:

     python tools/fetch_art.py "https://commons.wikimedia.org/wiki/File:Brace's_Rock....jpg"
     python tools/fetch_art.py https://www.metmuseum.org/art/collection/search/11396
     python tools/fetch_art.py https://www.loc.gov/item/2007626395/

   Files land in art/inbox/ with a .json sidecar recording where they came from,
   the licence, pixel size and a SHA-256.

2) Fill the app with local high-res copies of everything in data/artworks.json:

     python tools/fetch_art.py --all            # skips files you already have
     python tools/fetch_art.py --id lane-stage-fort-1862 --force
     python tools/fetch_art.py --all --dry-run  # only resolve and list the source URLs

   For each item it tries the museum's own original first ("best" in the catalogue:
   The Met, Cleveland, Library of Congress...), falls back to Wikimedia Commons,
   and keeps whichever is larger. Writes:
     art/originals/<id>.<ext>   untouched original bytes (+ <id>.json provenance)
     art/full/<id>.jpg          full-size JPEG when the original is TIFF/PNG (browsers can't show TIFF)
     art/web/<id>.jpg           2560 px JPEG for the overlay and detail view
     art/thumbs/<id>.jpg        480 px JPEG for map pins and lists
     data/local.json            tells the app which local copies exist

Supported links: Wikimedia Commons (File: page or upload URL), The Met
(collection/search/<id>), Art Institute of Chicago (artworks/<id>), Cleveland
Museum of Art (art/<accession>), Library of Congress (item/<id>), National
Gallery of Art (object page — finds its IIIF image), any IIIF info.json, or a
direct image URL.

Needs only the Python standard library to download. Install Pillow
(`pip install pillow`) to also make the web/thumb/full JPEGs.
Be polite: one request per second, a descriptive User-Agent. Set
VANTAGE_CONTACT=you@example.com (or --contact) to add contact info to the
User-Agent, as Wikimedia asks of scripted clients.
"""
from __future__ import annotations

import argparse, hashlib, json, os, re, shutil, struct, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "artworks.json"
LOCAL = ROOT / "data" / "local.json"
ART = ROOT / "art"

UA = "VantageArtFetcher/1.0 (personal homelab art-walk app; python-urllib)"
WEB_PX, THUMB_PX, FULL_CAP_PX = 2560, 480, 16000
_last = [0.0]


# ── HTTP ────────────────────────────────────────────────────────────────────
def _req(url: str, method="GET", accept=None):
    h = {"User-Agent": UA}
    if accept:
        h["Accept"] = accept
    return urllib.request.Request(url, headers=h, method=method)


PACE = [1.0]   # seconds between requests (harvest.py raises it for Wikimedia)


def _pace():
    wait = PACE[0] - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()


def get_json(url: str, tries=7):
    for i in range(tries):
        _pace()
        try:
            with urllib.request.urlopen(_req(url, accept="application/json"), timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                # honour Retry-After when the server sends one, else back off 5, 10, 20, 40… s (max 120)
                ra = e.headers.get("Retry-After") if e.headers else None
                wait = int(ra) if ra and ra.isdigit() else min(5 * 2 ** i, 120)
                print(f"   (HTTP {e.code} — waiting {wait}s)")
                time.sleep(wait); continue
            raise
        except urllib.error.URLError:
            if i < tries - 1:
                time.sleep(2 ** (i + 1)); continue
            raise


def get_text(url: str):
    _pace()
    with urllib.request.urlopen(_req(url), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def download(url: str, dest: Path, max_mb: float, tries=4) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    for i in range(tries):
        _pace()
        try:
            with urllib.request.urlopen(_req(url), timeout=120) as r:
                total = int(r.headers.get("Content-Length") or 0)
                if total and total > max_mb * 1e6:
                    raise SystemExit(f"   ! {total/1e6:.0f} MB is over --max-mb {max_mb:.0f}; skipping {url}")
                got, t0 = 0, time.time()
                with open(part, "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk); got += len(chunk)
                        if total > 8e6:
                            pct = got * 100 / total
                            sys.stdout.write(f"\r   … {got/1e6:6.1f} / {total/1e6:.1f} MB ({pct:4.1f}%) {got/1e6/max(time.time()-t0,.1):.1f} MB/s")
                            sys.stdout.flush()
                if total > 8e6:
                    sys.stdout.write("\n")
            if total and got != total:
                raise IOError(f"short read {got} of {total}")
            os.replace(part, dest)
            return dest
        except (urllib.error.HTTPError, urllib.error.URLError, IOError) as e:
            code = getattr(e, "code", None)
            if i < tries - 1 and (code in (None, 429, 500, 502, 503, 504)):
                print(f"   retry after error: {e}"); time.sleep(2 ** (i + 1)); continue
            if part.exists():
                part.unlink()
            raise


# ── image size without Pillow ───────────────────────────────────────────────
def image_size(p: Path):
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 600_000_000
        with Image.open(p) as im:
            return im.size
    except Exception:
        pass
    with open(p, "rb") as f:
        head = f.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", head[16:24])
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                b = f.read(1)
                while b and b != b"\xff":
                    b = f.read(1)
                while b == b"\xff":
                    b = f.read(1)
                if not b:
                    break
                marker = b[0]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    f.read(3); h, w = struct.unpack(">HH", f.read(4)); return (w, h)
                seg = struct.unpack(">H", f.read(2))[0]; f.seek(seg - 2, 1)
        if head[:4] in (b"II*\x00", b"MM\x00*"):
            e = "<" if head[:2] == b"II" else ">"
            f.seek(4); off = struct.unpack(e + "I", f.read(4))[0]; f.seek(off)
            n = struct.unpack(e + "H", f.read(2))[0]; w = h = None
            for _ in range(n):
                tag, typ, cnt, val = struct.unpack(e + "HHI4s", f.read(12))
                v = struct.unpack(e + ("H" if typ == 3 else "I"), val[:2] if typ == 3 else val)[0]
                if tag == 256: w = v
                if tag == 257: h = v
            if w and h:
                return (w, h)
    return (None, None)


# ── resolvers: URL → {url, page, license, title, width?, height?} ───────────
def commons_info(filename: str):
    filename = urllib.parse.unquote(filename).replace("_", " ")
    if not filename.lower().startswith("file:"):
        filename = "File:" + filename
    q = urllib.parse.urlencode({"action": "query", "format": "json", "formatversion": 2, "titles": filename, "prop": "imageinfo",
                                "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "LicenseShortName|Credit|Artist|ObjectName"})
    d = get_json("https://commons.wikimedia.org/w/api.php?" + q)
    page = d["query"]["pages"][0]
    if "imageinfo" not in page:
        raise LookupError(f"Commons has no file called {filename!r}")
    ii = page["imageinfo"][0]; m = ii.get("extmetadata", {})
    strip = lambda s: re.sub(r"<[^>]+>", "", (s or {}).get("value", "")).strip()
    return {"url": ii["url"], "page": ii["descriptionurl"], "width": ii["width"], "height": ii["height"], "bytes": ii.get("size"),
            "license": strip(m.get("LicenseShortName")) or "see Commons page", "title": page["title"][5:], "source": "commons"}


def met_info(obj_id):
    d = get_json(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}")
    if not d.get("primaryImage"):
        raise LookupError(f"The Met object {obj_id} has no open-access image")
    return {"url": d["primaryImage"], "page": d.get("objectURL"), "license": "CC0 (The Met Open Access)" if d.get("isPublicDomain") else "NOT public domain",
            "title": d.get("title"), "source": "met", "pd": bool(d.get("isPublicDomain"))}


def iiif_info(info_url: str):
    d = get_json(info_url)
    base = d.get("@id") or d.get("id") or info_url.rsplit("/info.json", 1)[0]
    v3 = "iiif.io/api/image/3" in json.dumps(d.get("@context", ""))
    w, h = d.get("width"), d.get("height")
    mw = d.get("maxWidth") or (d.get("profile", [{}])[-1].get("maxWidth") if isinstance(d.get("profile"), list) and d["profile"] and isinstance(d["profile"][-1], dict) else None)
    size = f"{mw}," if mw and w and mw < w else ("max" if v3 else "full")
    return {"url": f"{base}/full/{size}/0/default.jpg", "page": info_url, "width": min(w or 0, mw or w or 0) or None, "license": "see source", "source": "iiif"}


def aic_info(obj_id):
    d = get_json(f"https://api.artic.edu/api/v1/artworks/{obj_id}?fields=id,title,image_id,is_public_domain")
    data, cfg = d["data"], d.get("config", {})
    if not data.get("image_id"):
        raise LookupError("Art Institute record has no image")
    r = iiif_info(f"{cfg.get('iiif_url', 'https://www.artic.edu/iiif/2')}/{data['image_id']}/info.json")
    r.update(page=f"https://www.artic.edu/artworks/{obj_id}", title=data.get("title"), source="aic",
             license="CC0 (Art Institute of Chicago)" if data.get("is_public_domain") else "NOT public domain", pd=bool(data.get("is_public_domain")))
    return r


def cma_info(accession):
    d = get_json(f"https://openaccess-api.clevelandart.org/api/artworks/{urllib.parse.quote(str(accession))}")["data"]
    imgs = d.get("images") or {}
    best = max((v for v in imgs.values() if isinstance(v, dict) and v.get("url")), key=lambda v: int(v.get("width") or 0), default=None)
    if not best:
        raise LookupError("Cleveland record has no image")
    return {"url": best["url"], "page": d.get("url"), "width": int(best.get("width") or 0) or None, "height": int(best.get("height") or 0) or None,
            "license": d.get("share_license_status", "see source"), "title": d.get("title"), "source": "cma", "pd": d.get("share_license_status") == "CC0"}


def loc_info(item_id):
    d = get_json(f"https://www.loc.gov/item/{item_id}/?fo=json")
    files = [f for res in d.get("resources", []) for group in res.get("files", []) for f in group]
    pick = lambda mt: max((f for f in files if f.get("mimetype") == mt and f.get("url")), key=lambda f: (f.get("width") or 0) * (f.get("height") or 0) or (f.get("size") or 0), default=None)
    best = pick("image/tiff") or pick("image/jp2") or pick("image/jpeg")
    if not best:
        raise LookupError("Library of Congress item has no image files")
    rights = " ".join(d.get("item", {}).get("rights_advisory", []) or []) or "see LOC rights statement"
    return {"url": best["url"], "page": f"https://www.loc.gov/item/{item_id}/", "width": best.get("width"), "height": best.get("height"),
            "bytes": best.get("size"), "license": rights, "title": d.get("item", {}).get("title"), "source": "loc"}


def nga_info(page_url):
    html = get_text(page_url)
    m = re.search(r"https://api\.nga\.gov/iiif/([0-9a-f-]{36})", html)
    if not m:
        raise LookupError("Couldn't find an IIIF image on that NGA page")
    r = iiif_info(f"https://api.nga.gov/iiif/{m.group(1)}/info.json")
    r.update(page=page_url, source="nga", license="CC0 (NGA Open Access)")
    return r


def resolve(link: str):
    u = urllib.parse.urlparse(link); host = u.netloc.lower(); path = urllib.parse.unquote(u.path)
    if "wikimedia.org" in host or "wikipedia.org" in host:
        if "/wiki/" in path:
            return commons_info(path.split("/wiki/", 1)[1])
        name = path.rstrip("/").split("/")[-1]
        if "/thumb/" in path:                     # …/thumb/a/ab/Name.jpg/1920px-Name.jpg
            name = path.split("/thumb/", 1)[1].split("/")[2]
        return commons_info(name)
    if "metmuseum.org" in host:
        m = re.search(r"/(\d+)/?$", path) or re.search(r"objects/(\d+)", path)
        return met_info(m.group(1))
    if "artic.edu" in host:
        return aic_info(re.search(r"/artworks/(\d+)", path).group(1))
    if "clevelandart.org" in host:
        return cma_info(path.rstrip("/").split("/")[-1])
    if "loc.gov" in host:
        m = re.search(r"/item/([^/]+)", path)
        if not m:
            raise LookupError("Use the LOC 'item' link (https://www.loc.gov/item/<id>/), not a resource/viewer link")
        return loc_info(m.group(1))
    if "nga.gov" in host and "iiif" not in path:
        return nga_info(link)
    if path.endswith("info.json"):
        return iiif_info(link)
    return {"url": link, "page": link, "license": "unknown — check it yourself", "source": "direct"}


def resolve_best(best: dict):
    src, ident = best["source"], best["id"]
    return {"met": met_info, "aic": aic_info, "cma": cma_info, "loc": loc_info}[src](ident)


# ── derivatives ─────────────────────────────────────────────────────────────
def make_jpeg(src: Path, dest: Path, long_edge: int | None, quality: int):
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = 600_000_000
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("I;16", "I;16B", "I;16L", "I"):
            im = im.point(lambda v: v / 256).convert("L")
        if im.mode not in ("RGB", "L"):
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
            else:
                im = im.convert("RGB")
        if long_edge and max(im.size) > long_edge:
            im.thumbnail((long_edge, long_edge), Image.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "JPEG", quality=quality, optimize=True, progressive=True, subsampling=0)
        return im.size


def sha256(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ext_for(url: str, fallback=".jpg"):
    e = Path(urllib.parse.urlparse(url).path).suffix.lower()
    return {".jpeg": ".jpg", ".tiff": ".tif"}.get(e, e) if e in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".jp2", ".webp") else fallback


# ── modes ───────────────────────────────────────────────────────────────────
def fetch_links(links, args):
    inbox = ART / "inbox"
    for link in links:
        print(f"→ {link}")
        info = resolve(link)
        print(f"   source: {info['source']}  licence: {info.get('license')}")
        print(f"   original: {info['url']}" + (f"  ({info['width']}×{info.get('height')})" if info.get("width") else ""))
        if args.dry_run:
            continue
        stem = re.sub(r"[^\w.-]+", "_", (info.get("title") or Path(urllib.parse.urlparse(info["url"]).path).stem))[:90].strip("_") or "image"
        dest = inbox / (stem + ext_for(info["url"]))
        download(info["url"], dest, args.max_mb)
        w, h = image_size(dest)
        meta = {**info, "file": dest.name, "width": w, "height": h, "bytes": dest.stat().st_size, "sha256": sha256(dest),
                "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"), "requested": link}
        dest.with_suffix(dest.suffix + ".json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        print(f"   saved {dest.relative_to(ROOT)}  {w}×{h}  {meta['bytes']/1e6:.1f} MB")


def fetch_catalog(args):
    cat = json.loads(DATA.read_text(encoding="utf-8"))
    local = json.loads(LOCAL.read_text(encoding="utf-8")) if LOCAL.exists() else {"items": {}}
    items = [i for i in cat["items"] if not args.id or i["id"] in args.id]
    if not items:
        sys.exit("No matching items.")
    try:
        import PIL  # noqa: F401
        have_pil = True
    except ImportError:
        have_pil = False
        print("Pillow isn't installed — originals only. `pip install pillow` to also build the app's JPEGs.\n")
    ok = fail = 0
    for it in items:
        iid, img = it["id"], it["image"]
        print(f"■ {iid} — {it['title']}")
        orig_dir = ART / "originals"
        existing = sorted(orig_dir.glob(iid + ".*")) if orig_dir.exists() else []
        existing = [p for p in existing if p.suffix not in (".json", ".part")]
        try:
            if existing and not args.force:
                orig = existing[0]
                print(f"   have {orig.name}")
                meta = json.loads((orig_dir / f"{iid}.json").read_text(encoding="utf-8")) if (orig_dir / f"{iid}.json").exists() else {}
            else:
                cands = []
                if img.get("best"):
                    try:
                        cands.append(resolve_best(img["best"]))
                    except Exception as e:
                        print(f"   (museum source failed: {e})")
                try:
                    cands.append(commons_info(img["commons"]))
                except Exception as e:
                    print(f"   (Commons lookup failed: {e})")
                if not cands:
                    raise LookupError("no source resolved")
                for c in cands:
                    print(f"   candidate {c['source']:8s} {c.get('width') or '?'}×{c.get('height') or '?'}  {c['url'][:110]}")
                if args.dry_run:
                    ok += 1; continue
                # museum original first; if it turns out smaller than Commons, fetch Commons too and keep the larger
                for p in existing:
                    p.unlink()
                best, best_px, best_path = None, -1, None
                for c in cands:
                    if best and c.get("width") and best_px >= (c["width"] * (c.get("height") or c["width"])):
                        continue
                    dest = orig_dir / f"{iid}{ext_for(c['url'])}"
                    tmp = dest.with_name(dest.stem + f".{c['source']}{dest.suffix}")
                    download(c["url"], tmp, args.max_mb)
                    w, h = image_size(tmp)
                    px = (w or 0) * (h or 0)
                    print(f"   got {c['source']}: {w}×{h}  {tmp.stat().st_size/1e6:.1f} MB")
                    if px > best_px:
                        if best_path and best_path.exists():
                            best_path.unlink()
                        best, best_px, best_path = {**c, "width": w, "height": h}, px, tmp
                    else:
                        tmp.unlink()
                orig = orig_dir / f"{iid}{best_path.suffix}"
                os.replace(best_path, orig)
                meta = {k: best.get(k) for k in ("source", "url", "page", "license", "title", "width", "height")}
                meta.update(file=orig.name, bytes=orig.stat().st_size, sha256=sha256(orig), fetched=datetime.now(timezone.utc).isoformat(timespec="seconds"))
                (orig_dir / f"{iid}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
            w, h = meta.get("width"), meta.get("height")
            if not w:
                w, h = image_size(orig)
            entry = {"original": f"art/originals/{orig.name}", "width": w, "height": h, "source": meta.get("source"), "license": meta.get("license")}
            if have_pil:
                web = ART / "web" / f"{iid}.jpg"; th = ART / "thumbs" / f"{iid}.jpg"
                if args.force or not web.exists():
                    make_jpeg(orig, web, WEB_PX, 88)
                if args.force or not th.exists():
                    make_jpeg(orig, th, THUMB_PX, 82)
                entry.update(web=f"art/web/{iid}.jpg", thumb=f"art/thumbs/{iid}.jpg")
                if orig.suffix in (".jpg", ".png"):
                    entry["full"] = entry["original"]
                else:
                    full = ART / "full" / f"{iid}.jpg"
                    if args.force or not full.exists():
                        make_jpeg(orig, full, FULL_CAP_PX, 92)
                    entry["full"] = f"art/full/{iid}.jpg"
            elif orig.suffix in (".jpg", ".png"):
                entry["full"] = entry["original"]
            local["items"][iid] = entry
            print(f"   ✓ {w}×{h} · {meta.get('source')} · {meta.get('license')}")
            ok += 1
        except SystemExit as e:
            print(e); fail += 1
        except Exception as e:
            print(f"   ✗ {type(e).__name__}: {e}"); fail += 1
    if not args.dry_run:
        local["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        LOCAL.write_text(json.dumps(local, indent=1), encoding="utf-8")
        print(f"\nWrote {LOCAL.relative_to(ROOT)} — {len(local['items'])} local images.")
    print(f"Done: {ok} ok, {fail} failed.")


def main():
    global UA
    ap = argparse.ArgumentParser(description="Fetch the highest-resolution public-domain image for an artwork.")
    ap.add_argument("links", nargs="*", help="museum / Commons / LOC / IIIF links to fetch into art/inbox/")
    ap.add_argument("--all", action="store_true", help="fetch every item in data/artworks.json")
    ap.add_argument("--id", action="append", help="only this catalogue id (repeatable)")
    ap.add_argument("--force", action="store_true", help="re-download and rebuild even if files exist")
    ap.add_argument("--dry-run", action="store_true", help="resolve and print sources, download nothing")
    ap.add_argument("--max-mb", type=float, default=400, help="skip single files larger than this (default 400)")
    ap.add_argument("--contact", default=os.environ.get("VANTAGE_CONTACT"), help="contact info appended to the User-Agent")
    args = ap.parse_args()
    if args.contact:
        UA = UA.replace(")", f"; {args.contact})")
    if args.links:
        fetch_links(args.links, args)
    elif args.all or args.id:
        fetch_catalog(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
