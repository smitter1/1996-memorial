import json
import re
from difflib import SequenceMatcher
from html import escape
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path.cwd()
DATA_PATH = ROOT / "1996_Classmates_AGGREGATE_Memorial.json"
OUT_DIR = ROOT / "docs"
CLASSMATES_DIR = OUT_DIR / "classmates"
IMAGES_DIR = ROOT / "images"
SITE_IMAGES_DIR = OUT_DIR / "images"

data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
classmates = data.get("classmates", [])

# Numeric prefix convention used by uploaded photos (1_..., 2_..., etc.) — derived from JSON order
PERSON_INDEX = {p.get("id"): i + 1 for i, p in enumerate(classmates)}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def normalize(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def format_date(date_obj):
    if not date_obj or not date_obj.get("year"):
        return "Unknown"
    if not date_obj.get("month"):
        return str(date_obj["year"])
    months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    month = months[date_obj["month"] - 1] if 1 <= date_obj["month"] <= 12 else ""
    if date_obj.get("day"):
        return f"{month} {date_obj['day']}, {date_obj['year']}"
    return f"{month} {date_obj['year']}"


def life_span(person):
    born = format_date(person.get("dates", {}).get("born"))
    died = format_date(person.get("dates", {}).get("died"))
    return f"{born} - {died}"


def is_image_url(url):
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


def image_path_for_page(image_path, page_kind):
    # page_kind: "index" or "profile"
    if isinstance(image_path, Path):
        if OUT_DIR in image_path.parents:
            rel = image_path.relative_to(OUT_DIR).as_posix()
            return f"./{rel}" if page_kind == "index" else f"../{rel}"
        rel = image_path.relative_to(ROOT).as_posix()
        return f"../{rel}" if page_kind == "index" else f"../../{rel}"
    return image_path


def collect_remote_images(person):
    out = []
    for p in person.get("photos", []):
        remote = p.get("url") or p.get("source_url")
        if remote and is_image_url(remote):
            out.append(remote)
    return out


def person_keys(person):
    raw_names = [
        person.get("id"),
        person.get("common_name"),
        person.get("full_name"),
        person.get("maiden_name"),
    ]
    keys = {normalize(v) for v in raw_names if v}
    for name in raw_names:
        if not name:
            continue
        parts = re.split(r"[\s\-_().]+", str(name))
        for part in parts:
            n = normalize(part)
            if len(n) >= 4:
                keys.add(n)
    keys.discard("")
    return keys


def score_local_image(person, image_file):
    stem = normalize(image_file.stem)
    name = normalize(image_file.name)
    keys = person_keys(person)
    score = 0

    # Definitive match: filename starts with the person's index prefix (e.g. "6_*" for Stefanie)
    index = PERSON_INDEX.get(person.get("id"))
    if index is not None:
        m = re.match(r"^(\d+)[_\-]", image_file.name)
        if m and int(m.group(1)) == index:
            score += 200

    for key in keys:
        if not key:
            continue
        if stem == key:
            score += 100
        if name.startswith(key):
            score += 60
        if key in name:
            score += 30
        ratio = SequenceMatcher(None, key, stem).ratio()
        if ratio >= 0.8:
            score += int(ratio * 25)
    return score


def collect_local_images(person, local_files):
    scored = []
    for f in local_files:
        s = score_local_image(person, f)
        if s > 0:
            scored.append((s, f.name.lower(), f))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [item[2] for item in scored]


def choose_images(person, local_files):
    local = collect_local_images(person, local_files)
    remote = collect_remote_images(person)

    primary = local[0] if local else (remote[0] if remote else None)

    secondary = []
    if local:
        secondary.extend(local[1:])

    # Only fall back to remote photos when no local secondaries are available
    if not secondary:
        for r in remote:
            if r != primary:
                secondary.append(r)

    return primary, secondary


def render_list(items, render_item):
    if not items:
        return "<p>Not available.</p>"
    rows = "".join(f"<li>{render_item(item)}</li>" for item in items)
    return f"<ul>{rows}</ul>"


def section(title, content):
    return f"<section><h2>{escape(title)}</h2>{content}</section>"


def person_page(person):
    primary, secondary = choose_images(person, local_image_files)
    main_photo = image_path_for_page(primary, "profile") if primary else None
    education = render_list(
        person.get("education"),
        lambda e: escape(
            " | ".join(
                str(v)
                for v in [e.get("institution"), e.get("degree"), e.get("field"), e.get("year")]
                if v
            )
        ),
    )
    career = render_list(
        person.get("career"),
        lambda c: escape(
            " | ".join(
                str(v)
                for v in [c.get("role"), c.get("employer"), c.get("location"), c.get("period") or c.get("duration")]
                if v
            )
        ),
    )
    family_obj = person.get("family") if isinstance(person.get("family"), dict) else {}
    if family_obj:
        family_items = []
        for key, value in family_obj.items():
            pretty = ", ".join(value) if isinstance(value, list) else str(value)
            family_items.append(f"<li><strong>{escape(key.replace('_', ' '))}:</strong> {escape(pretty)}</li>")
        family = f"<ul>{''.join(family_items)}</ul>"
    else:
        family = "<p>Not available.</p>"

    interests = person.get("interests")
    interests_html = (
        f"<p>{escape(' | '.join(interests))}</p>" if isinstance(interests, list) and interests else "<p>Not available.</p>"
    )

    obituary = person.get("obituary", {})
    obituary_text = obituary.get("text") or obituary.get("excerpt") or obituary.get("summary") or "Not available."

    sources = render_list(
        person.get("sources"),
        lambda s: (
            f'<a href="{escape(s.get("url", ""))}" target="_blank" rel="noopener noreferrer">{escape(s.get("label") or s.get("url", ""))}</a>'
            if s.get("url")
            else escape(s.get("label", "Source"))
        ),
    )

    secondary_html = "".join(
        f'<a class="lightbox-trigger" href="{escape(image_path_for_page(img, "profile"))}" title="Click to enlarge">'
        f'<img src="{escape(image_path_for_page(img, "profile"))}" alt="Additional photo of {escape(person.get("common_name") or person.get("full_name", ""))}" loading="lazy" />'
        f'</a>'
        for img in secondary
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(person.get("common_name") or person.get("full_name", ""))} | Class of 1996 Memorial</title>
  <link rel="icon" type="image/png" href="../favicon.png" />
  <link rel="apple-touch-icon" href="../apple-touch-icon.png" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Lora:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" />
  <link rel="stylesheet" href="../styles.css" />
  <script defer src="../lightbox.js"></script>
</head>
<body>
  <main class="container">
    <nav class="back-link"><a href="../index.html">← Back to classmates</a></nav>
    <div class="person-hero">
      <div class="person-hero-left">
        <header class="person-header">
          <h1>{escape(person.get("full_name", ""))}</h1>
          <p class="dates">{escape(life_span(person))}</p>
        </header>
        {section("Biography", f"<p>{escape(person.get('biography', 'Not available.'))}</p>")}
      </div>
      <div class="person-hero-right">
        {'<a class="lightbox-trigger" href="' + escape(main_photo) + '" title="Click to enlarge"><img class="portrait" src="' + escape(main_photo) + '" alt="Photo of ' + escape(person.get("common_name") or person.get("full_name", "")) + '" loading="lazy" /></a>' if main_photo else '<div class="portrait placeholder">No photo available</div>'}
      </div>
    </div>
    {section("Photos", f'<div class="gallery">{secondary_html}</div>' if secondary_html else "<p>No additional photos available.</p>")}
    {section("Education", education)}
    {section("Career", career)}
    {section("Family", family)}
    {section("Interests", interests_html)}
    {section("Obituary", f"<p>{escape(obituary_text)}</p>")}
    {section("Memorial Legacy", f"<p>{escape(person.get('memorial_legacy', 'Not available.'))}</p>")}
    {section("Sources", sources)}
  </main>
</body>
</html>"""


def index_page():
    cards = []
    for person in classmates:
        primary, _ = choose_images(person, local_image_files)
        photo = image_path_for_page(primary, "index") if primary else None
        bio = person.get("biography", "")
        excerpt = bio if len(bio) <= 220 else f"{bio[:217]}..."
        person_url = f"./classmates/{escape(person.get('id', ''))}.html"
        photo_html = (
            f'<a class="card-photo" href="{person_url}"><img src="{escape(photo)}" alt="Photo of {escape(person.get("common_name") or person.get("full_name", ""))}" loading="lazy" /></a>'
            if photo
            else '<div class="thumb placeholder">No photo available</div>'
        )
        cards.append(
            f"""<article class="card">
        {photo_html}
        <div class="card-body">
          <h2>{escape(person.get("full_name", ""))}</h2>
          <p class="dates">{escape(life_span(person))}</p>
          <p class="excerpt">{escape(excerpt)}</p>
          <a class="card-link" href="{person_url}">Read full memorial <span aria-hidden="true">&rarr;</span></a>
        </div>
      </article>"""
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Classmates We Remember | UCLA Anderson MBA 1996</title>
  <link rel="icon" type="image/png" href="./favicon.png" />
  <link rel="apple-touch-icon" href="./apple-touch-icon.png" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Lora:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" />
  <link rel="stylesheet" href="./styles.css" />
</head>
<body>
  <main class="container">
    <header class="site-header">
      <h1>{escape(data.get("document", {}).get("title", "Classmates We Remember"))}</h1>
      <div class="ornament" aria-hidden="true"></div>
      <p class="subtitle">{escape(data.get("document", {}).get("subtitle", ""))}</p>
      <p class="intro">This memorial dossier honors our deceased classmates who we promise to keep in our collective memory for all time.</p>
    </header>
    <section class="grid">
      {''.join(cards)}
    </section>
  </main>
</body>
</html>"""


css = """:root {
  --bg: #F7F4EF;
  --card: #FFFCF8;
  --heading: #1F3A56;
  --text: #2F3A45;
  --muted: #6B7280;
  --accent: #2E5B86;
  --accent-hover: #1F3A56;
  --border: #E6DFD4;
  --serif: "Lora", Georgia, "Times New Roman", serif;
  --sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: var(--sans);
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.container {
  width: min(1140px, 92%);
  margin: 3rem auto 4rem;
}

h1, h2, h3 {
  font-family: var(--serif);
  color: var(--heading);
  line-height: 1.2;
  font-weight: 600;
  letter-spacing: -0.01em;
}

p { margin: 0 0 .75rem; }

a {
  color: var(--accent);
  text-decoration: none;
  transition: color .15s ease;
}
a:hover { color: var(--accent-hover); text-decoration: underline; }

.muted, .dates, .subtitle { color: var(--muted); }
.dates { font-size: .95rem; margin: .25rem 0 .6rem; }

/* ---------- Site header (homepage) ---------- */

.site-header {
  text-align: center;
  margin-bottom: 2.5rem;
}

.site-header h1 {
  font-size: clamp(2.2rem, 4.5vw, 3.4rem);
  margin: 0 0 .6rem;
}

.site-header .subtitle {
  font-family: var(--serif);
  font-size: 1.15rem;
  color: var(--heading);
  margin: 0 0 1rem;
  font-style: normal;
}

.site-header .intro {
  max-width: 620px;
  margin: 0 auto;
  color: var(--muted);
}

.ornament {
  width: 80px;
  height: 14px;
  margin: .6rem auto 1rem;
  background-image: linear-gradient(to right, transparent 0%, var(--border) 20%, var(--border) 80%, transparent 100%);
  background-size: 100% 1px;
  background-position: center;
  background-repeat: no-repeat;
  position: relative;
}

.ornament::before,
.ornament::after {
  content: "";
  position: absolute;
  top: 50%;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #C9A65B;
  transform: translateY(-50%);
}
.ornament::before { left: 28%; }
.ornament::after  { left: 72%; }

/* ---------- Card grid (homepage) ---------- */

.grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: box-shadow .2s ease, transform .2s ease;
}
.card:hover {
  box-shadow: 0 6px 18px rgba(31, 58, 86, 0.08);
  transform: translateY(-2px);
}

.card img, .thumb {
  width: 100%;
  height: 240px;
  object-fit: cover;
  display: block;
  border-bottom: 1px solid var(--border);
}

.card-photo {
  display: block;
  line-height: 0;
  overflow: hidden;
  cursor: pointer;
}
.card-photo:hover { text-decoration: none; }
.card-photo img { transition: transform .25s ease, filter .25s ease; }
.card-photo:hover img {
  transform: scale(1.03);
  filter: brightness(1.04);
}

.card-body {
  padding: 1.1rem 1.2rem 1.3rem;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.card-body h2 {
  font-size: 1.4rem;
  margin: 0 0 .15rem;
}

.card-body .excerpt {
  color: var(--text);
  font-size: .95rem;
  margin: .25rem 0 1rem;
  flex: 1;
}

.card-link {
  font-weight: 500;
  font-size: .95rem;
  align-self: flex-start;
}
.card-link span { margin-left: .2rem; transition: margin-left .15s ease; }
.card-link:hover { text-decoration: none; }
.card-link:hover span { margin-left: .45rem; }

/* ---------- Person page ---------- */

.back-link {
  margin-bottom: 1.5rem;
  font-size: .95rem;
}

.person-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2rem;
  align-items: stretch;
  margin-bottom: 1rem;
}

.person-hero-left {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.person-hero-left .person-header {
  margin-bottom: .25rem;
  padding-bottom: 0;
  border-bottom: none;
}

.person-hero-left section {
  flex: 1;
  margin-top: 1rem;
}

.person-hero-right {
  display: flex;
  align-items: flex-start;
}

.person-header h1 {
  font-size: clamp(2rem, 3.6vw, 2.8rem);
  margin: 0 0 .3rem;
}

.person-header .dates {
  margin: 0 0 .5rem;
}

.person-hero-right .portrait {
  width: 320px;
  max-width: 100%;
  display: block;
}

@media (max-width: 820px) {
  .person-hero {
    grid-template-columns: 1fr;
  }
  .person-hero-right .portrait {
    width: min(320px, 100%);
  }
}

.portrait {
  width: min(320px, 100%);
  border-radius: 8px;
  border: 1px solid var(--border);
}

/* ---------- Section blocks (person page) ---------- */

section {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.4rem 1.6rem;
  margin-top: 1.2rem;
}

section h2 {
  font-size: 1.35rem;
  margin: 0 0 .8rem;
  padding-bottom: .5rem;
  border-bottom: 1px solid var(--border);
}

section ul {
  margin: 0;
  padding-left: 1.2rem;
}

section li { margin-bottom: .35rem; }

section p:last-child { margin-bottom: 0; }

/* ---------- Photo gallery ---------- */

.gallery {
  display: flex;
  flex-wrap: nowrap;
  gap: .9rem;
  overflow-x: auto;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
  padding-bottom: .5rem;
  scrollbar-color: var(--border) transparent;
  scrollbar-width: thin;
}

.gallery::-webkit-scrollbar { height: 8px; }
.gallery::-webkit-scrollbar-track { background: transparent; }
.gallery::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}
.gallery::-webkit-scrollbar-thumb:hover { background: #cdc4b3; }

.gallery > * { flex: 0 0 auto; }

.gallery img {
  width: 300px;
  height: 200px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--border);
  display: block;
}

.lightbox-trigger {
  display: inline-block;
  cursor: pointer;
  line-height: 0;
  border-radius: 8px;
  overflow: hidden;
  transition: transform .15s ease, box-shadow .15s ease;
  position: relative;
}
.lightbox-trigger img { cursor: pointer; }
.lightbox-trigger:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(31, 58, 86, 0.18);
}
.lightbox-trigger:hover img { filter: brightness(1.04); }
.lightbox-trigger:hover { text-decoration: none; }

/* ---------- Lightbox overlay ---------- */

.lightbox {
  position: fixed;
  inset: 0;
  background: rgba(20, 26, 36, 0.88);
  display: none;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  z-index: 1000;
  cursor: zoom-out;
}
.lightbox.is-open { display: flex; }

.lightbox img {
  max-width: 100%;
  max-height: 100%;
  border-radius: 6px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.5);
}

.lightbox-close {
  position: absolute;
  top: 1rem;
  right: 1.25rem;
  background: none;
  border: none;
  color: #FFFCF8;
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: .25rem .5rem;
  border-radius: 4px;
  font-family: var(--sans);
}
.lightbox-close:hover { background: rgba(255,255,255,0.1); }

.placeholder {
  background: #EFEAE2;
  color: var(--muted);
  display: grid;
  place-items: center;
  font-size: .9rem;
}

.thumb.placeholder { height: 240px; }
.portrait.placeholder {
  height: 280px;
  width: min(320px, 100%);
}

/* ---------- Responsive tweaks ---------- */

@media (max-width: 600px) {
  .container { margin: 2rem auto 3rem; }
  .person-header { gap: 1.2rem; }
  section { padding: 1.1rem 1.2rem; }
}
"""

local_image_files = []
for image_dir in [SITE_IMAGES_DIR, IMAGES_DIR]:
    if image_dir.exists():
        local_image_files.extend([p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS])
local_image_files = sorted(local_image_files, key=lambda p: p.name.lower())

lightbox_js = """(function () {
  function buildOverlay() {
    var overlay = document.createElement("div");
    overlay.className = "lightbox";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.innerHTML = '<button class="lightbox-close" aria-label="Close">&times;</button><img alt="" />';
    document.body.appendChild(overlay);
    return overlay;
  }

  function close(overlay) {
    overlay.classList.remove("is-open");
    var img = overlay.querySelector("img");
    if (img) img.src = "";
    document.body.style.overflow = "";
  }

  function open(overlay, src, alt) {
    var img = overlay.querySelector("img");
    img.src = src;
    img.alt = alt || "";
    overlay.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var overlay = buildOverlay();
    var triggers = document.querySelectorAll(".lightbox-trigger");

    triggers.forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        var img = el.querySelector("img");
        var src = el.getAttribute("href") || (img && img.src);
        var alt = img && img.alt;
        if (src) open(overlay, src, alt);
      });
    });

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay || e.target.classList.contains("lightbox-close")) {
        close(overlay);
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && overlay.classList.contains("is-open")) {
        close(overlay);
      }
    });
  });
})();
"""

CLASSMATES_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "styles.css").write_text(css, encoding="utf-8")
(OUT_DIR / "lightbox.js").write_text(lightbox_js, encoding="utf-8")
(OUT_DIR / "index.html").write_text(index_page(), encoding="utf-8")

for person in classmates:
    (CLASSMATES_DIR / f"{person['id']}.html").write_text(person_page(person), encoding="utf-8")

print(f"Generated {len(classmates)} classmate pages in {OUT_DIR}")
