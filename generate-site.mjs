import fs from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const dataPath = path.join(root, "1996_Classmates_AGGREGATE_Memorial.json");
const outDir = path.join(root, "site");
const classmatesDir = path.join(outDir, "classmates");

const raw = await fs.readFile(dataPath, "utf8");
const data = JSON.parse(raw);
const classmates = data.classmates ?? [];

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDate(dateObj) {
  if (!dateObj || !dateObj.year) return "Unknown";
  if (!dateObj.month) return String(dateObj.year);
  const months = [
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
  ];
  const month = months[dateObj.month - 1] ?? "";
  if (dateObj.day) return `${month} ${dateObj.day}, ${dateObj.year}`;
  return `${month} ${dateObj.year}`;
}

function lifeSpan(person) {
  const born = formatDate(person.dates?.born);
  const died = formatDate(person.dates?.died);
  return `${born} - ${died}`;
}

function leadPhoto(person) {
  const photos = person.photos ?? [];
  for (const p of photos) {
    const remote = p.url || p.source_url;
    if (remote) return remote;
  }
  return null;
}

function list(items, renderItem) {
  if (!Array.isArray(items) || items.length === 0) return "<p>Not available.</p>";
  const rows = items.map((item) => `<li>${renderItem(item)}</li>`).join("");
  return `<ul>${rows}</ul>`;
}

function section(title, content) {
  return `<section><h2>${escapeHtml(title)}</h2>${content}</section>`;
}

function personPage(person) {
  const photo = leadPhoto(person);
  const education = list(person.education, (e) => {
    const parts = [e.institution, e.degree, e.field, e.year].filter(Boolean);
    return escapeHtml(parts.join(" | "));
  });
  const career = list(person.career, (c) => {
    const parts = [c.role, c.employer, c.location, c.period || c.duration].filter(Boolean);
    return escapeHtml(parts.join(" | "));
  });
  const familyObject = person.family && typeof person.family === "object" ? person.family : {};
  const familyEntries = Object.entries(familyObject);
  const family = familyEntries.length
    ? `<ul>${familyEntries
        .map(([key, value]) => {
          const label = key.replaceAll("_", " ");
          const prettyValue = Array.isArray(value) ? value.join(", ") : String(value);
          return `<li><strong>${escapeHtml(label)}:</strong> ${escapeHtml(prettyValue)}</li>`;
        })
        .join("")}</ul>`
    : "<p>Not available.</p>";
  const interests = Array.isArray(person.interests) && person.interests.length
    ? `<p>${escapeHtml(person.interests.join(" | "))}</p>`
    : "<p>Not available.</p>";
  const obituaryText = person.obituary?.text || person.obituary?.excerpt || person.obituary?.summary || "Not available.";
  const sources = list(person.sources, (s) => {
    if (!s?.url) return escapeHtml(s?.label ?? "Source");
    return `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(
      s.label || s.url
    )}</a>`;
  });

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(person.common_name || person.full_name)} | Class of 1996 Memorial</title>
  <link rel="stylesheet" href="../styles.css" />
</head>
<body>
  <main class="container">
    <nav><a href="../index.html">← Back to classmates</a></nav>
    <header class="person-header">
      <div>
        <h1>${escapeHtml(person.full_name)}</h1>
        <p class="muted">${escapeHtml(lifeSpan(person))}</p>
      </div>
      ${
        photo
          ? `<img class="portrait" src="${escapeHtml(photo)}" alt="Photo of ${escapeHtml(
              person.common_name || person.full_name
            )}" loading="lazy" />`
          : `<div class="portrait placeholder">No photo available</div>`
      }
    </header>
    ${section("Biography", `<p>${escapeHtml(person.biography || "Not available.")}</p>`)}
    ${section("Memorial Legacy", `<p>${escapeHtml(person.memorial_legacy || "Not available.")}</p>`)}
    ${section("Education", education)}
    ${section("Career", career)}
    ${section("Family", family)}
    ${section("Interests", interests)}
    ${section("Obituary", `<p>${escapeHtml(obituaryText)}</p>`)}
    ${section("Sources", sources)}
  </main>
</body>
</html>`;
}

function indexPage() {
  const cards = classmates
    .map((person) => {
      const photo = leadPhoto(person);
      const bio = person.biography || "";
      const excerpt = bio.length > 220 ? `${bio.slice(0, 217)}...` : bio;
      return `<article class="card">
        ${
          photo
            ? `<img src="${escapeHtml(photo)}" alt="Photo of ${escapeHtml(
                person.common_name || person.full_name
              )}" loading="lazy" />`
            : `<div class="thumb placeholder">No photo available</div>`
        }
        <div class="card-body">
          <h2>${escapeHtml(person.full_name)}</h2>
          <p class="muted">${escapeHtml(lifeSpan(person))}</p>
          <p>${escapeHtml(excerpt)}</p>
          <a class="button" href="./classmates/${escapeHtml(person.id)}.html">Read full memorial</a>
        </div>
      </article>`;
    })
    .join("");

  return `<!doctype html>
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
      <h1>${escapeHtml(data.document?.title || "Classmates We Remember")}</h1>
      <p class="subtitle">${escapeHtml(data.document?.subtitle || "")}</p>
      <p>This memorial site honors seven classmates from the UCLA Anderson MBA Class of 1996.</p>
    </header>
    <section class="grid">
      ${cards}
    </section>
  </main>
</body>
</html>`;
}

const css = `:root {
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
`;

await fs.mkdir(classmatesDir, { recursive: true });
await fs.writeFile(path.join(outDir, "styles.css"), css, "utf8");
await fs.writeFile(path.join(outDir, "index.html"), indexPage(), "utf8");

for (const person of classmates) {
  await fs.writeFile(path.join(classmatesDir, `${person.id}.html`), personPage(person), "utf8");
}

console.log(`Generated ${classmates.length} classmate pages in ${outDir}`);
