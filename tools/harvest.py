#!/usr/bin/env python3
"""
harvest.py — sweep the big open-access collections for Cape Ann and Portland-area art,
download the highest-resolution public-domain files, and build a gallery to triage them.

    python tools/harvest.py                 # discover → download → gallery (resumable; just re-run)
    python tools/harvest.py discover        # search only: writes harvest/manifest.jsonl
    python tools/harvest.py download        # fetch originals within the budget
    python tools/harvest.py gallery         # rebuild harvest/gallery.html
    python tools/harvest.py --budget-gb 250 --region cape_ann --sources commons,cma,nga

What it searches (no API keys needed)
  commons  Wikimedia Commons — artist + place searches, public-domain and pre-1931 only
  met      The Met — open-access CSV (search API is closed), objects API for the image
  nga      National Gallery of Art — open-data CSVs from GitHub, IIIF full-size images
  cma      Cleveland Museum of Art — CC0 API, full-resolution TIFFs
  aic      Art Institute of Chicago — public-domain filter, IIIF
  loc      Library of Congress — Detroit Publishing & other pre-1931 photos, HABS
           (federal, public domain), bird's-eye views, Sanborn fire-insurance maps

Where things go
  harvest/manifest.jsonl     every candidate: source, title, artist, date, places matched, rights
  harvest/downloads.jsonl    what's been fetched (append-only log, makes re-runs resumable)
  harvest/gallery.html       browse everything, filter, tick favourites, export picks
  art/library/<region>/<source>/<file>   untouched originals + .json provenance sidecars
  art/library/_thumbs/       480 px previews (needs Pillow)

Rights: an item is kept only when its source says so — Met isPublicDomain, NGA openaccess,
CMA CC0, AIC is_public_domain, Commons "public domain"/CC0 with a date before 1931, LOC
items dated before 1931 (or HABS/HAER, which are federal works). Still check before
publishing anything outside your homelab.
"""
from __future__ import annotations

import argparse, csv, html, io, json, os, re, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_art as F  # shared HTTP, download, image helpers

ROOT = F.ROOT
HV = ROOT / "harvest"
CACHE = HV / "cache"
LIB = ROOT / "art" / "library"
MANIFEST = HV / "manifest.jsonl"
DLOG = HV / "downloads.jsonl"
csv.field_size_limit(1 << 30)

# ── who and where ───────────────────────────────────────────────────────────
# scope "all": keep every public-domain work by the artist; "local": only works whose
# title/description mentions one of the region's places.
ARTISTS = [
    # Cape Ann and the North Shore
    ("Fitz Henry Lane", ["Fitz Hugh Lane", "Lane, Fitz Henry", "Lane, Fitz Hugh"], "cape_ann", "all"),
    ("Mary Blood Mellen", ["Mellen, Mary Blood"], "cape_ann", "all"),
    ("Winslow Homer", ["Homer, Winslow"], "cape_ann", "local"),
    ("Childe Hassam", ["Frederick Childe Hassam", "Hassam, Childe"], "cape_ann", "local"),
    ("John Henry Twachtman", ["John H. Twachtman", "Twachtman, John Henry", "John Twachtman"], "cape_ann", "local"),
    ("Frank Duveneck", ["Duveneck, Frank"], "cape_ann", "local"),
    ("Willard Leroy Metcalf", ["Willard Metcalf", "Metcalf, Willard"], "cape_ann", "local"),
    ("Maurice Prendergast", ["Maurice Brazil Prendergast", "Prendergast, Maurice"], "cape_ann", "local"),
    ("John Sloan", ["Sloan, John"], "cape_ann", "local"),
    ("Cecilia Beaux", ["Beaux, Cecilia"], "cape_ann", "local"),
    ("William Morris Hunt", ["Hunt, William Morris"], "cape_ann", "local"),
    ("William Lamb Picknell", ["Picknell, William Lamb"], "cape_ann", "local"),
    ("Augustus Waldeck Buhler", ["A. W. Buhler", "Buhler, Augustus"], "cape_ann", "all"),
    ("Paul Cornoyer", ["Cornoyer, Paul"], "cape_ann", "local"),
    ("Arthur Wesley Dow", ["Dow, Arthur Wesley"], "cape_ann", "local"),
    ("Edward Hopper", ["Hopper, Edward"], "cape_ann", "local"),
    ("Marsden Hartley", ["Hartley, Marsden"], "cape_ann", "local"),
    ("Martha Hale Harvey", ["Harvey, Martha Hale"], "cape_ann", "all"),
    # Portland, Casco Bay, Cape Elizabeth, Prouts Neck
    ("Charles Codman", ["Codman, Charles"], "portland", "all"),
    ("Charles Frederick Kimball", ["Kimball, Charles Frederick"], "portland", "all"),
    ("Harrison Bird Brown", ["Brown, Harrison Bird", "Harrison B. Brown"], "portland", "all"),
    ("John Bradford Hudson", ["Hudson, John Bradford"], "portland", "all"),
    ("George M. Hathaway", ["Hathaway, George M."], "portland", "all"),
    ("Walter Griffin", ["Griffin, Walter"], "portland", "local"),
    ("John Calvin Stevens", ["Stevens, John Calvin"], "portland", "all"),
    ("Winslow Homer", ["Homer, Winslow"], "portland", "local"),
    ("Edward Hopper", ["Hopper, Edward"], "portland", "local"),
    ("Fitz Henry Lane", ["Fitz Hugh Lane"], "portland", "local"),
]

