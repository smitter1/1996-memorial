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
    for r in remote:
        if r != primary:
            secondary.append(r)

    return primary, secondary[:3]


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
        f'<img src="{escape(image_path_for_page(img, "profile"))}" alt="Additional photo of {escape(person.get("common_name") or person.get("full_name", ""))}" loading="lazy" />'
        for img in secondary
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(person.get("common_name") or person.get("full_name", ""))} | Class of 1996 Memorial</title>
  <link rel="stylesheet" href="../styles.css" />
</head>
<body>
  <main class="container">
    <nav><a href="../index.html">← Back to classmates</a></nav>
    <header class="person-header">
      <div>
        <h1>{escape(person.get("full_name", ""))}</h1>
        <p class="muted">{escape(life_span(person))}</p>
      </div>
      {'<img class="portrait" src="' + escape(main_photo) + '" alt="Photo of ' + escape(person.get("common_name") or person.get("full_name", "")) + '" loading="lazy" />' if main_photo else '<div class="portrait placeholder">No photo available</div>'}
    </header>
    {section("Biography", f"<p>{escape(person.get('biography', 'Not available.'))}</p>")}
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
        cards.append(
            f"""<article class="card">
        {'<img src="' + escape(photo) + '" alt="Photo of ' + escape(person.get("common_name") or person.get("full_name", "")) + '" loading="lazy" />' if photo else '<div class="thumb placeholder">No photo available</div>'}
        <div class="card-body">
          <h2>{escape(person.get("full_name", ""))}</h2>
          <p class="muted">{escape(life_span(person))}</p>
          <p>{escape(excerpt)}</p>
          <a class="button" href="./classmates/{escape(person.get("id", ""))}.html">Read full memorial</a>
        </div>
      </article>"""
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Classmates We Remember | UCLA Anderson MBA 1996</title>
  <link rel="stylesheet" href="./styles.css" />
</head>
<body>
  <main class="container">
    <header>
      <h1>{escape(data.get("document", {}).get("title", "Classmates We Remember"))}</h1>
      <p class="subtitle">{escape(data.get("document", {}).get("subtitle", ""))}</p>
      <p>This memorial site honors seven classmates from the UCLA Anderson MBA Class of 1996.</p>
    </header>
    <section class="grid">
      {''.join(cards)}
    </section>
  </main>
</body>
</html>"""


css = """:root {
  --bg: #f7f5f2;
  --text: #1f2937;
  --muted: #6b7280;
  --card: #ffffff;
  --border: #e5e7eb;
  --accent: #1f4d78;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
}

.container {
  width: min(1100px, 92%);
  margin: 2rem auto 3rem;
}

h1, h2 { line-height: 1.25; }
.subtitle, .muted { color: var(--muted); }

.grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}

.card img, .thumb {
  width: 100%;
  height: 220px;
  object-fit: cover;
  display: block;
}

.card-body { padding: 1rem; }

.button {
  display: inline-block;
  margin-top: .4rem;
  text-decoration: none;
  color: white;
  background: var(--accent);
  padding: .45rem .7rem;
  border-radius: 8px;
}

.person-header {
  display: flex;
  gap: 1.2rem;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
}

.portrait {
  width: min(320px, 100%);
  border-radius: 10px;
  border: 1px solid var(--border);
}

.gallery {
  display: flex;
  flex-wrap: wrap;
  gap: .7rem;
}

.gallery img {
  width: 300px;
  max-width: 100%;
  height: 180px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--border);
}

.placeholder {
  background: #eef2f7;
  color: var(--muted);
  display: grid;
  place-items: center;
}

section {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem;
  margin-top: 1rem;
}

a { color: var(--accent); }
"""

local_image_files = []
for image_dir in [SITE_IMAGES_DIR, IMAGES_DIR]:
    if image_dir.exists():
        local_image_files.extend([p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS])
local_image_files = sorted(local_image_files, key=lambda p: p.name.lower())

CLASSMATES_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "styles.css").write_text(css, encoding="utf-8")
(OUT_DIR / "index.html").write_text(index_page(), encoding="utf-8")

for person in classmates:
    (CLASSMATES_DIR / f"{person['id']}.html").write_text(person_page(person), encoding="utf-8")

print(f"Generated {len(classmates)} classmate pages in {OUT_DIR}")
