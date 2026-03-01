# Recipinator

A self-hosted recipe manager for your local network. Paste a recipe URL, and Recipinator scrapes the ingredients and instructions automatically. Browse your collection in a responsive tile-based UI.

## Features

- **URL scraping** — paste a link and the app extracts title, ingredients, instructions, and hero image (JSON-LD first, HTML fallback)
- **Ingredient filtering** — search by one or more ingredients (AND logic, semicolon-separated)
- **Star ratings** — rate recipes 0–5 stars
- **Image support** — auto-scraped hero images, or upload your own (png/jpg/gif/webp, 5 MB max)
- **Bookmarklet** — save recipes from your browser with one tap (setup at `/bookmarklet`)
- **Responsive layout** — 4-column grid on desktop down to single-column on mobile
- **No account required** — designed for trusted home networks

## Tech Stack

Flask · SQLite · vanilla HTML/CSS/JS (no frontend framework)

## Quick Start

```bash
git clone <repo-url> && cd recipinator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open `http://localhost:5000` (or `http://<your-lan-ip>:5000` from other devices).

## Project Structure

```
app.py            Flask routes and image upload handling
database.py       SQLite schema, CRUD helpers, ingredient filtering
scraper.py        Recipe scraping and ingredient normalization
templates/
  index.html      Single-page app template
  add.html        Standalone add-recipe page (bookmarklet target)
  bookmarklet.html  Setup instructions for bookmarklet
static/
  css/style.css   Responsive layout and styling
  js/app.js       SPA logic (API calls, DOM rendering)
  uploads/        User-uploaded images (gitignored)
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