PLACES = {
    "cape_ann": ["Gloucester", "Rockport", "Annisquam", "Cape Ann", "Lanesville", "Pigeon Cove", "Magnolia, Mass", "Eastern Point",
                 "Rocky Neck", "Ten Pound Island", "Ten-Pound Island", "Five Pound Island", "Bass Rocks", "Good Harbor",
                 "Norman's Woe", "Normans Woe", "Thacher", "Thatcher's Island", "Straitsmouth", "Brace's Rock", "Braces Rock",
                 "Brace's Cove", "Dolliver", "Fresh Water Cove", "Freshwater Cove", "Stage Fort", "'Squam", "Squam River", "Folly Cove",
                 "Bearskin Neck", "Sandy Bay", "Coffin's Beach", "Wingaersheek", "Essex, Mass", "Manchester-by-the-Sea",
                 "Manchester, Mass", "Kettle Cove", "Ipswich, Mass", "Ipswich River", "Ipswich Bay", "Ipswich Marsh", "Plum Island",
                 "Halfway Rock", "Dogtown"],
    "portland": ["Portland, Me", "Portland, Maine", "Portland Harbor", "Portland harbour", "Portland Head", "Casco Bay",
                 "Cape Elizabeth", "Two Lights", "Prout's Neck", "Prouts Neck", "Scarborough, Me", "Scarborough, Maine", "Peak's Island", "Peaks Island",
                 "Cushing Island", "Diamond Island", "House Island", "Falmouth Foreside", "Back Cove", "Munjoy", "Spring Point",
                 "Old Orchard Beach", "Higgins Beach", "Richmond Island", "Westbrook, Me", "South Portland", "Cannon Rock",
                 "Coast of Maine", "Maine Coast"],
}
# search phrases for sources with a text search (artists are searched separately)
QUERIES = {
    "cape_ann": ["Gloucester Massachusetts", "Gloucester Harbor", "Gloucester, Mass", "Rockport Massachusetts", "Annisquam",
                 "Cape Ann", "Eastern Point", "Ten Pound Island", "Magnolia Massachusetts", "Manchester Massachusetts",
                 "Essex Massachusetts", "Ipswich Massachusetts", "Pigeon Cove", "Lanesville", "Rocky Neck"],
    "portland": ["Portland Maine", "Portland, Me", "Portland Harbor", "Casco Bay", "Cape Elizabeth", "Portland Head Light",
                 "Prouts Neck", "Scarborough Maine", "Peaks Island", "Old Orchard"],
}
LOC_TOWNS = {"cape_ann": ["Gloucester, Massachusetts", "Rockport, Massachusetts", "Manchester, Massachusetts",
                          "Essex, Massachusetts", "Ipswich, Massachusetts"],
             "portland": ["Portland, Maine", "South Portland, Maine", "Cape Elizabeth, Maine", "Scarborough, Maine",
                          "Westbrook, Maine", "Falmouth, Maine"]}

SOURCE_RANK = {"cma": 0, "met": 1, "nga": 2, "aic": 3, "loc": 4, "commons": 5}


# ── text helpers ────────────────────────────────────────────────────────────
def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

_place_res = {r: [(p, re.compile(r"\b" + re.escape(norm(p)) + r"\b")) for p in ps] for r, ps in PLACES.items()}
_artist_res = [(a, region, scope, re.compile(r"\b(" + "|".join(re.escape(norm(n)) for n in [a] + al) + r")\b"))
               for a, al, region, scope in ARTISTS]


# same names elsewhere (Gloucester UK/VA/NJ, Rockport ME/TX…) — a hit preceded/followed by these is ignored
ELSEWHERE = re.compile(r"\b(gloucestershire|gloucester (cathedral|england|virginia|va|new jersey|nj|county|point|city|road|docks)|"
                       r"rockport (me|maine|texas|tx|indiana)|cape elizabeth (south africa)|portland (oregon|or|place|vase|stone|cement))\b")


def places_in(text):
    t = norm(text); hits = {}
    t = ELSEWHERE.sub(" ", t)
    for region, pats in _place_res.items():
        found = [p for p, rx in pats if rx.search(t)]
        if found:
            hits[region] = found
    return hits


def artists_in(text):
    t = norm(text)
    return [(a, region, scope) for a, region, scope, rx in _artist_res if rx.search(t)]


