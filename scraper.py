import os
import re
import json
import html
import uuid
import requests
from bs4 import BeautifulSoup

# Units and measurements to strip from ingredient text
UNITS = {
    'cup', 'cups', 'tablespoon', 'tablespoons', 'tbsp', 'teaspoon', 'teaspoons',
    'tsp', 'ounce', 'ounces', 'oz', 'pound', 'pounds', 'lb', 'lbs', 'gram',
    'grams', 'g', 'kilogram', 'kilograms', 'kg', 'ml', 'milliliter', 'milliliters',
    'liter', 'liters', 'l', 'quart', 'quarts', 'qt', 'pint', 'pints', 'pt',
    'gallon', 'gallons', 'gal', 'pinch', 'dash', 'handful', 'bunch', 'can',
    'cans', 'package', 'packages', 'pkg', 'bag', 'bags', 'bottle', 'bottles',
    'jar', 'jars', 'stick', 'sticks', 'slice', 'slices', 'piece', 'pieces',
    'clove', 'cloves', 'head', 'heads', 'sprig', 'sprigs', 'stalk', 'stalks',
}

# Preparation/modifier words to strip
PREP_WORDS = {
    'diced', 'chopped', 'minced', 'sliced', 'grated', 'shredded', 'crushed',
    'ground', 'peeled', 'cored', 'seeded', 'deveined', 'trimmed', 'halved',
    'quartered', 'cubed', 'julienned', 'melted', 'softened', 'frozen', 'thawed',
    'drained', 'rinsed', 'cooked', 'uncooked', 'raw', 'dried', 'canned',
    'packed', 'sifted', 'beaten', 'divided', 'optional',
    'finely', 'roughly', 'thinly', 'coarsely', 'freshly',
}

# Filler/size words to strip
FILLER_WORDS = {
    'of', 'fresh', 'large', 'small', 'medium', 'extra', 'about', 'approximately',
    'plus', 'more', 'for', 'serving', 'garnish', 'or', 'whole', 'bone-in',
    'boneless', 'skinless', 'skin-on', 'thick', 'thin', 'warm', 'cold', 'hot',
    'room', 'temperature', 'store-bought', 'homemade',
}


def normalize_ingredient(raw_text):
    """Extract the core ingredient name from a raw ingredient string.

    Examples:
        '2 cups diced sweet potatoes' -> 'sweet potatoes'
        '1/2 lb ground beef' -> 'beef'
        '3 cloves garlic, minced' -> 'garlic'
        '1 (14 oz) can diced tomatoes' -> 'tomatoes'
        'salt and pepper to taste' -> 'salt and pepper'
    """
    text = raw_text.lower().strip()

    # Remove parenthetical content like (14 oz) or (about 2 cups)
    text = re.sub(r'\([^)]*\)', '', text)

    # Remove content after comma (usually prep instructions)
    text = text.split(',')[0]

    # Remove fractions and numbers (including unicode fractions)
    text = re.sub(r'[\d½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞/]+', '', text)

    # Remove common trailing phrases
    text = re.sub(r'\bto taste\b', '', text)
    text = re.sub(r'\bas needed\b', '', text)

    # Remove hyphens used in ranges
    text = re.sub(r'\s*-\s*', ' ', text)

    # Split into words and filter
    words = text.split()
    filtered = []
    for word in words:
        word_clean = word.strip('.,;:!?')
        if not word_clean:
            continue
        if word_clean in UNITS:
            continue
        if word_clean in PREP_WORDS:
            continue
        if word_clean in FILLER_WORDS:
            continue
        filtered.append(word_clean)

    result = ' '.join(filtered).strip()

    # Handle "salt and pepper" as a single ingredient
    if result == 'salt pepper':
        return 'salt and pepper'

    return result if result else raw_text.lower().strip()


