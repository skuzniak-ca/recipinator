import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recipinator.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            instructions TEXT,
            rating INTEGER DEFAULT 0 CHECK(rating >= 0 AND rating <= 5),
            image_filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            raw_text TEXT,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_ingredients_name ON ingredients(name);
        CREATE INDEX IF NOT EXISTS idx_ingredients_recipe_id ON ingredients(recipe_id);
    ''')
    conn.commit()
    conn.close()


def add_recipe(title, url, instructions, ingredients):
    """Add a recipe with its ingredients.

    Args:
        title: Recipe title
        url: Original recipe URL
        instructions: Cooking instructions text
        ingredients: List of dicts with 'name' (normalized) and 'raw_text' (original)

    Returns:
        The id of the newly created recipe
    """
    conn = get_db()
    cursor = conn.execute(
        'INSERT INTO recipes (title, url, instructions) VALUES (?, ?, ?)',
        (title, url, instructions)
    )
    recipe_id = cursor.lastrowid

    for ing in ingredients:
        conn.execute(
            'INSERT INTO ingredients (recipe_id, name, raw_text) VALUES (?, ?, ?)',
            (recipe_id, ing['name'], ing['raw_text'])
        )

    conn.commit()
    conn.close()
    return recipe_id


def get_all_recipes():
    """Return all recipes with their ingredients."""
    conn = get_db()
    recipes = conn.execute('SELECT * FROM recipes ORDER BY created_at DESC').fetchall()
    result = []
    for recipe in recipes:
        ingredients = conn.execute(
            'SELECT name, raw_text FROM ingredients WHERE recipe_id = ?',
            (recipe['id'],)
        ).fetchall()
        r = dict(recipe)
        r['ingredients'] = [dict(i) for i in ingredients]
        result.append(r)
    conn.close()
    return result


def get_recipe(recipe_id):
    """Return a single recipe with full details."""
    conn = get_db()
    recipe = conn.execute('SELECT * FROM recipes WHERE id = ?', (recipe_id,)).fetchone()
    if recipe is None:
        conn.close()
        return None
    ingredients = conn.execute(
        'SELECT name, raw_text FROM ingredients WHERE recipe_id = ?',
        (recipe_id,)
    ).fetchall()
    r = dict(recipe)
    r['ingredients'] = [dict(i) for i in ingredients]
    conn.close()
    return r


def update_rating(recipe_id, rating):
    """Set star rating (1-5) for a recipe."""
    if not (0 <= rating <= 5):
        raise ValueError("Rating must be between 0 and 5")
    conn = get_db()
    conn.execute('UPDATE recipes SET rating = ? WHERE id = ?', (rating, recipe_id))
    conn.commit()
    conn.close()


def update_image(recipe_id, filename):
    """Set the image filename for a recipe."""
    conn = get_db()
    conn.execute('UPDATE recipes SET image_filename = ? WHERE id = ?', (filename, recipe_id))
    conn.commit()
    conn.close()


def filter_recipes(ingredient_names):
    """Return recipes matching ALL given ingredient names (exact match, AND logic).

    Args:
        ingredient_names: List of normalized ingredient name strings
    """
    if not ingredient_names:
        return get_all_recipes()

    conn = get_db()
    # Find recipe IDs that have ALL specified ingredients
    placeholders = ','.join('?' * len(ingredient_names))
    query = f'''
        SELECT recipe_id FROM ingredients
        WHERE name IN ({placeholders})
        GROUP BY recipe_id
        HAVING COUNT(DISTINCT name) = ?
    '''
    params = ingredient_names + [len(ingredient_names)]
    matching_ids = [row['recipe_id'] for row in conn.execute(query, params).fetchall()]

    if not matching_ids:
        conn.close()
        return []

    id_placeholders = ','.join('?' * len(matching_ids))
    recipes = conn.execute(
        f'SELECT * FROM recipes WHERE id IN ({id_placeholders}) ORDER BY created_at DESC',
        matching_ids
    ).fetchall()

    result = []
    for recipe in recipes:
        ingredients = conn.execute(
            'SELECT name, raw_text FROM ingredients WHERE recipe_id = ?',
            (recipe['id'],)
        ).fetchall()
        r = dict(recipe)
        r['ingredients'] = [dict(i) for i in ingredients]
        result.append(r)

    conn.close()
    return result


def delete_recipe(recipe_id):
    """Delete a recipe and its ingredients."""
    conn = get_db()
    conn.execute('DELETE FROM recipes WHERE id = ?', (recipe_id,))
    conn.commit()
    conn.close()


def get_all_ingredient_names():
    """Return a sorted list of all unique ingredient names."""
    conn = get_db()
    rows = conn.execute(
        'SELECT DISTINCT name FROM ingredients ORDER BY name'
    ).fetchall()
    conn.close()
    return [row['name'] for row in rows]
