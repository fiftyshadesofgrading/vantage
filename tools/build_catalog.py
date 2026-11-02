#!/usr/bin/env python3
"""
build_catalog.py — writes ../data/artworks.json from the CATALOG list below.

Each entry names its Wikimedia Commons file; this script works out the Commons
original / thumbnail URLs (no network needed) so the app can show images
straight away, before fetch_art.py has pulled local high-res copies.

Edit CATALOG, then:   python tools/build_catalog.py
Field notes on vantage:
  heading    compass bearing (deg, true north) the artist was looking along
  fov        approximate horizontal angle of view of the picture (deg)
  confidence documented = from a published viewpoint map / catalogue commentary
             inferred   = from the title + geography, not yet field-checked
             general    = right area, exact easel spot unknown
  access     public | private-view (scene visible, exact spot is private) | water
"""
import hashlib, json, os, sys, urllib.parse
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "artworks.json")

LANE_CR = "https://www.fitzhenrylaneonline.org/catalogue/entry.php?id="

ARTISTS = {
    "lane":     {"name": "Fitz Henry Lane", "life": "1804–1865", "color": "#c8782a"},
    "homer":    {"name": "Winslow Homer", "life": "1836–1910", "color": "#3f7fa8"},
    "hassam":   {"name": "Childe Hassam", "life": "1859–1935", "color": "#8e5ea8"},
    "hopper":   {"name": "Edward Hopper", "life": "1882–1967", "color": "#b8443c"},
    "duveneck": {"name": "Frank Duveneck", "life": "1848–1919", "color": "#4e8a5c"},
    "detroit":  {"name": "Detroit Publishing Co.", "life": "photochroms & glass negatives, c.1898–1910", "color": "#6e7b85"},
    "birdseye": {"name": "Bird's-eye view", "life": "lithographed town views", "color": "#8a7550"},
    "sloan":    {"name": "John Sloan", "life": "1871–1951", "color": "#c0503a"},
    "metcalf":  {"name": "Willard Leroy Metcalf", "life": "1858–1925", "color": "#6f9a3e"},
    "kroll":    {"name": "Leon Kroll", "life": "1884–1974", "color": "#d08a3a"},
    "beaux":    {"name": "Cecilia Beaux", "life": "1855–1942", "color": "#a85a7a"},
    "hbbrown":  {"name": "Harrison Bird Brown", "life": "1831–1915", "color": "#5a6fa8"},
}

# crop = [left, top, right, bottom] as fractions to trim (gallery photos include a sliver of frame)
G = [0.012, 0.012, 0.012, 0.012]

