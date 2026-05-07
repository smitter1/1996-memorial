# Class of 1996 Memorial Site

Static memorial website generated from a single JSON data source.

## Project Structure

- `1996_Classmates_AGGREGATE_Memorial.json` - source data
- `generate_site.py` - site generator script
- `docs/` - generated website (GitHub Pages publish folder)
  - `index.html` - homepage
  - `classmates/*.html` - one page per classmate
  - `images/` - local primary photos
  - `styles.css` - shared styles

## Update the Site

1. Edit/replace `1996_Classmates_AGGREGATE_Memorial.json` as needed.
2. Add/update local photos in `docs/images/`.
3. Regenerate:

```bash
python3 generate_site.py
```

4. Commit and push changes to GitHub.

## Publish on GitHub Pages

In your GitHub repo:

1. Open **Settings -> Pages**
2. Under **Build and deployment**, choose:
   - **Source:** Deploy from a branch
   - **Branch:** `main`
   - **Folder:** `/docs`
3. Save

Your site will publish at:
- `https://<your-username>.github.io/<repo-name>/`