def _try_json_ld(soup):
    """Try to extract recipe data from JSON-LD structured data."""
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle @graph wrapper
        if isinstance(data, dict) and '@graph' in data:
            data = data['@graph']

        # Handle list of items
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get('@type') in ('Recipe', ['Recipe']):
                    data = item
                    break
            else:
                continue

        if not isinstance(data, dict):
            continue

        schema_type = data.get('@type', '')
        if isinstance(schema_type, list):
            schema_type = schema_type[0] if schema_type else ''

        if schema_type != 'Recipe':
            continue

        title = data.get('name', '')

        # Extract ingredients
        ingredients_raw = data.get('recipeIngredient', [])
        if not ingredients_raw:
            ingredients_raw = data.get('ingredients', [])

        # Extract instructions
        instructions_data = data.get('recipeInstructions', [])
        instructions = _parse_instructions(instructions_data)

        # Extract image URL
        image_url = _extract_json_ld_image(data)

        if title or ingredients_raw:
            return {
                'title': title,
                'ingredients_raw': ingredients_raw,
                'instructions': instructions,
                'image_url': image_url,
            }

    return None


def _parse_instructions(instructions_data):
    """Parse recipe instructions from various JSON-LD formats."""
    if isinstance(instructions_data, str):
        return instructions_data

    steps = []
    if isinstance(instructions_data, list):
        for item in instructions_data:
            if isinstance(item, str):
                steps.append(item)
            elif isinstance(item, dict):
                if item.get('@type') == 'HowToStep':
                    steps.append(item.get('text', ''))
                elif item.get('@type') == 'HowToSection':
                    section_name = item.get('name', '')
                    if section_name:
                        steps.append(f"\n{section_name}:")
                    for sub_item in item.get('itemListElement', []):
                        if isinstance(sub_item, dict):
                            steps.append(sub_item.get('text', ''))
                        elif isinstance(sub_item, str):
                            steps.append(sub_item)

    return '\n'.join(f"{i+1}. {step}" for i, step in enumerate(steps) if step)


def _extract_json_ld_image(data):
    """Extract image URL from JSON-LD Recipe data."""
    image_data = data.get('image')
    if isinstance(image_data, str):
        return image_data
    if isinstance(image_data, list) and image_data:
        first = image_data[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get('url', '')
    if isinstance(image_data, dict):
        return image_data.get('url', '')
    return None


def _try_html_fallback(soup):
    """Fallback: scrape ingredients and instructions from HTML structure."""
    title = ''
    ingredients_raw = []
    instructions = ''

    # Title extraction
    h1 = soup.find('h1')
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)
    else:
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content', '')

    # Find ingredients section
    ingredient_keywords = ['ingredients', 'ingredient list', 'ingredient']
    ingredients_raw = _find_list_after_heading(soup, ingredient_keywords)

    # Find instructions section
    instruction_keywords = [
        'instructions', 'directions', 'method', 'steps',
        'cooking instructions', 'preparation', 'how to make'
    ]
    instruction_elements = _find_list_after_heading(soup, instruction_keywords)
    if instruction_elements:
        instructions = '\n'.join(
            f"{i+1}. {step}" for i, step in enumerate(instruction_elements) if step
        )
    else:
        # Try finding ordered list or paragraphs after heading
        instructions_text = _find_text_after_heading(soup, instruction_keywords)
        if instructions_text:
            instructions = instructions_text

    # Extract image from og:image meta tag
    image_url = None
    og_image = soup.find('meta', property='og:image')
    if og_image:
        image_url = og_image.get('content', '').strip() or None

    return {
        'title': title,
        'ingredients_raw': ingredients_raw,
        'instructions': instructions,
        'image_url': image_url,
    }


def _find_list_after_heading(soup, keywords):
    """Find list items that follow a heading containing one of the keywords."""
    items = []

    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        heading_text = heading.get_text(strip=True).lower()
        if any(kw in heading_text for kw in keywords):
            # Look for <ul> or <ol> following this heading
            sibling = heading.find_next_sibling()
            while sibling:
                if sibling.name in ('ul', 'ol'):
                    for li in sibling.find_all('li'):
                        text = li.get_text(strip=True)
                        if text:
                            items.append(text)
                    if items:
                        return items
                elif sibling.name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                    break
                sibling = sibling.find_next_sibling()

    # Broader search: look for elements with class/id containing keywords
    for kw in keywords:
        containers = soup.find_all(
            attrs={'class': lambda c: c and kw in ' '.join(c).lower() if isinstance(c, list) else c and kw in c.lower()}
        )
        for container in containers:
            for li in container.find_all('li'):
                text = li.get_text(strip=True)
                if text:
                    items.append(text)
            if items:
                return items

    return items


