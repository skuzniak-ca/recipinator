# Recipinator

Recipinator is a locally hosted recipe database that runs on your local network. You can paste a recipe URL (like from a food blog, or a recipe website), and Recipinator will scrape the ingredients and instructions automatically. You can browse and filter your stored recipes tile-based UI. This was originally created because my wife loves food blogs, but has trouble keeping track of recipes, and when she would bookmark them, they would often disappear from the internet at some point.

## Features

- **URL scraping** — paste a link and the app extracts title, ingredients, instructions, and hero image (JSON-LD first, HTML fallback)
- **Ingredient filtering** — search by one or more ingredients (AND logic, semicolon-separated; eg, a search for chicken;cheese will return recipes that have ingredients of chicken AND cheese)
- **Star ratings** — rate recipes 0–5 stars
- **Image support** — auto-scraped hero images, or upload your own (png/jpg/gif/webp, 5 MB max)
- **Bookmarklet** — save recipes from your browser with one tap (setup for your browser at `/bookmarklet`)
- **Responsive layout** — 4-column grid on desktop down to single-column on mobile
- **No account required** — designed for trusted home networks - there is no authentication by design!

## Tech Stack

Flask · SQLite · Gunicorn · Docker · vanilla HTML/CSS/JS (no frontend framework)

## Quick Start

### Docker (recommended)

```bash
git clone <repo-url> && cd recipinator
docker compose up -d
```

Data (database and uploaded images) is persisted in Docker named volumes.

To change the host port, set `HOST_PORT` before starting:

```bash
HOST_PORT=8080 docker compose up -d
```

### Manual

```bash
git clone <repo-url> && cd recipinator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open `http://localhost:5000` (or `http://<your-lan-ip>:5000` from other devices on the same network). Replace with your selected port if you specified a different value.

## Project Structure

```
app.py              Flask routes, security middleware, image upload handling
database.py         SQLite schema, CRUD helpers, ingredient filtering
scraper.py          Recipe scraping, ingredient normalization, URL validation
Dockerfile          Container image (Python 3.12-slim, gunicorn)
docker-compose.yml  Service config with named volumes for DB and uploads
.dockerignore       Files excluded from Docker build context
templates/
  index.html        Single-page app template
  add.html          Standalone add-recipe page (bookmarklet target)
  bookmarklet.html  Setup instructions for bookmarklet
static/
  css/style.css     Responsive layout and styling
  js/app.js         SPA logic (API calls, DOM rendering)
  uploads/          User-uploaded images (gitignored)
```

## API

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/add` | Standalone add page (accepts `?url=` for bookmarklet) |
| GET | `/bookmarklet` | Bookmarklet setup instructions |
| GET | `/api/recipes` | List all or filter (`?ingredients=chicken;garlic`) |
| GET | `/api/recipes/<id>` | Single recipe detail |
| POST | `/api/recipes` | Add recipe (`{"url": "..."}`) |
| PUT | `/api/recipes/<id>/rating` | Set rating (`{"rating": 4}`) |
| POST | `/api/recipes/<id>/image` | Upload image (multipart) |
| DELETE | `/api/recipes/<id>/image` | Remove image |
| DELETE | `/api/recipes/<id>` | Delete recipe |
| GET | `/api/ingredients` | Unique ingredient names (for autocomplete) |