CATALOG = [
    # ── Harbor Cove / Fort Point / the Cut ────────────────────────────────────
    dict(id="lane-stage-fort-1862", artist="lane", title="Stage Fort across Gloucester Harbor", date="1862",
         kind="painting", medium="Oil on canvas", collection="The Metropolitan Museum of Art (1978.203)",
         commons="Stage Fort across Gloucester Harbor MET DT5586.jpg", photo="museum", best={"source": "met", "id": 11396},
         vantage=dict(lat=42.60890, lon=-70.67680, heading=185, fov=75, range=1400, confidence="documented", access="public",
                      basis="Lane's field drawing (inv. 109 + 222) and the catalogue viewpoint map",
                      note="Stand on the Stage Fort Park side of the Blynman Bridge (the Cut), at the harbor edge, looking south. Stage Head and Tablet Rock fill the right half; Eastern Point light is the speck far left."),
         blurb="Late-afternoon light on the overgrown 1620s settlement site. Lane's pencil study was ruled into eight equal panels — probably with a camera lucida — and the rocks in the painting register almost exactly with it.",
         links=[("The Met", "https://www.metmuseum.org/art/collection/search/11396"), ("Lane catalogue", LANE_CR + "237")]),

    dict(id="lane-stage-rocks-1857", artist="lane", title="Stage Rocks and Western Shore of Gloucester Outer Harbor", date="1857",
         kind="painting", medium="Oil on canvas", collection="National Gallery of Art, Washington",
         commons="Stage Rocks and Western Shore of Gloucester Outer Harbor, by Fitz Henry Lane, 1857, oil on canvas - National Gallery of Art, Washington - DSC00071.JPG",
         photo="gallery", crop=G,
         vantage=dict(lat=42.60830, lon=-70.66380, heading=250, fov=60, range=1500, confidence="documented", access="public",
                      basis="Viewpoint chart for Lane's related drawing (inv. 107): end of Fort Point, or a boat just offshore",
                      note="From the tip of Fort Point, look west-southwest across the outer harbor to the granite of Stage Head."),
         blurb="Lane wrote to a friend that he'd sketched Stage Fort 'from the water' for a client who wanted it treated as a sunset. This canvas is in unusually pristine condition — close to how it looked coming off his easel.",
         links=[("Lane catalogue", LANE_CR + "348")]),

    dict(id="lane-old-fort-1850s", artist="lane", title="The Old Fort and Ten Pound Island, Gloucester", date="1850s",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="The Old Fort and Ten Pound Island, Gloucester, by Fitz Henry Lane, 1850s, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01162.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.61170, lon=-70.66100, heading=200, fov=55, range=1600, confidence="documented", access="public",
                      basis="Catalogue commentary + proposed-viewpoint map (inv. 28/30): Duncan Street, on the fill that became Fear's Wharf",
                      note="Bottom of Duncan Street at Harbor Loop — a block from Lane's own stone house — looking down Harbor Cove toward Ten Pound Island and Eastern Point."),
         blurb="Harbor Cove as it looked in the early 1840s. A smaller unfinished version (inv. 28) shows Lane's method: he blocked in the landforms like a stage set, then populated it with vessels.",
         links=[("Lane catalogue", LANE_CR + "30")]),

    dict(id="lane-ten-pound-pavilion-1862", artist="lane", title="Ten Pound Island from Pavilion Beach", date="c.1862",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Ten Pound Island from Pavilion Beach, by Fitz Henry Lane, . 1862, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01136.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.60920, lon=-70.66620, heading=176, fov=50, range=1100, confidence="inferred", access="public",
                      basis="Title + geography (Pavilion Beach faces Ten Pound Island across the harbor mouth)",
                      note="Pavilion Beach, between the Fishermen's Memorial and Fort Point. Ten Pound Island light sits almost due south."),
         blurb="Summer southwesterlies blow straight down the outer harbor onto Pavilion Beach; Lane shows vessels running fast for the inner harbor, about to drop sail amid hundreds of others.",
         links=[("Lane catalogue", LANE_CR + "15")]),

    dict(id="lane-ten-pound-1850s", artist="lane", title="Ten Pound Island, Gloucester", date="1850s",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Ten Pound Island, Gloucester, by Fitz Henry Lane, 1850s, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01159.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.60850, lon=-70.66330, heading=194, fov=45, range=1000, confidence="inferred", access="public",
                      basis="Catalogue commentary: George Rogers's new wharf on Fort Point is the foreground",
                      note="East side of Fort Point, by the wharves, looking south to the island."),
         blurb="Hazy late-summer light. The foreground is Rogers's wharf under construction — sharpened pilings stacked at the same angle as the lumber brig coming in.",
         links=[("Lane catalogue", LANE_CR + "17")]),

    dict(id="lane-three-master-1857", artist="lane", title="Three Master on the Gloucester Railways", date="1857",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Three Master on the Gloucester Railways, by Fitz Henry Lane, 1857, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01056.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.60800, lon=-70.65600, heading=323, fov=9, range=500, confidence="documented", access="public",
                      basis="Catalogue viewpoint chart (inv. 29): tip of Rocky Neck, 9° angle of view",
                      note="North tip of Rocky Neck, looking across the inner harbor to Duncan's Point and Harbor Loop, where Maritime Gloucester keeps a working marine railway today. A very narrow view: zoom your camera in."),
         blurb="Painted as a shop sign for John Trask's paint shop at the Burnham Brothers' marine railway. The ship California is hauled out for repairs; it later hung in City Hall.",
         links=[("Lane catalogue", LANE_CR + "29")]),

    dict(id="lane-harbor-1852", artist="lane", title="Gloucester Harbor", date="1852",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Gloucester Harbor, by Fitz Henry Lane, 1852, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01203.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.60580, lon=-70.66680, heading=35, fov=80, range=1500, confidence="documented", access="water",
                      basis="Catalogue viewpoint map (inv. 38): Babson's Ledge, off Fort Point",
                      note="Lane worked from the water at Babson's Ledge. The closest dry land is the end of Pavilion Beach — look northeast at the city."),
         blurb="A panorama commissioned by Sidney Mason, who built much of the new waterfront: the whole city of 1852, its wharves and church spires, under a huge still sky.",
         links=[("Lane catalogue", LANE_CR + "38")]),

    dict(id="homer-gloucester-harbor-1873", artist="homer", title="Gloucester Harbor", date="1873",
         kind="painting", medium="Oil on canvas", collection="The Nelson-Atkins Museum of Art",
         commons="Winslow Homer - Gloucester Harbor (1873).jpg", photo="museum",
         vantage=dict(lat=42.61160, lon=-70.66620, heading=165, fov=60, range=900, confidence="general", access="public",
                      basis="Homer boarded at the corner of Main Street and Western Avenue in summer 1873",
                      note="Exact spot not documented. This pin is Homer's 1873 lodging corner — the harbor he painted is a few steps south."),
         blurb="Homer's first Gloucester summer, when he also took up watercolor in earnest. He returned in 1880 and lived with the keeper on Ten Pound Island.",
         links=[]),

    # ── Rocky Neck ────────────────────────────────────────────────────────────
    dict(id="lane-harbor-from-rocky-neck-1844", artist="lane", title="Gloucester Harbor from Rocky Neck", date="1844",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Gloucester Harbor from Rocky Neck, by Fitz Henry Lane, 1844, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01134.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.60660, lon=-70.65830, heading=340, fov=76, range=1300, confidence="documented", access="public",
                      basis="Catalogue viewpoint chart (inv. 14)",
                      note="West side of Rocky Neck, looking north-northwest across the inner harbor to downtown."),
         blurb="Painted two years before his 1846 lithograph from nearly the same spot — compare them side by side here.",
         links=[("Lane catalogue", LANE_CR + "14")]),

    dict(id="lane-view-rocky-neck-1846", artist="lane", title="View of Gloucester (From Rocky Neck)", date="1846",
         kind="lithograph", medium="Colored lithograph (Lane & Scott)", collection="Cape Ann Museum",
         commons="View of Gloucester from Rocky Neck, by Fitz Henry Lane, 1846, colored lithograph on paper by Lane and Scott's Lithography, Boston - Cape Ann Museum - Gloucester, MA - DSC01119.jpg",
         photo="gallery", crop=[0.02, 0.03, 0.02, 0.13],
         vantage=dict(lat=42.60660, lon=-70.65830, heading=330, fov=82, range=1300, confidence="documented", access="public",
                      basis="Catalogue: Rocky Neck, half the elevation and half the distance of the 1836 view; 82° angle of view",
                      note="Same spot as the 1844 painting. Harbor Cove is compressed into the bottom third of the print."),
         blurb="Lane's second Gloucester lithograph, sold to townspeople by Lane himself for a few dollars. Each of his three town views is larger and more detailed than the last.",
         links=[("Lane catalogue", LANE_CR + "92")]),

    dict(id="lane-view-of-gloucester-1855", artist="lane", title="View of Gloucester, Mass.", date="1855–59",
         kind="lithograph", medium="Lithograph (L.H. Bradford & Co.)", collection="National Gallery of Art, Washington",
         commons="Fitz Henry Lane, View of Gloucester, Mass., 1855, NGA 145208.jpg", photo="museum",
         vantage=dict(lat=42.60650, lon=-70.65850, heading=318, fov=74, range=1300, confidence="documented", access="public",
                      basis="Catalogue visual guide (inv. 446): about 50 ft south-west of the 1846 viewpoint, 74° angle of view",
                      note="A few steps from the 1846 spot. The narrower view puts Fort Point and Duncan's Point front and centre."),
         blurb="The largest and last of Lane's Gloucester prints (the NGA dates its impression 1855; the catalogue, 1859). Lane later mounted several on canvas, painted over them in oil, and sold them to friends for $25.",
         links=[("Lane catalogue", LANE_CR + "446")]),

    dict(id="lane-ten-pound-sunset-1851", artist="lane", title="Ten Pound Island at Sunset", date="1851",
         kind="painting", medium="Oil on panel", collection="Cape Ann Museum",
         commons="Ten Pound Island at Sunset, by Fitz Henry Lane, 1851, oil on panel - Cape Ann Museum - Gloucester, MA - DSC01106.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.60430, lon=-70.65830, heading=245, fov=40, range=900, confidence="inferred", access="public",
                      basis="Sunset glow behind the island ⇒ looking west from the Rocky Neck / East Gloucester shore",
                      note="Wonson Street at Stevens Lane on Rocky Neck (Rocky Neck Art Trail stop 13); the public way runs down to the water."),
         blurb="Unusually moody for Lane: two men in a skiff reach for a mooring in deep twilight. The catalogue wonders whether his student Mary Blood Mellen had a hand in it.",
         links=[("Lane catalogue", LANE_CR + "25"), ("Rocky Neck Art Trail", "https://trail.rockyneckartcolony.org/index.php/winslow-homer-and-ten-pound-island")]),

    dict(id="lane-town-of-gloucester-1836", artist="lane", title="View of the Town of Gloucester, Mass.", date="1836",
         kind="lithograph", medium="Lithograph (Pendleton's)", collection="Cleveland Museum of Art (2019.165)",
         commons="Fitz Henry Lane (American, 1804-1865), Pendleton's Lithography (American, active 1825-1836) - View of the Town of Gloucester, Mass. - 2019.165 - Cleveland Museum of Art.jpg",
         photo="museum", best={"source": "cma", "id": "2019.165"},
         vantage=dict(lat=42.60280, lon=-70.65470, heading=325, fov=92, range=1600, confidence="general", access="private-view",
                      basis="Catalogue: twice the elevation and twice the distance from Harbor Cove of the 1846 Rocky Neck view; 92° view",
                      note="Estimated: high ground in East Gloucester behind Rocky Neck. Walk the streets here and use the calibrate tool when the skyline lines up."),
         blurb="Lane's first view of his hometown, drawn on the stone himself at age 31. The high vantage gives an intimate look down on East Gloucester and a distant harbor village.",
         links=[("Lane catalogue", LANE_CR + "437")]),

    # ── Head of the harbor ────────────────────────────────────────────────────
    dict(id="lane-harbor-1847", artist="lane", title="Gloucester Harbor", date="1847",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Gloucester Harbor, by Fitz Henry Lane, 1847, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01150.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.61770, lon=-70.65050, heading=215, fov=70, range=1800, confidence="documented", access="public",
                      basis="Catalogue locator map (inv. 23): the shore at the head of the harbor — today largely filled",
                      note="The 1847 shoreline here has been filled in; stand near East Main Street at the head of the inner harbor and look down-harbor past the State Fish Pier (once Five Pound Island)."),
         blurb="Lane tries to fit his whole world into one view: wharves on both sides, Five Pound Island's fish shacks in the middle, Ten Pound light beyond, and a man caulking a boat on the beach.",
         links=[("Lane catalogue", LANE_CR + "23")]),

    # ── Middle Street ─────────────────────────────────────────────────────────
    dict(id="hassam-church-gloucester-1918", artist="hassam", title="The Church at Gloucester", date="1918",
         kind="painting", medium="Oil on canvas", collection="The Metropolitan Museum of Art",
         commons="The Church at Gloucester MET DP161219.jpg", photo="museum",
         vantage=dict(lat=42.61270, lon=-70.66550, heading=315, fov=45, range=250, confidence="inferred", access="public",
                      basis="Subject: the Independent Christian (Universalist) Church, Middle & Church Streets, 1806",
                      note="The church is certain; Hassam's exact spot isn't. Start on Middle Street south-east of the church and step around until the spire lines up."),
         blurb="Hassam painted this white Federal-style meetinghouse in 1918 and etched it the same year. Hopper painted the same steeple eight years later — all three are pinned here.",
         links=[]),

    dict(id="hassam-colonial-church-1918", artist="hassam", title="Colonial Church, Gloucester", date="1918",
         kind="print", medium="Etching", collection="National Gallery of Art, Washington",
         commons="Childe Hassam, Colonial Church, Gloucester, 1918, NGA 32764.jpg", photo="museum",
         vantage=dict(lat=42.61270, lon=-70.66550, heading=315, fov=45, range=250, confidence="inferred", access="public",
                      basis="Same church as the Met painting",
                      note="Same church, same year, as an etching."),
         blurb="Hassam's etching of the same meetinghouse.",
         links=[]),

    dict(id="hopper-universalist-church-1926", artist="hopper", title="Universalist Church", date="1926",
         kind="watercolor", medium="Watercolor", collection="Princeton University Art Museum",
         commons="Universalist Church (Edward Hopper, 1926).jpg", photo="museum",
         rights="Listed as public domain on Wikimedia Commons (US, 1926). Check the museum's terms before any public or commercial use.",
         vantage=dict(lat=42.61270, lon=-70.66550, heading=315, fov=45, range=250, confidence="inferred", access="public",
                      basis="Subject: the Universalist (Independent Christian) Church on Middle Street",
                      note="Same steeple Hassam painted in 1918."),
         blurb="Hopper first came to Gloucester in 1912 and returned in 1923, working in watercolor as Homer had fifty years before.",
         links=[]),

    # ── Western shore: the Cut, Stage Fort, Fresh Water Cove, Norman's Woe ───
    dict(id="photo-gloucester-from-stage-fort", artist="detroit", title="Gloucester, Mass. from Stage Fort Park", date="c.1900s",
         kind="photograph", medium="Photochrom print", collection="New York Public Library",
         commons="Gloucester, Mass. from Stage Fort Park, Gloucester, Mass (NYPL b12647398-75765).tiff", photo="museum",
         vantage=dict(lat=42.60520, lon=-70.67580, heading=47, fov=55, range=1500, confidence="inferred", access="public",
                      basis="Title; Stage Head is the high ground in the park facing the city",
                      note="Top of Stage Head, looking north-east across the harbor to the city skyline."),
         blurb="Photographs are the easiest overlays to line up — a lens doesn't editorialise like a painter does.",
         links=[]),

    dict(id="photo-sea-wall-stage-fort", artist="detroit", title="Along Sea Wall, Stage Fort Park", date="c.1900s",
         kind="photograph", medium="Photochrom print", collection="New York Public Library",
         commons="Along Sea Wall, Stage Fort Park, Gloucester, Mass (NYPL b12647398-75766).tiff", photo="museum",
         vantage=dict(lat=42.60700, lon=-70.67720, heading=150, fov=55, range=500, confidence="general", access="public",
                      basis="Title only", note="Somewhere along the harbor-side wall of Stage Fort Park."),
         blurb="", links=[]),

    dict(id="lane-dollivers-neck-1857", artist="lane", title="Dolliver's Neck and the Western Shore from Field Beach", date="1857",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Dolliver's Neck and the Western Shore from Field Beach, by Fitz Henry Lane, 1857, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01201.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.60350, lon=-70.67860, heading=205, fov=65, range=1300, confidence="documented", access="public",
                      basis="Catalogue viewpoint drawing (inv. 3)",
                      note="The beach just south-west of Stage Head (today's Cressy's Beach end of Stage Fort Park), looking down Fresh Water Cove to Dolliver's Neck."),
         blurb="One of the few pictures Lane described himself, in a letter to his patron Joseph Stevens: 'The effect is a mid day light with a cloudy sky, a patch of sunlight is thrown across the beach and the breaking waves…'",
         links=[("Lane catalogue", LANE_CR + "3")]),

    dict(id="lane-fresh-water-cove", artist="lane", title="Fresh Water Cove from Dolliver's Neck, Gloucester", date="early 1850s",
         kind="painting", medium="Oil on canvas", collection="Museum of Fine Arts, Boston (48.445)",
         commons="Fitz Henry Lane - Fresh Water Cove from Dolliver's Neck, Gloucester - 48.445 - Museum of Fine Arts.jpg", photo="museum",
         vantage=dict(lat=42.59400, lon=-70.68200, heading=23, fov=60, range=1400, confidence="inferred", access="private-view",
                      basis="Title + catalogue locator map",
                      note="Dolliver's Neck is private residential. You can see the same cove from Hough Avenue and the Fresh Water Cove end of Western Avenue."),
         blurb="Fresh Water Cove had a spring, a road toward Salem and shelter behind Dolliver's Neck — reasons settlers came back here in the 1650s.",
         links=[("Lane catalogue", LANE_CR + "45")]),

    dict(id="lane-sawyer-homestead-1860", artist="lane", title="Brookbank, the Sawyer Homestead", date="c.1860",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Samuel Sawyer Homestead, Freshwater Cover, Gloucester, by Fitz Henry Lane, c. 1860, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01168.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.60050, lon=-70.68350, heading=60, fov=60, range=1200, confidence="general", access="private-view",
                      basis="Subject: Samuel Sawyer's house at Fresh Water Cove, with the Fort and town behind",
                      note="Around the head of Fresh Water Cove looking north-east; exact spot unknown."),
         blurb="Sawyer — patron of Lane and of what became the Sawyer Free Library — before he added dormers to the house.",
         links=[("Lane catalogue", LANE_CR + "216")]),

    dict(id="lane-normans-woe-1862", artist="lane", title="The Western Shore with Norman's Woe", date="1862",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="The Western Shore with Norman's Woe, by Fitz Henry Lane, 1862, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01220.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.58560, lon=-70.69120, heading=212, fov=55, range=1200, confidence="documented", access="private-view",
                      basis="Catalogue viewpoint chart (inv. 18): head of Norman's Woe Cove",
                      note="Shoreline here is private; the Hammond Castle grounds next door overlook the same rock."),
         blurb="A masterpiece of Lane's late luminism — calm cove, low tide, early twilight, and Longfellow's Norman's Woe glowing in the distance.",
         links=[("Lane catalogue", LANE_CR + "18")]),

    # ── Riverdale / Annisquam River ──────────────────────────────────────────
    dict(id="lane-babson-ellery-1863", artist="lane", title="Babson and Ellery Houses, Gloucester", date="1863",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Babson and Ellery Houses by Fitz Henry Lane.png", photo="museum",
         alt=["Babson and Ellery Houses, Gloucester, by Fitz Henry Lane, 1863, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01213.jpg"],
         vantage=dict(lat=42.62190, lon=-70.67580, heading=355, fov=50, range=300, confidence="documented", access="public",
                      basis="Catalogue map showing Lane's viewpoint (inv. 10)",
                      note="Both houses still stand on Washington Street. Lane's foreground salt marsh is now the Grant Circle rotary — view from the circle's edge, carefully."),
         blurb="Commissioned by the Babson sisters before they moved west. The best place in town to see 'then and now' — the buildings are the same, the marsh is a traffic circle.",
         links=[("Lane catalogue", LANE_CR + "10")]),

    dict(id="lane-babson-meadows-1863", artist="lane", title="The Babson Meadows at Riverdale", date="1863",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="The Babson Meadows, by Fitz Henry Lane, 1863, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01217.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.62360, lon=-70.67500, heading=20, fov=60, range=700, confidence="inferred", access="private-view",
                      basis="Catalogue: the view from behind the Babson homestead over Poplar Street and the Riverdale marshes",
                      note="Behind the Babson house, looking out toward Poplar Street and the marsh."),
         blurb="Companion to the Babson and Ellery Houses picture; a hay wagon nods to the family's haying business.",
         links=[("Lane catalogue", LANE_CR + "11")]),

    dict(id="lane-done-fudging-1850s", artist="lane", title="Looking up Squam River from 'Done Fudging'", date="1850s",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Looking Up 'Squam River from 'Done Fudging', by Fitz Henry Lane, c. 1850s, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01208.jpg",
         photo="gallery", crop=G,
         vantage=dict(lat=42.62180, lon=-70.67780, heading=270, fov=60, range=1500, confidence="documented", access="public",
                      basis="Catalogue commentary: the present-day Grant Circle rotary, looking west up the Annisquam",
                      note="West edge of Grant Circle toward the Route 128 bridge."),
         blurb="'Fudging' was poling a river boat upstream against wind or tide — here you were done. Tiny canvas, enormous landscape.",
         links=[("Lane catalogue", LANE_CR + "26")]),

    # ── Eastern Point / Brace Cove ────────────────────────────────────────────
    dict(id="lane-braces-rock-1864", artist="lane", title="Brace's Rock", date="1864",
         kind="painting", medium="Oil on canvas", collection="Cape Ann Museum",
         commons="Brace's Rock, by Fitz Henry Lane, 1864, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01239.jpg",
         photo="gallery", crop=G, alt=["Fitz Henry Lane - Brace's Rock.jpg"],
         vantage=dict(lat=42.59000, lon=-70.65200, heading=135, fov=45, range=600, confidence="inferred", access="public",
                      basis="Title + geography: Brace Rock off the south-east shore of Brace Cove",
                      note="The beach between Niles Pond and Brace Cove, looking south-east. Eastern Point Boulevard is a private way beyond its gate — check the signs before walking in."),
         blurb="One of Lane's last subjects: a lone rock, a wreck, absolute stillness. He painted at least three versions, lowering the horizon each time to give the rock more presence.",
         links=[("Lane catalogue", LANE_CR + "37")]),

    dict(id="duveneck-braces-rock-1893", artist="duveneck", title="Study of Brace's Rock, Gloucester", date="c.1893",
         kind="painting", medium="Oil", collection="Cape Ann Museum",
         commons="Frank Duveneck - Study of Braces Rock, Gloucester (c.1893).jpg", photo="museum",
         vantage=dict(lat=42.59000, lon=-70.65200, heading=135, fov=45, range=600, confidence="general", access="public",
                      basis="Title", note="Same rock, thirty years after Lane."),
         blurb="Duveneck summered in Gloucester for decades; his loose study makes a good foil to Lane's glassy version.",
         links=[]),

    dict(id="photo-eastern-point-light", artist="detroit", title="Eastern Point Light", date="c.1898–1905",
         kind="photograph", medium="Photochrom print", collection="New York Public Library",
         commons="Eastern Point Light, Gloucester, Mass (NYPL b12647398-67903).tiff", photo="museum",
         vantage=dict(lat=42.58080, lon=-70.66500, heading=150, fov=50, range=200, confidence="inferred", access="public",
                      basis="Subject; the lighthouse grounds are approached from the north-west",
                      note="Lighthouse lot at the end of Eastern Point Blvd, near the start of the Dog Bar Breakwater."),
         blurb="The 1890 brick tower at the harbor mouth; the Dog Bar Breakwater was being built around the time of this card.",
         links=[]),

    dict(id="photo-mother-ann", artist="detroit", title="Mother Ann", date="c.1898–1905",
         kind="photograph", medium="Photochrom print", collection="New York Public Library",
         commons="Mother Ann, Gloucester, Mass (NYPL b12647398-67902).tiff", photo="museum",
         vantage=dict(lat=42.58050, lon=-70.66330, heading=110, fov=50, range=150, confidence="general", access="public",
                      basis="Mother Ann is the rock profile on the shore just east of Eastern Point Light",
                      note="Walk east of the lighthouse along the shore rocks."),
         blurb="A granite outcrop by the lighthouse that locals have long seen as a woman's figure.",
         links=[]),

    # ── Bass Rocks / Good Harbor / East Gloucester ───────────────────────────
    dict(id="photo-good-harbor-bass-rocks", artist="detroit", title="Good Harbor Beach, Bass Rocks", date="c.1900s",
         kind="photograph", medium="Photochrom print", collection="New York Public Library",
         commons="Good Harbor Beach, Bass Rocks, Gloucester, Mass (NYPL b12647398-75767).tiff", photo="museum",
         vantage=dict(lat=42.61500, lon=-70.63250, heading=15, fov=60, range=1000, confidence="inferred", access="public",
                      basis="Title; Bass Rocks is the headland at the beach's south end",
                      note="From the Bass Rocks end, looking up the beach toward Salt Island."),
         blurb="", links=[]),

    dict(id="photo-hawthorn-inn", artist="detroit", title="Hawthorn Inn, E. Gloucester", date="c.1900s",
         kind="photograph", medium="Photochrom print", collection="New York Public Library",
         commons="Hawthorn Inn, E. Gloucester, Mass (NYPL b12647398-75764).tiff", photo="museum",
         vantage=dict(lat=42.60180, lon=-70.65740, heading=120, fov=55, range=400, confidence="general", access="public",
                      basis="The Hawthorne Inn stood above Wonson Cove, off today's Hawthorne Lane",
                      note="Compare the shoreline and hill from across Wonson Cove."),
         blurb="One of East Gloucester's summer hotels around 1900.",
         links=[]),

    # ── Annisquam & Rockport ──────────────────────────────────────────────────
    dict(id="photo-annisquam-village", artist="detroit", title="Annisquam Village", date="c.1900s",
         kind="photograph", medium="Photochrom ('Phostint') print", collection="New York Public Library",
         commons="Annisquam Village, Gloucester, Mass (NYPL b12647398-68949).tiff", photo="museum",
         vantage=dict(lat=42.65700, lon=-70.67400, heading=20, fov=55, range=700, confidence="general", access="public",
                      basis="Title only", note="Somewhere across Lobster Cove from the village; walk the footbridge and compare."),
         blurb="", links=[]),

    dict(id="birdseye-lands-end-rockport", artist="birdseye", title="Lands End, Rockport, Mass.", date="1880s",
         kind="birdseye", medium="Lithograph, bird's-eye view (Meredith & Grew house-lot plan)", collection="Library of Congress, Geography & Map Division",
         commons="Lands End, Rockport, Mass. LOC 2007626395.jpg", photo="museum", alt=["Lands End, Rockport, Mass. LOC 2007626395.tif"],
         best={"source": "loc", "id": "2007626395"},
         vantage=dict(lat=42.64040, lon=-70.59950, heading=None, fov=None, range=None, confidence="general", access="public",
                      basis="Aerial view — no single vantage on the ground", note="A bird's-eye view advertising house lots near the Turk's Head Inn. Thacher Island's twin lights lie just offshore."),
         blurb="The kind of aerial town view that started all this — drawn from an imaginary point in the sky. Zoom in: the LOC scan is 11,751 px wide.",
         links=[("Library of Congress", "https://www.loc.gov/item/2007626395/")]),

    # ── Batch 1 (2026-11-02): from the harvest triage ──────────────────────────
    dict(id='hopper-squam-light-1912', artist='hopper', title='Squam Light',
         date='1912', kind='painting', medium='Oil on canvas', collection='Private collection',
         commons='Squam Light, by Edward Hopper.webp',
         vantage=dict(lat=42.6612, lon=-70.6802, heading=305, fov=35, range=150, confidence='inferred', access='private-view',
                      basis="Catherine Ryan's Hopper-in-Gloucester guide places it at 98 Wigwam Road, Annisquam; heading from the lighthouse position",
                      note="Wigwam Road below Annisquam Light, looking up at the tower and keeper's house. The light station grounds are closed; the road is the way to see it."),
         blurb="One of the handful of oils from Hopper's first Gloucester summer. He came back to the same light in 1923 for the watercolour Houses of 'Squam Light.",
         links=[('Hopper in Gloucester (C. Ryan)', 'https://sites.google.com/view/catherineryanartimagedesign/edward-hopper-all-around-gloucester')]),

    dict(id='hopper-prospect-street-1928', artist='hopper', title='Prospect Street, Gloucester',
         date='1928', kind='watercolor', medium='Watercolor on paper', collection='Private collection',
         commons='Prospect Street, Gloucester, by Edward Hopper.png',
         vantage=dict(lat=42.6168, lon=-70.6608, heading=90, fov=45, range=300, confidence='inferred', access='public',
                      basis='Ryan guide: houses at 98–102 Prospect Street, with the Our Lady of Good Voyage towers in the distance',
                      note='Stand outside 98–102 Prospect Street and look east along the street. The twin blue domes of Our Lady of Good Voyage are your alignment mark.'),
         blurb='Hopper came back to this stretch of Prospect Street in 1934 for the oil Sun on Prospect Street. The church towers at the end of the road make this one of the easiest pictures in Gloucester to line up.',
         links=[('Hopper in Gloucester (C. Ryan)', 'https://sites.google.com/view/catherineryanartimagedesign/edward-hopper-all-around-gloucester')]),

    dict(id='hopper-railroad-gates-1928', artist='hopper', title='Railroad Gates',
         date='1928', kind='painting', medium='Oil on canvas', collection='Collection not recorded',
         commons='Railroad Gates (1928) by Edward Hopper.jpg',
         vantage=dict(lat=42.617, lon=-70.668, heading=103, fov=50, range=400, confidence='inferred', access='public',
                      basis="Ryan guide: near the Gloucester commuter-rail stop, with St. Ann's spire (exaggerated by Hopper) as the landmark; heading toward St. Ann's, 74 Pleasant St",
                      note="By the tracks near Gloucester station, looking toward St. Ann's church. Hopper stretched the spire, so match the rooflines rather than its height."),
         blurb='Crossing gates, telegraph poles and a church spire — the railroad and the town pressed into one frame. Painted the same summer as Freight Cars, a few hundred feet away.',
         links=[('Hopper in Gloucester (C. Ryan)', 'https://sites.google.com/view/catherineryanartimagedesign/edward-hopper-all-around-gloucester')]),

    dict(id='hopper-freight-cars-1928', artist='hopper', title='Freight Cars, Gloucester',
         date='1928', kind='painting', medium='Oil on canvas', collection='Addison Gallery of American Art',
         commons='Freight Cars, Gloucester (1928) by Edward Hopper.jpg',
         vantage=dict(lat=42.6178, lon=-70.667, heading=120, fov=50, range=400, confidence='inferred', access='public',
                      basis="Ryan guide: Maplewood Avenue by the rail yard, St. Ann's spire as reference",
                      note="Maplewood Avenue beside the tracks, looking southeast past the freight siding to the houses and St. Ann's spire."),
         blurb='A wall of boxcars cutting off the town behind it. The freight yard is mostly gone, but the houses and the spire survive.',
         links=[('Hopper in Gloucester (C. Ryan)', 'https://sites.google.com/view/catherineryanartimagedesign/edward-hopper-all-around-gloucester')]),

    dict(id='hopper-gloucester-roofs-1928', artist='hopper', title='Gloucester Roofs',
         date='1928', kind='watercolor', medium='Watercolor over graphite', collection='Private collection',
         commons='Gloucester Roofs, by Edward Hopper.png',
         vantage=dict(lat=42.615, lon=-70.662, heading=180, fov=50, range=200, confidence='general', access='public',
                      basis='Ryan guide: 9 Winchester Court, reached by the public stairs from Main Street at Spring Street',
                      note='Climb the Winchester Street stairs from Main at Spring; Hopper looked down over the roofs from the railing near 9 Winchester Court.'),
         blurb="A view from a railing down onto a jumble of roofs — Hopper's favourite Gloucester subject was the houses, not the harbor.",
         links=[('Hopper in Gloucester (C. Ryan)', 'https://sites.google.com/view/catherineryanartimagedesign/edward-hopper-all-around-gloucester')]),

    dict(id='hopper-box-factory-1928', artist='hopper', title='Box Factory, Gloucester',
         date='1928', kind='watercolor', medium='Watercolor and pencil', collection='The Museum of Modern Art',
         commons='Box Factory, Gloucester, by Edward Hopper.png',
         vantage=dict(lat=42.6185, lon=-70.6668, heading=None, fov=50, range=200, confidence='general', access='public',
                      basis='Ryan guide: Cleveland Street; the building with the span over the road has been razed',
                      note='Cleveland Street, near the rail yard. The factory and its bridge are gone, so this is a then-and-now of an empty sky — match the street line.'),
         blurb="A box factory's enclosed walkway bridging the street. Gone now, which makes it a good ghost.",
         links=[('MoMA', 'https://www.moma.org/collection/works/33748'), ('Hopper in Gloucester (C. Ryan)', 'https://sites.google.com/view/catherineryanartimagedesign/edward-hopper-all-around-gloucester')]),

    dict(id='hopper-italian-quarter-1912', artist='hopper', title='Italian Quarter, Gloucester',
         date='1912', kind='painting', medium='Oil on canvas', collection='Whitney Museum of American Art',
         commons='Italian Quarter, Gloucester, by Edward Hopper.jpg',
         vantage=dict(lat=42.6107, lon=-70.6648, heading=None, fov=45, range=150, confidence='general', access='public',
                      basis='Ryan guide: The Fort, Commercial Street',
                      note='The Fort neighbourhood off Commercial Street. Look for the green house against the granite.'),
         blurb="Hopper's first Gloucester summer: a green house and its neighbours on the Fort, the old Italian fishing quarter.",
         links=[('Whitney', 'https://whitney.org/collection/works/5901'), ('Hopper in Gloucester (C. Ryan)', 'https://sites.google.com/view/catherineryanartimagedesign/edward-hopper-all-around-gloucester')]),

    dict(id='sloan-main-street-1917', artist='sloan', title='Main Street, Gloucester',
         date='1917', kind='painting', medium='Oil on canvas', collection='New Britain Museum of American Art',
         commons='Main Street, Gloucester, by John Sloan, 1917, oil on canvas - New Britain Museum of American Art - DSC09607.JPG',
         photo='gallery',
         crop=[0.03, 0.03, 0.03, 0.03],
         vantage=dict(lat=42.6125, lon=-70.6625, heading=70, fov=55, range=300, confidence='general', access='public',
                      basis="Title + the street's alignment; exact block not yet identified",
                      note='Somewhere on Main Street near City Hall, looking along the old trolley line. Walk the street with the ghost up and stop where the building line and the far end match.'),
         blurb='Shoppers, a trolley and a flag-hung street on a hot afternoon in 1917. A one-point perspective down the street — the easiest kind of picture to align in the ghost view.',
         links=[('New Britain Museum of American Art', 'https://nbmaa.org/')]),

    dict(id='sloan-gloucester-towers-1918', artist='sloan', title='Gloucester Towers',
         date='1918', kind='painting', medium='Oil on canvas', collection='Private collection',
         commons='Gloucester Towers, by John Sloan.webp',
         vantage=dict(lat=42.616, lon=-70.665, heading=145, fov=45, range=400, confidence='general', access='public',
                      basis="City Hall's tower is the square tower; vantage on the hill north of it is a guess",
                      note="From the hill above Main Street, line up City Hall's tower and the church spire beside it. Where they stand in the same relation as in the painting, you're in Sloan's spot."),
         blurb='Sloan spent five summers in East Gloucester (1914–18). Here the town is reduced to its towers against a heavy sky.',
         links=[]),

    dict(id='hassam-gloucester-harbor-1899', artist='hassam', title='Gloucester Harbor',
         date='c.1899', kind='painting', medium='Oil on canvas', collection='Norton Museum of Art',
         commons='Childe Hassam - Gloucester Harbour (c. 1899).jpg',
         vantage=dict(lat=42.6095, lon=-70.6545, heading=295, fov=60, range=1500, confidence='general', access='private-view',
                      basis='Composition: high ground in East Gloucester looking across the inner harbor to downtown',
                      note="From the slope above East Main Street, look west across the inner harbor. City Hall's tower should sit just right of centre."),
         blurb='Painted from the East Gloucester side: the whole inner harbor, the wharves and the city climbing behind.',
         links=[]),

    dict(id='hassam-drydock-1890s', artist='hassam', title='Drydock, Gloucester',
         date='1890s', kind='painting', medium='Oil on canvas', collection='Collection not recorded',
         commons='Childe Hassam - Drydock, Gloucester - Google Art Project.jpg',
         vantage=dict(lat=42.6082, lon=-70.6588, heading=None, fov=40, range=60, confidence='general', access='public',
                      basis='Subject: a schooner hauled out on a marine railway — the Rocky Neck railway is the survivor',
                      note='Gloucester Marine Railways at the tip of Rocky Neck, still hauling boats. The hull fills the frame, so this is about the scene, not a precise spot.'),
         blurb='A schooner hauled out for painting, sails slack. The Rocky Neck railway has been doing this since 1859.',
         links=[]),

    dict(id='metcalf-gloucester-harbour-1895', artist='metcalf', title='Gloucester Harbor',
         date='1895', kind='painting', medium='Oil on canvas', collection='Collection not recorded',
         commons='Willard Leroy Metcalf - Gloucester Harbour (1895).jpg',
         vantage=dict(lat=42.61, lon=-70.654, heading=280, fov=60, range=1500, confidence='general', access='private-view',
                      basis='Composition: hillside above the wharves looking across the harbor',
                      note='East Gloucester hillside, looking down over the wharves to the harbor and the city.'),
         blurb="Metcalf's summer of 1895 in Gloucester: a bright hillside view down to the wharves.",
         links=[]),

    dict(id='kroll-good-harbor-1912', artist='kroll', title='Good Harbor Beach, Gloucester',
         date='1912', kind='painting', medium='Oil on canvas', collection='Private collection',
         commons='Leon Kroll - Good Harbor Beach, Gloucester (1912).jpg',
         vantage=dict(lat=42.6205, lon=-70.629, heading=130, fov=55, range=200, confidence='inferred', access='public',
                      basis='The footbridge over the creek to Good Harbor Beach (rebuilt 2018 on the same line)',
                      note='Stand on the bank by the footbridge from the parking lot and look along it toward the beach.'),
         blurb='Bathers crossing the footbridge to Good Harbor Beach. The bridge has been rebuilt several times, always in the same place.',
         links=[]),

    dict(id='beaux-half-tide-1905', artist='beaux', title='Half-Tide, Annisquam River',
         date='c.1905', kind='painting', medium='Oil on canvas', collection='Collection not recorded',
         commons='Beaux-half-tide-annisquam-river-1905.jpg',
         vantage=dict(lat=42.651, lon=-70.683, heading=50, fov=50, range=900, confidence='general', access='private-view',
                      basis='Title; a low view across the river to the village houses',
                      note='West bank of the Annisquam River, looking across to the village. Compare the shoreline at mid-tide.'),
         blurb='Beaux, best known for portraits, summered at Green Alley in Eastern Point. This is a pure landscape: the river at mid-tide and the houses beyond.',
         links=[]),

    dict(id='lane-coffins-beach-1862', artist='lane', title="View of Coffin's Beach",
         date='1862', kind='painting', medium='Oil on canvas', collection='Museum of Fine Arts, Boston (53.383)',
         commons="Fitz Henry Lane - View of Coffin's Beach - 53.383 - Museum of Fine Arts.jpg",
         vantage=dict(lat=42.6648, lon=-70.711, heading=95, fov=70, range=4000, confidence='documented', access='public',
                      basis="Lane's inscription: 'View of Coffin's beach, from the Rocks at the Loaf, after a sketch taken, August, 1862' (catalogue inv. 41)",
                      note="The Loaf — the rocky outcrop at the Essex River end of Coffin's Beach. Look east along the beach; Annisquam and Lanesville are on the far shore."),
         blurb='Dawn over Ipswich Bay. Lane sketched it in August 1862 and inscribed exactly where he sat.',
         links=[('Lane catalogue', 'https://www.fitzhenrylaneonline.org/catalogue/entry.php?id=41')]),

    dict(id='lane-brookbank-1848', artist='lane', title='Gloucester from Brookbank',
         date='1848', kind='painting', medium='Oil on canvas', collection='Museum of Fine Arts, Boston',
         commons='Fitz Henry Lane - Gloucester from Brookbank - 48.444 - Museum of Fine Arts.jpg',
         vantage=dict(lat=42.6005, lon=-70.6835, heading=75, fov=65, range=2000, confidence='inferred', access='private-view',
                      basis="Catalogue (inv. 42): the Brookbank series looks east from the Sawyer house over Fresh Water Cove to Dolliver's Neck and the harbor",
                      note="Above Fresh Water Cove on the Sawyer homestead grounds, looking east over the cove to Dolliver's Neck and Ten Pound Island light."),
         blurb="The first of Lane's views from Brookbank, the Sawyer family's farm. Same spot as the 1860 homestead picture, twelve years earlier.",
         links=[('Lane catalogue', 'https://www.fitzhenrylaneonline.org/catalogue/entry.php?id=42')]),

    dict(id='lane-watch-house-point-1860', artist='lane', title='Watch House Point',
         date='1860', kind='painting', medium='Oil on canvas', collection='Sargent House Museum, Gloucester',
         commons='Watch House Point, by Fitz Henry Lane, 1860, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01193.jpg',
         photo='gallery',
         crop=[0.012, 0.012, 0.012, 0.012],
         vantage=dict(lat=42.6075, lon=-70.659, heading=300, fov=55, range=900, confidence='general', access='public',
                      basis="Catalogue (inv. 292) names the point (the fort on Fort Point) but not Lane's vantage; this is a guess from the composition",
                      note='From Rocky Neck, look west across the harbor to Fort Point — the old Watch House Point fort.'),
         blurb='The fort on Watch House Point at sunset, small working boats in the foreground. Lane painted this point again and again.',
         links=[('Lane catalogue', 'https://www.fitzhenrylaneonline.org/catalogue/entry.php?id=292')]),

    dict(id='lane-kettle-cove-1847', artist='lane', title='View from Kettle Cove, Manchester-by-the-Sea',
         date='1847', kind='painting', medium='Oil on canvas', collection='RISD Museum',
         commons='Fitz Henry Lane - View from Kettle Cove, Manchester-by-the-Sea - 38.068 - Rhode Island School of Design Museum.jpg',
         vantage=dict(lat=42.5765, lon=-70.734, heading=120, fov=60, range=2000, confidence='general', access='public',
                      basis='Title only',
                      note='Kettle Cove on the Manchester–Magnolia line. Look out to the islands offshore.'),
         blurb='An early, quiet Lane looking out from the Manchester shore.',
         links=[('RISD Museum', 'https://risdmuseum.org/')]),

    dict(id='lane-fort-ten-pound-1847', artist='lane', title='The Fort and Ten Pound Island, Gloucester',
         date='1847', kind='painting', medium='Oil on canvas', collection='Museo Thyssen-Bornemisza / Carmen Thyssen Collection',
         commons='Fitz Hugh Lane - The Fort and Ten Pound Island, Gloucester, Massachusetts.jpg',
         vantage=dict(lat=42.6117, lon=-70.661, heading=200, fov=60, range=1600, confidence='inferred', access='public',
                      basis='Same view as The Old Fort and Ten Pound Island (catalogue inv. 28/30): Duncan Street, looking down Harbor Cove',
                      note='Bottom of Duncan Street at Harbor Loop, looking toward the fort and Ten Pound Island.'),
         blurb="Men hauling timber on the foreshore, the fort and Ten Pound Island beyond — an earlier treatment of the view from Lane's own neighbourhood.",
         links=[]),

    dict(id='hopper-lighthouse-two-lights-1929', artist='hopper', title='The Lighthouse at Two Lights',
         date='1929', kind='painting', medium='Oil on canvas', collection='The Metropolitan Museum of Art',
         commons='Edward Hopper-Lighthouse at Two Lights.jpg',
         region='portland',
         vantage=dict(lat=43.5657, lon=-70.2008, heading=40, fov=40, range=120, confidence='inferred', access='private-view',
                      basis="Subject: the east tower of Cape Elizabeth Light with its keeper's house, seen from below",
                      note="Cape Elizabeth, below the east tower. The keeper's house is private; the view is from the end of Two Lights Road."),
         blurb="Painted in Hopper's 1927 and 1929 summers at Cape Elizabeth. Look up at the tower from below, as he did.",
         links=[]),

    dict(id='hopper-light-two-lights-1927', artist='hopper', title='Light at Two Lights',
         date='1927', kind='watercolor', medium='Watercolor on paper', collection='Collection not recorded',
         commons='Light at Two Lights.jpg',
         region='portland',
         vantage=dict(lat=43.5661, lon=-70.2012, heading=85, fov=40, range=80, confidence='inferred', access='private-view',
                      basis="Subject: the east tower beside the keeper's house",
                      note="Close in by the keeper's house, looking at the tower."),
         blurb="A watercolour from Hopper's first summer at Two Lights.",
         links=[]),

    dict(id='hopper-lighthouse-village-1929', artist='hopper', title='Lighthouse Village (Cape Elizabeth)',
         date='1929', kind='drawing', medium='Watercolor', collection='Cleveland Museum of Art (1930.851)',
         src={'web': 'https://openaccess-cdn.clevelandart.org/1930.851/1930.851_print.jpg', 'thumb': 'https://openaccess-cdn.clevelandart.org/1930.851/1930.851_web.jpg', 'full': 'https://openaccess-cdn.clevelandart.org/1930.851/1930.851_print.jpg', 'original': 'https://openaccess-cdn.clevelandart.org/1930.851/1930.851_full.tif', 'page': 'https://clevelandart.org/art/1930.851', 'width': 13041, 'height': 8429},
         best={'source': 'cma', 'id': '1930.851'},
         rights='CC0 (Cleveland Museum of Art)',
         region='portland',
         vantage=dict(lat=43.5658, lon=-70.203, heading=70, fov=50, range=250, confidence='inferred', access='public',
                      basis="Subject: the keepers' houses with the lighthouse behind, seen from the field to the west",
                      note='Along Two Lights Road west of the light, looking east to the houses with the tower rising behind.'),
         blurb="The cluster of keepers' houses and the light, laid out like a stage set. Cleveland's scan is 13,000 px wide.",
         links=[('Cleveland Museum of Art', 'https://clevelandart.org/art/1930.851')]),

    dict(id='lane-portland-harbor', artist='lane', title='View of Portland Harbor',
         date='', kind='painting', medium='Oil on canvas', collection='Museum of Fine Arts, Boston (64.438)',
         commons='Fitz Henry Lane - View of Portland Harbor - 64.438 - Museum of Fine Arts.jpg',
         region='portland',
         vantage=dict(lat=43.6675, lon=-70.244, heading=200, fov=65, range=2500, confidence='general', access='public',
                      basis='Title only; vantage still to be worked out from the shoreline in the picture',
                      note='Somewhere on Munjoy Hill or the Eastern Promenade, looking over the harbor. Compare the islands on the horizon to place it.'),
         blurb="Lane's view of Portland's harbor. Pinning it properly is a good field job: the islands on the horizon will give it away.",
         links=[('MFA Boston', 'https://www.mfa.org/collections/object/view-of-portland-harbor-33807')]),

    dict(id='brown-sugar-refinery-1860', artist='hbbrown', title='View of the Forest City Sugar Refinery, Portland, from across the Fore River',
         date='c.1860', kind='painting', medium='Oil on canvas', collection='Collection not recorded',
         commons='View of the Forest City Sugar Refinery, Portland, from across the Fore River by Harrison Bird Brown.jpg',
         photo='gallery',
         crop=[0.07, 0.09, 0.07, 0.09],
         region='portland',
         vantage=dict(lat=43.639, lon=-70.27, heading=0, fov=60, range=1500, confidence='general', access='public',
                      basis='Title: from across the Fore River (the South Portland side)',
                      note='South Portland shore of the Fore River, looking north to the West End waterfront where the refinery stood.'),
         blurb="Portland's industrial waterfront by its best-known 19th-century painter. This copy is a gallery photo, frame and all.",
         links=[]),

    dict(id='homer-cannon-rock-1895', artist='homer', title='Cannon Rock',
         date='1895', kind='painting', medium='Oil on canvas', collection='The Metropolitan Museum of Art (06.1281)',
         src={'web': 'https://images.metmuseum.org/CRDImages/ad/web-large/ap06.1281.jpg', 'thumb': 'https://images.metmuseum.org/CRDImages/ad/web-large/ap06.1281.jpg', 'full': 'https://images.metmuseum.org/CRDImages/ad/original/ap06.1281.jpg', 'original': 'https://images.metmuseum.org/CRDImages/ad/original/ap06.1281.jpg', 'page': 'https://www.metmuseum.org/art/collection/search/11113', 'width': 4000, 'height': 4000, 'approx': True},
         best={'source': 'met', 'id': 11113},
         rights='Public domain (artist died 1910); CC0 image from The Met',
         region='portland',
         vantage=dict(lat=43.5313, lon=-70.314, heading=120, fov=30, range=300, confidence='general', access='public',
                      basis="Cannon Rock lies off the shore below Homer's studio; Yankee Magazine notes it is 'off in the distance, not front and center' from the Cliff Walk",
                      note='Prouts Neck is private, but the Cliff Walk along its shore is open to the public — stay on the path. Cannon Rock is visible offshore from the ledges near the studio.'),
         blurb='Homer enlarged the rock and flattened the distance — the real Cannon Rock is a speck from the shore. A good test of how far painters bent the view.',
         links=[('The Met', 'https://www.metmuseum.org/art/collection/search/11113')]),

    dict(id='homer-west-point-1900', artist='homer', title="West Point, Prout's Neck",
         date='1900', kind='painting', medium='Oil on canvas', collection='Clark Art Institute',
         commons='Winslow Homer West Point, Prouts Neck.jpg',
         region='portland',
         vantage=dict(lat=43.5285, lon=-70.3225, heading=220, fov=45, range=300, confidence='general', access='public',
                      basis='Title: the western point of Prouts Neck, looking into the sunset',
                      note='Prouts Neck is private, but the Cliff Walk along its shore is open to the public — stay on the path. From the rocks at the western end of the Neck, look southwest at sunset.'),
         blurb="Spray thrown up against a sunset sky — Homer said he painted it 'fifteen minutes after sunset, not one minute before'.",
         links=[('Clark Art Institute', 'https://www.clarkart.edu/artpiece/detail/West-Point,-Prout-s-Neck')]),

    dict(id='homer-west-point-1884', artist='homer', title="West Point, Prout's Neck",
         date='1884', kind='watercolor', medium='Watercolor', collection='Philadelphia Museum of Art',
         commons="Winslow Homer - West Point, Prout's Neck.jpg",
         region='portland',
         vantage=dict(lat=43.5287, lon=-70.322, heading=230, fov=50, range=300, confidence='general', access='public',
                      basis='Title',
                      note='Prouts Neck is private, but the Cliff Walk along its shore is open to the public — stay on the path.'),
         blurb='The same point sixteen years earlier, in watercolour, soon after Homer settled at Prouts Neck.',
         links=[]),

    dict(id='homer-old-orchard-1883', artist='homer', title="Prout's Neck, Looking Toward Old Orchard",
         date='1883', kind='watercolor', medium='Watercolor', collection='Addison Gallery of American Art',
         commons="Winslow Homer - Prout's Neck, Looking Toward Old Orchard.jpg",
         region='portland',
         vantage=dict(lat=43.53, lon=-70.322, heading=250, fov=60, range=4000, confidence='general', access='public',
                      basis='Title: Old Orchard Beach lies west-southwest across Saco Bay',
                      note='Prouts Neck is private, but the Cliff Walk along its shore is open to the public — stay on the path. From the west side of the Neck, look across Saco Bay toward Old Orchard Beach.'),
         blurb="Homer's first summer living at Prouts Neck, looking across Saco Bay.",
         links=[]),

    dict(id='homer-the-watch-1894', artist='homer', title="The Watch, Eastern Shore, Prout's Neck",
         date='1894', kind='watercolor', medium='Watercolor', collection='Virginia Museum of Fine Arts',
         commons="Winslow Homer - The Watch, Eastern Shore, Prout's Neck (1894).jpg",
         region='portland',
         vantage=dict(lat=43.531, lon=-70.3145, heading=110, fov=45, range=200, confidence='general', access='public',
                      basis='Title: the eastern shore of the Neck',
                      note='Prouts Neck is private, but the Cliff Walk along its shore is open to the public — stay on the path.'),
         blurb="A man on the rocks hailing someone out at sea, on the shore below Homer's studio.",
         links=[]),

    dict(id='homer-high-cliff-1894', artist='homer', title='High Cliff, Coast of Maine',
         date='1894', kind='painting', medium='Oil on canvas', collection='Smithsonian American Art Museum',
         commons='High Cliff, Coast of Maine, 1894, by Winslow Homer - SAAM - DSC00845.JPG',
         photo='gallery',
         crop=[0.04, 0.05, 0.04, 0.05],
         region='portland',
         vantage=dict(lat=43.529, lon=-70.317, heading=160, fov=40, range=150, confidence='general', access='public',
                      basis="Yankee Magazine: inspired by the jagged shore on the Cliff Walk's ascent, about halfway along",
                      note='Prouts Neck is private, but the Cliff Walk along its shore is open to the public — stay on the path. About halfway along the Cliff Walk, where the path climbs.'),
         blurb='Surf breaking on the ledges partway along the Cliff Walk.',
         links=[('Finding Winslow Homer (Yankee)', 'https://newengland.com/yankee/winslow-homer-paintings/')]),

    # ── Batch 2 (2026-11-02): Cape Ann photographs + more paintings ─────────────
    dict(id='photo-annisquam-light-1904', artist='detroit', title='Annisquam Light',
         date='1904', kind='photograph', medium='Glass negative', collection='Library of Congress, Detroit Publishing Co.',
         commons='Annisquam Light, Gloucester, Massachusetts, 1904.jpg',
         best={'source': 'loc', 'id': '2016796682'},
         vantage=dict(lat=42.6606, lon=-70.6808, heading=330, fov=45, range=200, confidence='inferred', access='private-view',
                      basis="Annisquam Light's position (42.6619 N, 70.6815 W); camera assumed on the shore to the south-southeast",
                      note="Near the end of Wigwam Road, looking north-northwest at the tower and keeper's house. Pairs with Hopper's Squam Light next door."),
         blurb="The light and keeper's house eight years before Hopper painted them. A 7,000-pixel scan of the glass negative.",
         links=[('Library of Congress', 'https://www.loc.gov/item/2016796682/')]),

    dict(id='photo-surf-eastern-point', artist='detroit', title='Surf at Eastern Point',
         date='c.1898–1905', kind='photograph', medium='Photochrom', collection='NYPL Digital Collections',
         commons='Surf at Eastern Point, Gloucester, Mass (NYPL b12647398-67973).tiff',
         vantage=dict(lat=42.5795, lon=-70.6638, heading=150, fov=55, range=200, confidence='general', access='public',
                      basis='Title; Eastern Point Light at 42.5802 N, 70.6644 W',
                      note='The ledges below Eastern Point Light, by the start of the breakwater. Surf pictures need a stormy day to match.'),
         blurb='A Detroit Publishing photochrom — a black-and-white negative printed in colour by a Swiss lithographic process.',
         links=[]),

    dict(id='photo-eastern-point-1905', artist='detroit', title='Eastern Point, E. Gloucester',
         date='1905', kind='photograph', medium='Glass negative', collection='Library of Congress, Detroit Publishing Co.',
         src={'web': 'https://tile.loc.gov/storage-services/service/pnp/det/4a20000/4a23000/4a23800/4a23847v.jpg', 'thumb': 'https://tile.loc.gov/storage-services/service/pnp/det/4a20000/4a23000/4a23800/4a23847v.jpg', 'full': 'https://tile.loc.gov/storage-services/service/pnp/det/4a20000/4a23000/4a23800/4a23847v.jpg', 'original': 'https://www.loc.gov/item/2016815500/', 'page': 'https://www.loc.gov/item/2016815500/', 'width': 1024, 'height': 800, 'approx': True},
         best={'source': 'loc', 'id': '2016815500'},
         rights='Public domain / no known restrictions (Library of Congress, Detroit Publishing Co. collection).',
         vantage=dict(lat=42.583, lon=-70.662, heading=None, fov=50, range=300, confidence='general', access='public',
                      basis='Title only',
                      note='Somewhere along the Eastern Point shore. Direction not known yet.'),
         blurb='',
         links=[('Library of Congress', 'https://www.loc.gov/item/2016815500/')]),

    dict(id='photo-road-eastern-point-1905', artist='detroit', title='Road to Eastern Point, East Gloucester',
         date='1905', kind='photograph', medium='Glass negative', collection='Library of Congress, Detroit Publishing Co.',
         src={'web': 'https://tile.loc.gov/storage-services/service/pnp/det/4a20000/4a23000/4a23800/4a23848v.jpg', 'thumb': 'https://tile.loc.gov/storage-services/service/pnp/det/4a20000/4a23000/4a23800/4a23848v.jpg', 'full': 'https://tile.loc.gov/storage-services/service/pnp/det/4a20000/4a23000/4a23800/4a23848v.jpg', 'original': 'https://www.loc.gov/item/2016815501/', 'page': 'https://www.loc.gov/item/2016815501/', 'width': 1024, 'height': 800, 'approx': True},
         best={'source': 'loc', 'id': '2016815501'},
         rights='Public domain / no known restrictions (Library of Congress, Detroit Publishing Co. collection).',
         vantage=dict(lat=42.59, lon=-70.66, heading=180, fov=50, range=300, confidence='general', access='private-view',
                      basis='Title only',
                      note='Eastern Point Boulevard, heading south toward the light. Eastern Point is a private association; the road is walkable to the lighthouse lot.'),
         blurb='',
         links=[('Library of Congress', 'https://www.loc.gov/item/2016815501/')]),

    dict(id='photo-city-hall-1905', artist='detroit', title='City Hall, Gloucester',
         date='1905', kind='photograph', medium='Glass negative', collection='Library of Congress, Detroit Publishing Co.',
         src={'web': 'https://tile.loc.gov/storage-services/service/pnp/pcrd/1a00000/1a06000/1a06100/1a06135v.jpg', 'thumb': 'https://tile.loc.gov/storage-services/service/pnp/pcrd/1a00000/1a06000/1a06100/1a06135v.jpg', 'full': 'https://tile.loc.gov/storage-services/service/pnp/pcrd/1a00000/1a06000/1a06100/1a06135v.jpg', 'original': 'https://www.loc.gov/item/2025667674/', 'page': 'https://www.loc.gov/item/2025667674/', 'width': 1024, 'height': 800, 'approx': True},
         best={'source': 'loc', 'id': '2025667674'},
         rights='Public domain / no known restrictions (Library of Congress, Detroit Publishing Co. collection).',
         vantage=dict(lat=42.6132, lon=-70.6638, heading=38, fov=50, range=150, confidence='general', access='public',
                      basis='City Hall at 42.6139 N, 70.6631 W (9 Dale Avenue); camera position a guess',
                      note='Dale Avenue / Middle Street side of City Hall, looking up at the tower. Move until the tower and the corner of the building match.'),
         blurb='City Hall (1871) — the tower you can see from almost everywhere on the harbor.',
         links=[('Library of Congress', 'https://www.loc.gov/item/2025667674/')]),

    dict(id='photo-main-street-1905', artist='detroit', title='Main Street, Gloucester',
         date='1905', kind='photograph', medium='Glass negative', collection='Library of Congress, Detroit Publishing Co.',
         src={'web': 'https://tile.loc.gov/storage-services/service/pnp/det/4a20000/4a23000/4a23800/4a23838v.jpg', 'thumb': 'https://tile.loc.gov/storage-services/service/pnp/det/4a20000/4a23000/4a23800/4a23838v.jpg', 'full': 'https://tile.loc.gov/storage-services/service/pnp/det/4a20000/4a23000/4a23800/4a23838v.jpg', 'original': 'https://www.loc.gov/item/2016815492/', 'page': 'https://www.loc.gov/item/2016815492/', 'width': 1024, 'height': 800, 'approx': True},
         best={'source': 'loc', 'id': '2016815492'},
         rights='Public domain / no known restrictions (Library of Congress, Detroit Publishing Co. collection).',
         vantage=dict(lat=42.6123, lon=-70.663, heading=70, fov=50, range=300, confidence='general', access='public',
                      basis='Title only',
                      note="Main Street — same street as Sloan's 1917 painting. Walk it with both ghosts and see which block they share."),
         blurb='Main Street twelve years before Sloan painted it.',
         links=[('Library of Congress', 'https://www.loc.gov/item/2016815492/')]),

    dict(id='photo-pavilion-beach-1905', artist='detroit', title='Pavilion Beach, Gloucester',
         date='1905', kind='photograph', medium='Glass negative', collection='Library of Congress, Detroit Publishing Co.',
         src={'web': 'https://tile.loc.gov/storage-services/service/pnp/pcrd/1a00000/1a06000/1a06100/1a06131v.jpg', 'thumb': 'https://tile.loc.gov/storage-services/service/pnp/pcrd/1a00000/1a06000/1a06100/1a06131v.jpg', 'full': 'https://tile.loc.gov/storage-services/service/pnp/pcrd/1a00000/1a06000/1a06100/1a06131v.jpg', 'original': 'https://www.loc.gov/item/2025667670/', 'page': 'https://www.loc.gov/item/2025667670/', 'width': 1024, 'height': 800, 'approx': True},
         best={'source': 'loc', 'id': '2025667670'},
         rights='Public domain / no known restrictions (Library of Congress, Detroit Publishing Co. collection).',
         vantage=dict(lat=42.6095, lon=-70.6668, heading=150, fov=55, range=400, confidence='general', access='public',
                      basis='Title only',
                      note="Pavilion Beach by the Fishermen's Memorial, looking along the beach toward Fort Point."),
         blurb='',
         links=[('Library of Congress', 'https://www.loc.gov/item/2025667670/')]),

    dict(id='photo-gortons-1905', artist='detroit', title="Unloading Gorton's Codfish",
         date='1905', kind='photograph', medium='Glass negative', collection='Library of Congress, Detroit Publishing Co.',
         src={'web': 'https://tile.loc.gov/storage-services/service/pnp/det/4a10000/4a12000/4a12800/4a12860v.jpg', 'thumb': 'https://tile.loc.gov/storage-services/service/pnp/det/4a10000/4a12000/4a12800/4a12860v.jpg', 'full': 'https://tile.loc.gov/storage-services/service/pnp/det/4a10000/4a12000/4a12800/4a12860v.jpg', 'original': 'https://www.loc.gov/item/2016805472/', 'page': 'https://www.loc.gov/item/2016805472/', 'width': 1024, 'height': 800, 'approx': True},
         best={'source': 'loc', 'id': '2016805472'},
         rights='Public domain / no known restrictions (Library of Congress, Detroit Publishing Co. collection).',
         vantage=dict(lat=42.611, lon=-70.6595, heading=None, fov=50, range=100, confidence='general', access='public',
                      basis="Title; Gorton's wharves were on the inner harbor off Rogers Street",
                      note='Rogers Street waterfront. Direction not known yet.'),
         blurb="Salt cod coming ashore at Gorton's — the company is still in Gloucester.",
         links=[('Library of Congress', 'https://www.loc.gov/item/2016805472/')]),

    dict(id='photo-bass-rocks-surf', artist='detroit', title='Surf at Bass Rocks',
         date='c.1898–1905', kind='photograph', medium='Photochrom', collection='NYPL Digital Collections',
         commons='Surf at Bass Rocks, Gloucester, Mass (NYPL b12647398-68360).tiff',
         vantage=dict(lat=42.604, lon=-70.631, heading=120, fov=55, range=200, confidence='general', access='public',
                      basis='Title only',
                      note='Atlantic Road along Bass Rocks, looking out to sea.'),
         blurb='',
         links=[]),

    dict(id='photo-normans-woe', artist='detroit', title="Norman's Woe, Magnolia",
         date='c.1898–1905', kind='photograph', medium='Photochrom', collection='NYPL Digital Collections',
         commons="Norman's Woe, Magnolia, Mass (NYPL b12647398-67770).tiff",
         vantage=dict(lat=42.5785, lon=-70.699, heading=180, fov=50, range=300, confidence='inferred', access='public',
                      basis="Norman's Woe rock at 42.5764 N, 70.6994 W; camera assumed on the Hesperus Avenue shore to the north",
                      note="From the shore off Hesperus Avenue, look south to the reef 150 m offshore — the rock of Longfellow's 'Wreck of the Hesperus'."),
         blurb="The reef in Longfellow's poem. Lane painted the same shore in The Western Shore with Norman's Woe.",
         links=[]),

    dict(id='photo-rafes-chasm', artist='detroit', title="Rafe's Chasm, Magnolia",
         date='c.1898–1905', kind='photograph', medium='Photochrom', collection='NYPL Digital Collections',
         commons="Rafe's Chasm, Magnolia, Mass (NYPL b12647398-62514).tiff",
         vantage=dict(lat=42.58, lon=-70.69, heading=None, fov=40, range=60, confidence='general', access='public',
                      basis='Title only',
                      note="Rafe's Chasm park off Hesperus Avenue. Stay back from the edge."),
         blurb='A cleft in the granite where the sea booms in storms — a Victorian tourist stop.',
         links=[]),

    dict(id='photo-oceanside-magnolia', artist='detroit', title='The Oceanside, Magnolia',
         date='c.1898–1905', kind='photograph', medium='Photochrom', collection='NYPL Digital Collections',
         commons='The Oceanside, Magnolia, Mass (NYPL b12647398-66506).tiff',
         vantage=dict(lat=42.5775, lon=-70.71, heading=None, fov=50, range=200, confidence='general', access='public',
                      basis='Title only',
                      note='The Oceanside hotel stood in Magnolia village; it is long gone, so this is a pure ghost.'),
         blurb='One of the grand North Shore hotels. The building is gone; only the shoreline will match.',
         links=[]),

    dict(id='homer-harbor-ten-pound', artist='homer', title='Gloucester Harbor and Ten Pound Island',
         date='c.1880', kind='watercolor', medium='Watercolor', collection='Cape Ann Museum',
         commons='Winslow Homer - Gloucester Harbor and Ten Pound Island (c,1870).jpg',
         vantage=dict(lat=42.6066, lon=-70.6583, heading=228, fov=45, range=900, confidence='general', access='public',
                      basis='Ten Pound Island Light at 42.6019 N, 70.6656 W; heading from Rocky Neck to the light',
                      note='From Rocky Neck, look southwest to Ten Pound Island and its light. Homer boarded with the keeper on the island in 1880.'),
         blurb='Homer spent the summer of 1880 living on Ten Pound Island and painted the harbor around it over and over.',
         links=[]),

    dict(id='homer-eastern-point-light-1880', artist='homer', title='Eastern Point Light',
         date='1880', kind='watercolor', medium='Watercolor', collection='Collection not recorded',
         commons='Winslow Homer - Eastern Point Light - Google Art Project.jpg',
         vantage=dict(lat=42.585, lon=-70.662, heading=200, fov=40, range=600, confidence='general', access='public',
                      basis='Eastern Point Light at 42.5802 N, 70.6644 W; vantage on the harbor shore to the north-northeast is a guess',
                      note="From Niles Beach, look south-southwest down the harbor toward the light. Homer's view is at night, by moonlight."),
         blurb="Moonlight, schooners and the light at the harbor mouth, from Homer's Ten Pound Island summer.",
         links=[]),

    dict(id='lane-ships-in-ice', artist='lane', title='Ships in Ice off Ten Pound Island, Gloucester',
         date='n.d.', kind='painting', medium='Oil on canvas', collection='Museum of Fine Arts, Boston (48.447)',
         commons='Fitz Henry Lane - Ships in Ice off Ten Pound Island, Gloucester - 48.447 - Museum of Fine Arts.jpg',
         vantage=dict(lat=42.61, lon=-70.665, heading=183, fov=50, range=1000, confidence='general', access='public',
                      basis='Ten Pound Island Light at 42.6019 N, 70.6656 W; vantage on the Harbor Cove side is a guess',
                      note='From the Harbor Cove side of downtown, look south across the harbor to Ten Pound Island.'),
         blurb='A rare winter Lane: the harbor frozen hard enough for men to walk out to the ships.',
         links=[]),

    dict(id='hassam-bridge-bass-rocks-1918', artist='hassam', title='Bridge, Bass Rocks',
         date='1918', kind='print', medium='Etching', collection='The Metropolitan Museum of Art',
         commons='Bridge, Bass Rocks MET DP836010.jpg',
         vantage=dict(lat=42.6205, lon=-70.629, heading=130, fov=55, range=200, confidence='general', access='public',
                      basis="Probably the Good Harbor Beach footbridge (Bass Rocks lies just south); shares Kroll's pin until checked",
                      note="The footbridge over the creek to Good Harbor Beach. If the shoreline doesn't match, try the Bass Rocks side."),
         blurb="An etching from Hassam's 1918 Gloucester summer — compare it with Kroll's painting of the footbridge.",
         links=[]),

    dict(id='hassam-inner-harbor-etching', artist='hassam', title='Inner Harbor, Gloucester',
         date='1923', kind='print', medium='Etching', collection='National Gallery of Art',
         commons='Inner harbor, Gloucester - DPLA - 0d51ccdb858ff374fe98852f82f6405e.jpg',
         vantage=dict(lat=42.6095, lon=-70.656, heading=300, fov=50, range=800, confidence='general', access='public',
                      basis='Title; East Gloucester side looking across the inner harbor',
                      note='From the East Gloucester shore, look northwest across the inner harbor.'),
         blurb='',
         links=[('NGA', 'https://www.nga.gov/collection/art-object-page.182661.html')]),

    dict(id='hopper-briar-neck-1912', artist='hopper', title='Briar Neck, Gloucester',
         date='1912', kind='painting', medium='Oil on canvas', collection='Whitney Museum of American Art',
         commons='Briar Neck, Gloucester, by Edward Hopper.jpg',
         vantage=dict(lat=42.6205, lon=-70.6195, heading=110, fov=50, range=300, confidence='general', access='private-view',
                      basis='Title only; Briar Neck is the point between Good Harbor and Long Beach',
                      note='Briar Neck, looking out to sea. Mostly private homes; the shore road gives the view.'),
         blurb="Hopper's first Gloucester summer, 1912: hard sun on the granite and a deep blue sea.",
         links=[('Whitney', 'https://whitney.org/collection/works/5900')]),

    dict(id='hopper-cape-ann-granite-1928', artist='hopper', title='Cape Ann Granite',
         date='1928', kind='painting', medium='Oil on canvas', collection='Private collection',
         commons='Cape Ann Granite, by Edward Hopper.png',
         vantage=dict(lat=42.64, lon=-70.65, heading=None, fov=50, range=200, confidence='general', access='public',
                      basis='Subject: glacial boulders on open pasture, as at Dogtown',
                      note='Dogtown, the boulder-strewn upland in the middle of Cape Ann.'),
         blurb='Boulders on a bare hillside — Dogtown before the trees grew back.',
         links=[]),

    dict(id='sloan-fishing-port-1916', artist='sloan', title='Fishing Port, Gloucester',
         date='1916', kind='painting', medium='Oil on canvas', collection='Private collection',
         commons='Fishing Port, Gloucester, by John Sloan.webp',
         vantage=dict(lat=42.6145, lon=-70.66, heading=180, fov=55, range=800, confidence='general', access='public',
                      basis='Composition: a high view down onto wharves and the harbor',
                      note='From high ground above the waterfront, look down over the wharves to the harbor.'),
         blurb='',
         links=[]),


    # ── Featured: landing-page painting ─────────────────────────────────────────
    dict(id="lane-calm-sea-1860", artist="lane", title="A Calm Sea", date="c.1860",
         kind="painting", medium="Oil on canvas, 24 x 26 1/4 in.", collection="Cape Ann Museum (642.13b)",
         src={"web": "art/feature/lane-calm-sea.jpg", "thumb": "art/feature/lane-calm-sea.jpg", "full": "art/feature/lane-calm-sea.jpg",
              "original": "art/feature/lane-calm-sea.jpg", "page": LANE_CR + "6", "width": 1050, "height": 960, "approx": True},
         rights="Painting: public domain (artist died 1865). Photograph: Cape Ann Museum / Fitz Henry Lane Online — credit the museum.",
         region="new_york",
         vantage=dict(lat=40.63550, lon=-74.07900, heading=97, fov=60, range=6000, confidence="documented", access="public",
                      basis="Lane catalogue (inv. 6), reconstructed from a contemporary chart: 'probably on the northeast shore of Staten Island, just above the quarantine hospital at Tompkinsville', looking 'a few degrees south of due east'",
                      note="Staten Island, on the slope above Tompkinsville. Look just south of east across the Upper Bay to the low Brooklyn shore running from Flatbush down to Fort Hamilton."),
         blurb="A glassy calm in New York's Upper Bay. It belongs to the Cape Ann Museum, and the catalogue's viewpoint chart puts Lane on Staten Island, looking across to the Brooklyn shore.",
         links=[("Lane catalogue", LANE_CR + "6")]),
]