def _find_text_after_heading(soup, keywords):
    """Find paragraph/text content after a heading containing keywords."""
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        heading_text = heading.get_text(strip=True).lower()
        if any(kw in heading_text for kw in keywords):
            paragraphs = []
            sibling = heading.find_next_sibling()
            while sibling:
                if sibling.name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                    break
                if sibling.name in ('p', 'div', 'ol'):
                    text = sibling.get_text(strip=True)
                    if text:
                        paragraphs.append(text)
                sibling = sibling.find_next_sibling()
            if paragraphs:
                return '\n\n'.join(paragraphs)
    return ''


def scrape_recipe(url):
    """Scrape a recipe from the given URL.

    Returns:
        dict with keys:
            - title: str
            - ingredients: list of dicts with 'name' and 'raw_text'
            - instructions: str
    Raises:
        ValueError: If scraping fails or no recipe data found
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch URL: {e}")

    soup = BeautifulSoup(response.text, 'lxml')

    # Try JSON-LD first (most reliable)
    result = _try_json_ld(soup)

    # Fallback to HTML parsing
    if result is None or (not result['ingredients_raw'] and not result['instructions']):
        fallback = _try_html_fallback(soup)
        if result is None:
            result = fallback
        else:
            # Merge: use JSON-LD title but fill in missing fields from HTML
            if not result['ingredients_raw']:
                result['ingredients_raw'] = fallback['ingredients_raw']
            if not result['instructions']:
                result['instructions'] = fallback['instructions']
            if not result['title']:
                result['title'] = fallback['title']
            if not result.get('image_url'):
                result['image_url'] = fallback.get('image_url')

    if not result['title']:
        result['title'] = 'Untitled Recipe'

    # Clean up raw data
    result['ingredients_raw'] = [_clean_text(r) for r in result['ingredients_raw']]
    result['instructions'] = _clean_text(result['instructions'])
    result['title'] = _clean_text(result['title'])

    # Normalize ingredients
    ingredients = []
    seen_names = set()
    for raw in result['ingredients_raw']:
        name = normalize_ingredient(raw)
        if name and name not in seen_names:
            ingredients.append({'name': name, 'raw_text': raw})
            seen_names.add(name)

    if not ingredients and not result['instructions']:
        raise ValueError("Could not extract recipe data from this URL. "
                         "The page may not contain a recognizable recipe.")

    return {
        'title': result['title'],
        'ingredients': ingredients,
        'instructions': result['instructions'] or 'No instructions found.',
        'image_url': result.get('image_url'),
    }


def download_image(image_url, save_dir):
    """Download an image from a URL and save it locally.

    Returns the saved filename on success, None on failure.
    Failures are silent — image download should never prevent recipe saving.
    """
    if not image_url:
        return None

    # Resolve protocol-relative URLs
    if image_url.startswith('//'):
        image_url = 'https:' + image_url

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(image_url, headers=headers, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
        ext_map = {
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/gif': 'gif',
            'image/webp': 'webp',
        }
        ext = ext_map.get(content_type)
        if not ext:
            # Try to infer from URL path
            url_path = image_url.split('?')[0].lower()
            for check_ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
                if url_path.endswith('.' + check_ext):
                    ext = 'jpg' if check_ext == 'jpeg' else check_ext
                    break
            if not ext:
                ext = 'jpg'

        # Enforce 5MB size limit
        if len(response.content) > 5 * 1024 * 1024:
            return None

        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(save_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(response.content)

        return filename
    except Exception:
        return None


def _clean_text(text):
    """Decode HTML entities and strip price/cost annotations from text."""
    if not text:
        return text
    # Decode HTML entities (e.g. &#039; -> ', &amp; -> &)
    text = html.unescape(text)
    # Strip dollar amounts like ($0.42), ( $1.50 ), ($12.99), etc.
    text = re.sub(r'\s*\(\s*\$\d+(?:\.\d{1,2})?\s*\)', '', text)
    # Also strip standalone prices not in parens: $0.42
    text = re.sub(r'\s*\$\d+(?:\.\d{1,2})?', '', text)
    # Clean up trailing commas and empty parens left after stripping
    text = re.sub(r',\s*\)', ')', text)
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip().rstrip(',')