def year_of(s):
    m = re.findall(r"(1[5-9]\d\d|20[0-2]\d)", str(s or ""))
    return int(m[-1]) if m else None   # latest year mentioned (end of a range)


def classify(text, artist_text="", require_artist=False):
    """→ (regions, places, artist) or None when the item isn't relevant"""
    pl = places_in(text)
    arts = artists_in(artist_text or text)
    regions = set(pl)
    keep_artist = None
    for a, region, scope in arts:
        if scope == "all" or region in pl:
            regions.add(region); keep_artist = a
        elif pl:
            keep_artist = keep_artist or a
    if require_artist and not keep_artist:
        return None
    if not regions:
        return None
    return sorted(regions), sorted({p for v in pl.values() for p in v}), keep_artist or (arts[0][0] if arts else None)


def slug(s, n=70):
    return re.sub(r"[^a-z0-9]+", "-", norm(s))[:n].strip("-") or "item"


def cache_get(name, url, max_age_days=30):
    """download a big CSV once into harvest/cache"""
    p = CACHE / name
    if p.exists() and time.time() - p.stat().st_mtime < max_age_days * 86400 and p.stat().st_size > 1000:
        return p
    print(f"   caching {name} …")
    F.download(url, p, max_mb=2000)
    return p


# ── sources: each yields candidate dicts ────────────────────────────────────
def cand(source, sid, title, artist, date, regions, places, page, thumb=None, rights="", kind="", **kw):
    return {"key": f"{source}:{sid}", "source": source, "id": str(sid), "title": title, "artist": artist, "date": str(date or ""),
            "year": year_of(date), "regions": regions, "places": places, "page": page, "thumb": thumb, "rights": rights,
            "kind": kind, **kw}


def post_json(url, params, tries=7):
    """POST form query — long title lists overflow a GET URL (HTTP 414)"""
    body = urllib.parse.urlencode(params).encode()
    for i in range(tries):
        F._pace()
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": F.UA, "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                ra = e.headers.get("Retry-After") if e.headers else None
                wait = int(ra) if ra and ra.isdigit() else min(5 * 2 ** i, 120)
                print(f"   (HTTP {e.code} — waiting {wait}s)"); time.sleep(wait); continue
            raise


def src_commons(regions):
    F.PACE[0] = 2.0          # Wikimedia rate-limits bursty clients; restored after
    try:
        yield from _src_commons(regions)
    finally:
        F.PACE[0] = 1.0


def _src_commons(regions):
    api = "https://commons.wikimedia.org/w/api.php?"
    titles = set()
    def search(q, pages=4):
        off = 0
        for _ in range(pages):
            try:
                d = F.get_json(api + urllib.parse.urlencode({"action": "query", "format": "json", "formatversion": 2, "list": "search",
                           "srsearch": q, "srnamespace": 6, "srlimit": 500, "sroffset": off}))
            except Exception as e:
                print(f"   commons search '{q}' skipped: {e}"); return
            for r in d.get("query", {}).get("search", []):
                titles.add(r["title"])
            if "continue" not in d:
                break
            off = d["continue"]["sroffset"]
    seen_artist = set()
    for a, al, region, scope in ARTISTS:
        if region not in regions or a in seen_artist:
            continue
        seen_artist.add(a)
        print(f"   commons: artist {a}")
        search(f'"{a}"', pages=6 if scope == "all" else 4)
    for region in regions:
        for q in QUERIES[region]:
            for extra in ("painting", "photograph OR photochrom OR Detroit OR LOC OR NYPL", "lithograph OR engraving OR drawing OR watercolor"):
                print(f"   commons: {q} + {extra.split()[0]}…")
                search(f'"{q}" {extra}', pages=2)
    titles = sorted(titles)
    print(f"   commons: {len(titles)} files to inspect")
    for i in range(0, len(titles), 50):
      try:
        d = post_json(api, {"action": "query", "format": "json", "formatversion": 2, "titles": "|".join(titles[i:i + 50]),
                       "prop": "imageinfo|categories", "cllimit": "max", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 500,
                       "iiextmetadatafilter": "LicenseShortName|ImageDescription|DateTimeOriginal|Artist|ObjectName|Credit"})
      except Exception as e:
        print(f"   commons batch {i // 50 + 1} skipped: {e}"); continue
      if True:
          for p in d.get("query", {}).get("pages", []):
              ii = (p.get("imageinfo") or [{}])[0]
              if not ii or not str(ii.get("mime", "")).startswith("image/") or ii.get("mime") == "image/svg+xml":
                  continue
              m = ii.get("extmetadata", {})
              val = lambda k: re.sub(r"<[^>]+>", " ", (m.get(k) or {}).get("value", "")).strip()
              lic, date = val("LicenseShortName"), val("DateTimeOriginal")
              yr = year_of(date)
              cats = " ".join(c["title"][9:] for c in p.get("categories", []))
              pd_ok = ("public domain" in lic.lower() or lic.upper().startswith("PD") or "cc0" in lic.lower()) and (yr is None or yr <= 1930 or "cc0" in lic.lower())
              if not pd_ok or (yr and yr > 1930) or min(ii.get("width", 0), ii.get("height", 0)) < 600:
                  continue
              text = " ".join([p["title"], val("ObjectName"), val("ImageDescription"), cats])
              c = classify(text, " ".join([p["title"], val("Artist"), cats]))
              if not c:
                  continue
              kind = "photograph" if re.search(r"photo|photochrom|detroit publishing|stereograph|glass negative", text, re.I) else ""
              yield cand("commons", p["title"][5:], val("ObjectName") or p["title"][5:].rsplit(".", 1)[0], c[2] or val("Artist")[:80],
                         date[:40], c[0], c[1], ii.get("descriptionurl"), ii.get("thumburl"), lic, kind,
                         url=ii.get("url"), width=ii.get("width"), height=ii.get("height"), bytes=ii.get("size"), credit=val("Credit")[:160])