def commons_paths(name):
    under = name.replace(" ", "_")
    h = hashlib.md5(under.encode("utf-8")).hexdigest()
    return under, f"{h[0]}/{h[:2]}"


def q(s):
    return urllib.parse.quote(s, safe="")


def thumb_url(name, width):
    under, p = commons_paths(name)
    ext = under.rsplit(".", 1)[-1].lower()
    if ext in ("tif", "tiff"):
        tn = f"lossy-page1-{width}px-{under}.jpg"
    else:
        tn = f"{width}px-{under}"
        if len(tn.encode()) > 160:
            tn = f"{width}px-thumbnail.{under.rsplit('.', 1)[-1]}"
    return f"https://thumb.wikimedia.org/wikipedia/commons/thumb/{p}/{q(under)}/{q(tn)}"


def orig_url(name):
    under, p = commons_paths(name)
    return f"https://upload.wikimedia.org/wikipedia/commons/{p}/{q(under)}"


# pixel sizes from the Commons API (2026-11-01) — used to choose thumbnail buckets
SIZES = {
    "Stage Fort across Gloucester Harbor MET DT5586.jpg": (3811, 2281),
    "Stage Rocks and Western Shore of Gloucester Outer Harbor, by Fitz Henry Lane, 1857, oil on canvas - National Gallery of Art, Washington - DSC00071.JPG": (4205, 2593),
    "The Old Fort and Ten Pound Island, Gloucester, by Fitz Henry Lane, 1850s, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01162.jpg": (5064, 3094),
    "Ten Pound Island from Pavilion Beach, by Fitz Henry Lane, . 1862, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01136.jpg": (5179, 3167),
    "Ten Pound Island, Gloucester, by Fitz Henry Lane, 1850s, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01159.jpg": (4714, 2807),
    "Three Master on the Gloucester Railways, by Fitz Henry Lane, 1857, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01056.jpg": (4646, 3118),
    "Gloucester Harbor, by Fitz Henry Lane, 1852, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01203.jpg": (4766, 2759),
    "Winslow Homer - Gloucester Harbor (1873).jpg": (3999, 2746),
    "Gloucester Harbor from Rocky Neck, by Fitz Henry Lane, 1844, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01134.jpg": (4671, 3367),
    "View of Gloucester from Rocky Neck, by Fitz Henry Lane, 1846, colored lithograph on paper by Lane and Scott's Lithography, Boston - Cape Ann Museum - Gloucester, MA - DSC01119.jpg": (4343, 3199),
    "Fitz Henry Lane, View of Gloucester, Mass., 1855, NGA 145208.jpg": (4000, 2645),
    "Ten Pound Island at Sunset, by Fitz Henry Lane, 1851, oil on panel - Cape Ann Museum - Gloucester, MA - DSC01106.jpg": (4011, 2724),
    "Fitz Henry Lane (American, 1804-1865), Pendleton's Lithography (American, active 1825-1836) - View of the Town of Gloucester, Mass. - 2019.165 - Cleveland Museum of Art.jpg": (3400, 2448),
    "Gloucester Harbor, by Fitz Henry Lane, 1847, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01150.jpg": (4860, 3182),
    "The Church at Gloucester MET DP161219.jpg": (3240, 3846),
    "Childe Hassam, Colonial Church, Gloucester, 1918, NGA 32764.jpg": (3018, 4000),
    "Universalist Church (Edward Hopper, 1926).jpg": (4398, 3114),
    "Gloucester, Mass. from Stage Fort Park, Gloucester, Mass (NYPL b12647398-75765).tiff": (2400, 1590),
    "Along Sea Wall, Stage Fort Park, Gloucester, Mass (NYPL b12647398-75766).tiff": (2360, 1581),
    "Dolliver's Neck and the Western Shore from Field Beach, by Fitz Henry Lane, 1857, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01201.jpg": (4712, 2839),
    "Fitz Henry Lane - Fresh Water Cove from Dolliver's Neck, Gloucester - 48.445 - Museum of Fine Arts.jpg": (1600, 1057),
    "Samuel Sawyer Homestead, Freshwater Cover, Gloucester, by Fitz Henry Lane, c. 1860, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01168.jpg": (5007, 2986),
    "The Western Shore with Norman's Woe, by Fitz Henry Lane, 1862, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01220.jpg": (4691, 2844),
    "Babson and Ellery Houses by Fitz Henry Lane.png": (2500, 1509),
    "Babson and Ellery Houses, Gloucester, by Fitz Henry Lane, 1863, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01213.jpg": (5076, 3070),
    "The Babson Meadows, by Fitz Henry Lane, 1863, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01217.jpg": (5231, 3217),
    "Looking Up 'Squam River from 'Done Fudging', by Fitz Henry Lane, c. 1850s, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01208.jpg": (4347, 2567),
    "Brace's Rock, by Fitz Henry Lane, 1864, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01239.jpg": (4815, 3084),
    "Fitz Henry Lane - Brace's Rock.jpg": (2694, 1759),
    "Frank Duveneck - Study of Braces Rock, Gloucester (c.1893).jpg": (1410, 819),
    "Eastern Point Light, Gloucester, Mass (NYPL b12647398-67903).tiff": (2432, 1652),
    "Mother Ann, Gloucester, Mass (NYPL b12647398-67902).tiff": (2456, 1670),
    "Good Harbor Beach, Bass Rocks, Gloucester, Mass (NYPL b12647398-75767).tiff": (2376, 1599),
    "Hawthorn Inn, E. Gloucester, Mass (NYPL b12647398-75764).tiff": (2384, 1572),
    "Annisquam Village, Gloucester, Mass (NYPL b12647398-68949).tiff": (2392, 1579),
    "Lands End, Rockport, Mass. LOC 2007626395.jpg": (11751, 8594),
    "Lands End, Rockport, Mass. LOC 2007626395.tif": (11751, 8594),
    # batch 1
    'Squam Light, by Edward Hopper.webp': (2880, 2407),
    'Prospect Street, Gloucester, by Edward Hopper.png': (1007, 695),
    'Railroad Gates (1928) by Edward Hopper.jpg': (1000, 643),
    'Freight Cars, Gloucester (1928) by Edward Hopper.jpg': (1000, 738),
    'Gloucester Roofs, by Edward Hopper.png': (1007, 698),
    'Box Factory, Gloucester, by Edward Hopper.png': (1081, 739),
    'Italian Quarter, Gloucester, by Edward Hopper.jpg': (2048, 1690),
    'Main Street, Gloucester, by John Sloan, 1917, oil on canvas - New Britain Museum of American Art - DSC09607.JPG': (4255, 3475),
    'Gloucester Towers, by John Sloan.webp': (2880, 2280),
    'Childe Hassam - Gloucester Harbour (c. 1899).jpg': (1341, 1284),
    'Childe Hassam - Drydock, Gloucester - Google Art Project.jpg': (4001, 2794),
    'Leon Kroll - Good Harbor Beach, Gloucester (1912).jpg': (4000, 3242),
    'Beaux-half-tide-annisquam-river-1905.jpg': (2304, 1824),
    'Willard Leroy Metcalf - Gloucester Harbour (1895).jpg': (1800, 1599),
    'Watch House Point, by Fitz Henry Lane, 1860, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01193.jpg': (4618, 3132),
    "Fitz Henry Lane - View of Coffin's Beach - 53.383 - Museum of Fine Arts.jpg": (1600, 993),
    'Fitz Henry Lane - Gloucester from Brookbank - 48.444 - Museum of Fine Arts.jpg': (1600, 1072),
    'Fitz Henry Lane - View from Kettle Cove, Manchester-by-the-Sea - 38.068 - Rhode Island School of Design Museum.jpg': (1024, 680),
    'Fitz Hugh Lane - The Fort and Ten Pound Island, Gloucester, Massachusetts.jpg': (2000, 1338),
    'Edward Hopper-Lighthouse at Two Lights.jpg': (1463, 1000),
    'Light at Two Lights.jpg': (3840, 2416),
    'Fitz Henry Lane - View of Portland Harbor - 64.438 - Museum of Fine Arts.jpg': (1600, 1078),
    'View of the Forest City Sugar Refinery, Portland, from across the Fore River by Harrison Bird Brown.jpg': (2360, 1432),
    'Winslow Homer West Point, Prouts Neck.jpg': (9983, 6207),
    "Winslow Homer - West Point, Prout's Neck.jpg": (4096, 2916),
    "Winslow Homer - Prout's Neck, Looking Toward Old Orchard.jpg": (900, 643),
    "Winslow Homer - The Watch, Eastern Shore, Prout's Neck (1894).jpg": (1200, 846),
    'High Cliff, Coast of Maine, 1894, by Winslow Homer - SAAM - DSC00845.JPG': (3983, 3143),
    # batch 2
    'Annisquam Light, Gloucester, Massachusetts, 1904.jpg': (7214, 5572),
    'Surf at Eastern Point, Gloucester, Mass (NYPL b12647398-67973).tiff': (2448, 1652),
    'Surf at Bass Rocks, Gloucester, Mass (NYPL b12647398-68360).tiff': (2384, 1563),
    "Norman's Woe, Magnolia, Mass (NYPL b12647398-67770).tiff": (2472, 1625),
    "Rafe's Chasm, Magnolia, Mass (NYPL b12647398-62514).tiff": (1561, 2408),
    'The Oceanside, Magnolia, Mass (NYPL b12647398-66506).tiff': (2424, 1527),
    'Winslow Homer - Gloucester Harbor and Ten Pound Island (c,1870).jpg': (1000, 674),
    'Winslow Homer - Eastern Point Light - Google Art Project.jpg': (4427, 3217),
    'Fitz Henry Lane - Ships in Ice off Ten Pound Island, Gloucester - 48.447 - Museum of Fine Arts.jpg': (1600, 999),
    'Bridge, Bass Rocks MET DP836010.jpg': (3548, 2548),
    'Inner harbor, Gloucester - DPLA - 0d51ccdb858ff374fe98852f82f6405e.jpg': (4935, 3711),
    'Briar Neck, Gloucester, by Edward Hopper.jpg': (2048, 1693),
    'Cape Ann Granite, by Edward Hopper.png': (1008, 720),
    'Fishing Port, Gloucester, by John Sloan.webp': (2880, 2407),
}