def src_met(regions):
    p = cache_get("MetObjects.csv", "https://media.githubusercontent.com/media/metmuseum/openaccess/master/MetObjects.csv")
    hits = []
    with open(p, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("Is Public Domain") != "True":
                continue
            text = " ".join(r.get(k, "") for k in ("Title", "City", "State", "County", "Region", "Subregion", "Locale", "Tags", "Object Name"))
            artist = " ".join(r.get(k, "") for k in ("Artist Display Name", "Artist Alpha Sort"))
            c = classify(text + " " + artist, artist)
            if c and set(c[0]) & set(regions):
                hits.append((r, c))
    print(f"   met: {len(hits)} matches in the open-access CSV")
    for r, c in hits:
        oid = r["Object ID"]
        try:
            o = F.get_json(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}")
        except Exception as e:
            print(f"   met {oid}: {e}"); continue
        if not o.get("primaryImage"):
            continue
        yield cand("met", oid, o.get("title"), o.get("artistDisplayName") or c[2], o.get("objectDate"), c[0], c[1], o.get("objectURL"),
                   o.get("primaryImageSmall"), "CC0 (The Met Open Access)", o.get("classification", "").lower(), url=o["primaryImage"])


def src_nga(regions):
    base = "https://raw.githubusercontent.com/NationalGalleryOfArt/opendata/main/data/"
    objs = cache_get("nga_objects.csv", base + "objects.csv")
    imgs = cache_get("nga_published_images.csv", base + "published_images.csv")
    want = {}
    with open(objs, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            artist = r.get("attribution", "")
            c = classify(" ".join([r.get("title", ""), artist]), artist)
            if c and set(c[0]) & set(regions):
                want[r["objectid"]] = (r, c)
    n = 0
    with open(imgs, encoding="utf-8", newline="") as f:
        for im in csv.DictReader(f):
            oid = im.get("depictstmsobjectid")
            if oid not in want or im.get("viewtype") != "primary" or im.get("openaccess") != "1":
                continue
            r, c = want[oid]; n += 1
            yield cand("nga", oid, r["title"], r.get("attribution"), r.get("displaydate"), c[0], c[1],
                       f"https://www.nga.gov/collection/art-object-page.{oid}.html", im.get("iiifthumburl"), "CC0 (NGA Open Access)",
                       (r.get("classification") or "").lower(), url=im["iiifurl"] + "/full/max/0/default.jpg",
                       width=int(im.get("width") or 0), height=int(im.get("height") or 0))
    print(f"   nga: {len(want)} matching objects, {n} with open-access images")


def src_cma(regions):
    seen = set()
    terms = [q for r in regions for q in QUERIES[r]] + sorted({a for a, _, reg, _ in ARTISTS if reg in regions})
    for q in terms:
        skip = 0
        while True:
            d = F.get_json("https://openaccess-api.clevelandart.org/api/artworks/?" + urllib.parse.urlencode(
                {"q": q, "cc0": 1, "has_image": 1, "limit": 100, "skip": skip}))
            rows = d.get("data", [])
            for o in rows:
                if o["id"] in seen:
                    continue
                artist = " ".join(c.get("description", "") for c in (o.get("creators") or []))
                c = classify(" ".join([o.get("title", ""), o.get("description") or "", artist, o.get("culture") and " ".join(o["culture"]) or ""]), artist)
                if not c or not set(c[0]) & set(regions):
                    continue
                seen.add(o["id"])
                imgs = o.get("images") or {}
                best = max((v for v in imgs.values() if isinstance(v, dict) and v.get("url")), key=lambda v: int(v.get("width") or 0), default=None)
                if not best:
                    continue
                yield cand("cma", o["accession_number"], o.get("title"), artist[:120], o.get("creation_date"), c[0], c[1], o.get("url"),
                           (imgs.get("web") or {}).get("url"), "CC0 (Cleveland Museum of Art)", (o.get("type") or "").lower(),
                           url=best["url"], width=int(best.get("width") or 0), height=int(best.get("height") or 0))
            skip += 100
            if skip >= (d.get("info", {}).get("total") or 0) or not rows:
                break


def src_aic(regions):
    seen = set()
    terms = [q for r in regions for q in QUERIES[r]] + sorted({a for a, _, reg, _ in ARTISTS if reg in regions})
    for q in terms:
        for page in range(1, 6):
            try:
                d = F.get_json("https://api.artic.edu/api/v1/artworks/search?" + urllib.parse.urlencode(
                    {"q": q, "query[term][is_public_domain]": "true", "fields": "id,title,artist_display,date_display,image_id,place_of_origin,artwork_type_title",
                     "limit": 100, "page": page}))
            except Exception as e:
                print(f"   aic '{q}': {e}"); break
            for o in d.get("data", []):
                if o["id"] in seen or not o.get("image_id"):
                    continue
                c = classify(" ".join([o.get("title", ""), o.get("artist_display", "")]), o.get("artist_display", ""))
                if not c or not set(c[0]) & set(regions):
                    continue
                seen.add(o["id"])
                iiif = d.get("config", {}).get("iiif_url", "https://www.artic.edu/iiif/2")
                yield cand("aic", o["id"], o.get("title"), o.get("artist_display", "").split("\n")[0], o.get("date_display"), c[0], c[1],
                           f"https://www.artic.edu/artworks/{o['id']}", f"{iiif}/{o['image_id']}/full/843,/0/default.jpg",
                           "CC0 (Art Institute of Chicago)", (o.get("artwork_type_title") or "").lower(),
                           info=f"{iiif}/{o['image_id']}/info.json")
            if page >= (d.get("pagination", {}).get("total_pages") or 1):
                break


def src_loc(regions):
    def search(path, q, kind, pages=10, require_place=True, federal=False):
        for sp in range(1, pages + 1):
            try:
                d = F.get_json(f"https://www.loc.gov/{path}?" + urllib.parse.urlencode({"q": q, "fo": "json", "c": 100, "sp": sp}))
            except Exception as e:
                print(f"   loc '{q}': {e}"); return
            for r in d.get("results", []):
                iid = (r.get("id") or "").rstrip("/").split("/")[-1]
                if not iid or not r.get("image_url"):
                    continue
                title = r.get("title") or ""
                yr = year_of(r.get("date"))
                if not federal and (yr is None or yr > 1930):
                    continue
                text = " ".join([title, " ".join(r.get("location") or []), " ".join(r.get("subject") or [])])
                c = classify(text, " ".join(r.get("contributor") or []))
                if require_place and (not c or not set(c[0]) & set(regions)):
                    continue
                regs = c[0] if c else regions
                yield cand("loc", iid, title, ", ".join(r.get("contributor") or [])[:120], r.get("date"), regs, c[1] if c else [],
                           f"https://www.loc.gov/item/{iid}/", (r.get("image_url") or [None])[-1].split("#")[0],
                           "Library of Congress — federal work / no known restrictions" if federal else "Library of Congress — pre-1931",
                           kind, all_files=kind in ("sanborn", "habs"))
            if not d.get("pagination", {}).get("next"):
                break
    for region in regions:
        for q in QUERIES[region]:
            print(f"   loc: photos '{q}'")
            yield from search("photos/", q, "photograph", pages=8)
        for town in LOC_TOWNS[region]:
            print(f"   loc: maps/HABS '{town}'")
            yield from search("collections/panoramic-maps/", town, "birdseye", pages=2)
            yield from search("collections/sanborn-maps/", town, "sanborn", pages=3)
            yield from search("collections/historic-american-buildings-landscapes-and-engineering-records/", town, "habs", pages=10, federal=True)


SOURCES = {"commons": src_commons, "met": src_met, "nga": src_nga, "cma": src_cma, "aic": src_aic, "loc": src_loc}


# ── discover ────────────────────────────────────────────────────────────────
def discover(args):
    HV.mkdir(parents=True, exist_ok=True)
    found = {}
    if MANIFEST.exists():   # keep earlier results from sources/regions not being re-run
        for l in open(MANIFEST, encoding="utf-8"):
            if l.strip():
                c = json.loads(l)
                if c["source"] not in args.sources or not set(c["regions"]) & set(args.region):
                    found[c["key"]] = c
    for name in args.sources:
        print(f"■ {name}")
        n = 0
        try:
            for c in SOURCES[name](args.region):
                found[c["key"]] = c; n += 1
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"   ✗ {name} stopped early: {type(e).__name__}: {e}")
        print(f"   → {n} candidates")
    # light de-duplication across sources: same artist + title + year → keep the best source
    best = {}
    for c in found.values():
        k = (norm(c["artist"])[:30], norm(c["title"])[:60], c["year"])
        if c["kind"] in ("sanborn", "habs") or not norm(c["title"]):
            k = (c["key"],)
        if k not in best or SOURCE_RANK[c["source"]] < SOURCE_RANK[best[k]["source"]]:
            if k in best:
                c.setdefault("also", []).append(best[k]["page"])
            best[k] = c
    rows = sorted(best.values(), key=lambda c: (c["regions"][0], c["kind"] in ("sanborn", "habs"), c["source"], c["artist"] or "", c["title"] or ""))
    with open(MANIFEST, "w", encoding="utf-8") as f:
        for c in rows:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    by = {}
    for c in rows:
        by[(c["regions"][0], c["source"])] = by.get((c["regions"][0], c["source"]), 0) + 1
    print(f"\nmanifest: {len(rows)} items ({len(found) - len(rows)} duplicates folded)")
    for (r, s), n in sorted(by.items()):
        print(f"   {r:9s} {s:8s} {n}")


# ── download ────────────────────────────────────────────────────────────────
def load_manifest():
    if not MANIFEST.exists():
        sys.exit("No manifest yet — run `harvest.py discover` first.")
    return [json.loads(l) for l in open(MANIFEST, encoding="utf-8") if l.strip()]


def load_dlog():
    done = {}
    if DLOG.exists():
        for l in open(DLOG, encoding="utf-8"):
            if l.strip():
                d = json.loads(l); done[d["key"]] = d
    return done


def resolve_files(c):
    """→ list of (url, label) for the item's best original(s)"""
    s = c["source"]
    if s in ("commons", "met", "nga", "cma"):
        return [(c["url"], "")]
    if s == "aic":
        return [(F.iiif_info(c["info"])["url"], "")]
    if s == "loc":
        d = F.get_json(f"https://www.loc.gov/item/{c['id']}/?fo=json")
        rights = " ".join(d.get("item", {}).get("rights_advisory") or [])
        if re.search(r"rights status not evaluated|copyright", rights, re.I) and c["kind"] not in ("habs",) and not re.search(r"no known restrictions", rights, re.I):
            raise PermissionError(f"LOC rights: {rights[:120]}")
        out = []
        for i, res in enumerate(d.get("resources", [])):
            files = [f for g in res.get("files", []) for f in g if f.get("url")]
            pick = lambda mt: max((f for f in files if f.get("mimetype") == mt), key=lambda f: (f.get("width") or 0) * (f.get("height") or 0) or (f.get("size") or 0), default=None)
            b = pick("image/tiff") or pick("image/jp2") or pick("image/jpeg")
            if b:
                out.append((b["url"], f"-{i + 1:03d}" if c.get("all_files") else ""))
            if not c.get("all_files") and out:
                break
        return out
    raise ValueError(s)


def download(args):
    items = [c for c in load_manifest() if set(c["regions"]) & set(args.region) and c["source"] in args.sources]
    done = load_dlog()
    used = sum(d.get("bytes", 0) for d in done.values())
    budget = args.budget_gb * 1e9
    # artworks first, then photographs, then the big map/HABS sets
    order = {"": 0, "painting": 0, "paintings": 0, "photograph": 1, "birdseye": 1, "habs": 2, "sanborn": 3}
    items.sort(key=lambda c: (order.get(c["kind"], 0) if c["kind"] in order else (1 if "photo" in c["kind"] else 0), SOURCE_RANK[c["source"]]))
    print(f"{len(items)} items, {len(done)} already fetched ({used / 1e9:.1f} GB of {args.budget_gb:.0f} GB budget)")
    have_pil = True
    try:
        import PIL  # noqa: F401
    except ImportError:
        have_pil = False
        print("(Pillow not installed — no thumbnails; `pip install pillow`)")
    with open(DLOG, "a", encoding="utf-8") as log:
        for n, c in enumerate(items, 1):
            if c["key"] in done and all((ROOT / p).exists() for p in done[c["key"]]["files"]):
                continue
            if used >= budget:
                print(f"\nBudget of {args.budget_gb:.0f} GB reached — stopping. Raise --budget-gb to continue."); break
            print(f"[{n}/{len(items)}] {c['source']} · {c['title'][:70]}")
            try:
                files = resolve_files(c)
                if not files:
                    raise LookupError("no image files")
                folder = LIB / c["regions"][0] / c["source"]
                base = slug(f"{c['artist'] or ''} {c['title']} {c['year'] or ''}") + "--" + slug(c["id"], 24)
                paths, total = [], 0
                for url, label in files:
                    dest = folder / f"{base}{label}{F.ext_for(url)}"
                    if not dest.exists():
                        F.download(url, dest, args.max_file_mb)
                    paths.append(dest); total += dest.stat().st_size
                w, h = F.image_size(paths[0])
                meta = {**c, "files": [str(p.relative_to(ROOT)).replace("\\", "/") for p in paths], "bytes": total, "width": w, "height": h,
                        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                (folder / f"{base}.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
                if have_pil:
                    th = LIB / "_thumbs" / f"{slug(c['key'], 90)}.jpg"
                    if not th.exists():
                        try:
                            F.make_jpeg(paths[0], th, 480, 80); meta["thumb_local"] = str(th.relative_to(ROOT)).replace("\\", "/")
                        except Exception as e:
                            print(f"   (thumb failed: {e})")
                    else:
                        meta["thumb_local"] = str(th.relative_to(ROOT)).replace("\\", "/")
                log.write(json.dumps({"key": c["key"], "files": meta["files"], "bytes": total, "width": w, "height": h,
                                      "thumb_local": meta.get("thumb_local"), "fetched": meta["fetched"]}) + "\n"); log.flush()
                used += total
                print(f"   ✓ {w}×{h} · {total / 1e6:.1f} MB · total {used / 1e9:.2f} GB")
            except KeyboardInterrupt:
                print("\nStopped — re-run to resume."); break
            except SystemExit as e:
                print(e)
            except Exception as e:
                print(f"   ✗ {type(e).__name__}: {str(e)[:160]}")


# ── gallery ─────────────────────────────────────────────────────────────────
def pinned_keys():
    """manifest key -> catalogue id, for works already in data/artworks.json"""
    try:
        cat = json.loads((ROOT / "data" / "artworks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for it in cat.get("items", []):
        img = it.get("image") or {}
        if img.get("commons"):
            out["commons:" + img["commons"]] = it["id"]
        for a in img.get("alt") or []:
            out["commons:" + a["commons"]] = it["id"]
        b = img.get("best")
        if b and b.get("source") and b.get("id") is not None:
            out[f"{b['source']}:{b['id']}"] = it["id"]
    return out


def gallery(args):
    items = load_manifest()
    done = load_dlog()
    pins = pinned_keys()
    for c in items:
        if c["key"] in pins:
            c["pinned"] = pins[c["key"]]
        d = done.get(c["key"])
        if d:
            c["local"] = d["files"]; c["px"] = f"{d.get('width')}×{d.get('height')}"; c["mb"] = round(d.get("bytes", 0) / 1e6, 1)
            if d.get("thumb_local"):
                c["thumb"] = "../" + d["thumb_local"]
            c["local"] = ["../" + p for p in d["files"]]
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    page = GALLERY_HTML.replace("__DATA__", data).replace("__WHEN__", datetime.now().strftime("%Y-%m-%d %H:%M"))
    out = HV / "gallery.html"
    out.write_text(page, encoding="utf-8")
    print(f"gallery: {out.relative_to(ROOT)} — {len(items)} items, {len(done)} downloaded")


GALLERY_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vantage · Harvest</title>
<style>
:root{--paper:#f3eee3;--ink:#1d2529;--ink2:#5a6266;--rule:#cbbd9c;--amber:#c8782a}
@media (prefers-color-scheme:dark){:root{--paper:#1c2022;--ink:#ece5d6;--ink2:#a9a395;--rule:#4a4538}}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.4 Georgia,serif}
header{position:sticky;top:0;z-index:2;background:var(--paper);border-bottom:1px solid var(--rule);padding:12px 18px;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
h1{font-weight:400;font-size:24px;margin:0 12px 0 0}
select,input,button{font:inherit;padding:5px 8px;border:1px solid var(--rule);border-radius:8px;background:var(--paper);color:var(--ink)}
button{cursor:pointer}#count{color:var(--ink2);font-size:14px}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px;padding:16px 18px}
.card{border:1px solid var(--rule);border-radius:10px;overflow:hidden;display:flex;flex-direction:column;background:color-mix(in srgb,var(--paper) 92%,#fff)}
.card img{width:100%;height:170px;object-fit:cover;background:#0001;display:block}
.card .b{padding:8px 10px;display:flex;flex-direction:column;gap:3px;font-size:13.5px}
.card b{font-weight:600;font-size:14.5px}.m{color:var(--ink2)}.tags{display:flex;flex-wrap:wrap;gap:4px}
.tag{font-size:11.5px;border:1px solid var(--rule);border-radius:999px;padding:0 7px}
.card.pick{outline:3px solid var(--amber)}.tag.pin{background:#2f6f7a;color:#fff;border-color:#2f6f7a}.card.pinned img{opacity:.75}label.pk{display:flex;gap:6px;align-items:center;margin-top:4px}
a{color:#2f6f7a}
</style></head><body>
<header><h1>Vantage harvest</h1>
<select id="reg"><option value="">All regions</option><option value="cape_ann">Cape Ann</option><option value="portland">Portland area</option></select>
<select id="src"><option value="">All sources</option></select>
<select id="kind"><option value="">All kinds</option><option value="art">Art</option><option value="photograph">Photos</option><option value="birdseye">Bird's-eye</option><option value="sanborn">Sanborn maps</option><option value="habs">HABS</option></select>
<select id="dl"><option value="">Any</option><option value="1">Downloaded</option><option value="0">Not yet</option></select>
<input id="q" placeholder="search title, artist, place" size="24">
<select id="pin"><option value="">Pinned or not</option><option value="1">Pinned</option><option value="0">Not pinned yet</option></select>
<label><input type="checkbox" id="onlyPicks"> picks only</label>
<button id="export">Export picks</button><span id="count"></span><span class="m" style="margin-left:auto;font-size:12px">built __WHEN__</span></header>
<main id="grid"></main>
<script>
const DATA=__DATA__;let picks={};try{picks=JSON.parse(localStorage.getItem('vantage.picks')||'{}')}catch(e){}
const $=s=>document.querySelector(s),E=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
[...new Set(DATA.map(d=>d.source))].sort().forEach(s=>$('#src').insertAdjacentHTML('beforeend',`<option>${s}</option>`));
const kindOf=d=>['photograph','birdseye','sanborn','habs'].includes(d.kind)||/photo/.test(d.kind)?(/photo/.test(d.kind)?'photograph':d.kind):'art';
function draw(){const r=$('#reg').value,s=$('#src').value,k=$('#kind').value,dl=$('#dl').value,q=$('#q').value.toLowerCase(),op=$('#onlyPicks').checked,pn=$('#pin').value;
 const rows=DATA.filter(d=>(!r||d.regions.includes(r))&&(!s||d.source===s)&&(!k||kindOf(d)===k)&&(!dl||(dl==='1')===!!d.local)&&(!op||picks[d.key])&&(!pn||(pn==='1')===!!d.pinned)&&(!q||(d.title+' '+d.artist+' '+d.places.join(' ')+' '+d.date).toLowerCase().includes(q)));
 $('#count').textContent=`${rows.length} of ${DATA.length} · ${DATA.filter(d=>d.pinned).length} pinned · ${Object.keys(picks).length} picked`;
 $('#grid').innerHTML=rows.slice(0,1500).map(d=>`<div class="card${picks[d.key]?' pick':''}${d.pinned?' pinned':''}" data-k="${E(d.key)}">
  <a href="${E(d.local?d.local[0]:d.page)}" target="_blank"><img loading="lazy" src="${E(d.thumb||'')}" alt=""></a>
  <div class="b"><b>${E(d.title)}</b><span class="m">${E(d.artist||'')} · ${E(d.date)}</span>
  <div class="tags">${d.pinned?`<span class="tag pin" title="${E(d.pinned)}">📍 pinned</span>`:''}${d.places.slice(0,4).map(p=>`<span class="tag">${E(p)}</span>`).join('')}<span class="tag">${E(d.source)}</span>${d.px?`<span class="tag">${E(d.px)} · ${d.mb} MB</span>`:''}</div>
  <span><a href="${E(d.page)}" target="_blank">source ↗</a></span>
  <label class="pk"><input type="checkbox" ${picks[d.key]?'checked':''}> use in Vantage</label></div></div>`).join('');}
$('#grid').addEventListener('change',e=>{const c=e.target.closest('.card');if(!c)return;const k=c.dataset.k;if(e.target.checked)picks[k]=1;else delete picks[k];
 try{localStorage.setItem('vantage.picks',JSON.stringify(picks))}catch(_){}c.classList.toggle('pick',!!picks[k]);draw();});
$('#export').onclick=()=>{const out=DATA.filter(d=>picks[d.key]);const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,1)],{type:'application/json'}));a.download='vantage-picks.json';a.click();};
['#reg','#src','#kind','#dl','#pin','#onlyPicks'].forEach(s=>$(s).onchange=draw);$('#q').oninput=draw;draw();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Harvest Cape Ann / Portland public-domain art from open collections.")
    ap.add_argument("step", nargs="?", default="all", choices=["all", "discover", "download", "gallery"])
    ap.add_argument("--region", default="cape_ann,portland", help="cape_ann,portland")
    ap.add_argument("--sources", default="commons,met,nga,cma,aic,loc", help="comma list: " + ",".join(SOURCES))
    ap.add_argument("--budget-gb", type=float, default=250)
    ap.add_argument("--max-file-mb", type=float, default=2500, help="skip any single file bigger than this")
    ap.add_argument("--contact", default=os.environ.get("VANTAGE_CONTACT"))
    args = ap.parse_args()
    args.region = [r.strip() for r in args.region.split(",") if r.strip()]
    args.sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    for r in args.region:
        if r not in PLACES:
            sys.exit(f"unknown region {r}")
    if args.contact:
        F.UA = F.UA.replace(")", f"; {args.contact})")
    if args.step in ("all", "discover"):
        discover(args)
    if args.step in ("all", "download"):
        download(args)
    if args.step in ("all", "gallery", "download"):
        gallery(args)


if __name__ == "__main__":
    main()