RIGHTS = {
    "lane": "Public domain (artist died 1865).",
    "homer": "Public domain (artist died 1910).",
    "duveneck": "Public domain (artist died 1919).",
    "hassam": "Public domain in the US (published before 1931).",
    "detroit": "Public domain (Detroit Publishing Co., pre-1929; NYPL Digital Collections).",
    "birdseye": "Public domain / no known restrictions (Library of Congress).",
    "hopper": "Public domain in the US (made and published before 1931).",
    "sloan": "Public domain in the US (published before 1931).",
    "metcalf": "Public domain (artist died 1925).",
    "kroll": "Public domain in the US (published before 1931).",
    "beaux": "Public domain in the US (published before 1931).",
    "hbbrown": "Public domain (artist died 1915).",
}


def image_block(e):
    if e.get("src"):            # museum-hosted image, not on Commons
        s = e["src"]
        blk = {"commons": None, "page": s["page"], "width": s["width"], "height": s["height"],
               "web": s["web"], "thumb": s["thumb"], "full": s["full"], "original": s["original"],
               "photo": e.get("photo", "museum"), "crop": e.get("crop")}
        if s.get("approx"):
            blk["approx"] = True   # pixel size unknown; aspect only
        if e.get("best"):
            blk["best"] = e["best"]
        return blk
    name = e["commons"]
    w, h = SIZES[name]
    is_tif = name.lower().endswith((".tif", ".tiff"))
    web = thumb_url(name, 1920) if w > 1920 else orig_url(name)
    thumb = thumb_url(name, 500) if w > 500 else orig_url(name)
    if w > 3840:
        full = thumb_url(name, 3840)
    elif is_tif:
        full = thumb_url(name, 1920) if w > 1920 else orig_url(name)  # browsers can't show TIFF
    else:
        full = orig_url(name)
    blk = {
        "commons": name,
        "page": "https://commons.wikimedia.org/wiki/File:" + q(name.replace(" ", "_")),
        "width": w, "height": h,
        "web": web, "thumb": thumb, "full": full,
        "original": orig_url(name),
        "photo": e.get("photo", "museum"),
        "crop": e.get("crop"),
    }
    if e.get("best"):
        blk["best"] = e["best"]
    if e.get("alt"):
        blk["alt"] = [{"commons": a, "original": orig_url(a), "width": SIZES[a][0], "height": SIZES[a][1]} for a in e["alt"]]
    return blk


def main():
    items = []
    seen = set()
    for e in CATALOG:
        assert e["id"] not in seen, e["id"]
        seen.add(e["id"])
        it = {k: e[k] for k in ("id", "artist", "title", "date", "kind", "medium", "collection")}
        it["vantage"] = e["vantage"]
        it["image"] = image_block(e)
        it["rights"] = e.get("rights") or RIGHTS[e["artist"]]
        it["blurb"] = e.get("blurb", "")
        it["links"] = [{"label": l, "url": u} for l, u in e.get("links", [])]
        if it["image"]["commons"]:
            it["links"].append({"label": "Wikimedia Commons", "url": it["image"]["page"]})
        it["region"] = e.get("region", "cape_ann")
        items.append(it)
    doc = {
        "name": "Vantage — Cape Ann",
        "version": 1,
        "updated": date.today().isoformat(),
        "region": {"center": [42.6085, -70.6640], "zoom": 15},
        "artists": ARTISTS,
        "items": items,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"wrote {len(items)} items -> {os.path.relpath(OUT)}")
    if "--urls" in sys.argv:
        for it in items:
            print(it["image"]["web"]); print(it["image"]["thumb"]); print(it["image"]["full"])


if __name__ == "__main__":
    main()
