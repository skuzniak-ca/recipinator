import os
import time
import threading
import uuid
from urllib.parse import urlparse
from flask import Flask, request, jsonify, render_template
from database import init_db, add_recipe, get_all_recipes, get_recipe, \
    update_rating, update_image, filter_recipes, delete_recipe, get_all_ingredient_names
from scraper import scrape_recipe, download_image, _validate_image_content

app = Flask(__name__)


@app.before_request
def csrf_check():
    """Block cross-origin mutating requests (CSRF protection)."""
    if request.method in ('POST', 'PUT', 'DELETE'):
        origin = request.headers.get('Origin')
        referer = request.headers.get('Referer')
        if origin:
            allowed = request.host_url.rstrip('/')
            if origin != allowed:
                return jsonify({'error': 'Cross-origin request blocked.'}), 403
        elif referer:
            ref_origin = f"{urlparse(referer).scheme}://{urlparse(referer).netloc}"
            allowed = request.host_url.rstrip('/')
            if ref_origin != allowed:
                return jsonify({'error': 'Cross-origin request blocked.'}), 403


@app.after_request
def security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'"
    )
    return response


# Rate limiter for scraping endpoint: max 2 requests per 10 seconds per IP
_scrape_timestamps = {}  # {ip: [timestamp, ...]}
_scrape_lock = threading.Lock()
SCRAPE_RATE_LIMIT = 2
SCRAPE_RATE_WINDOW = 10  # seconds


def _check_scrape_rate_limit():
    """Return True if the request should be rate-limited."""
    ip = request.remote_addr
    now = time.monotonic()
    with _scrape_lock:
        timestamps = _scrape_timestamps.get(ip, [])
        # Remove timestamps outside the window
        timestamps = [t for t in timestamps if now - t < SCRAPE_RATE_WINDOW]
        if len(timestamps) >= SCRAPE_RATE_LIMIT:
            _scrape_timestamps[ip] = timestamps
            return True
        timestamps.append(now)
        _scrape_timestamps[ip] = timestamps
        return False


UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Page Routes ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/add')
def add_page():
    return render_template('add.html')


@app.route('/bookmarklet')
def bookmarklet_page():
    return render_template('bookmarklet.html')


# --- API Routes ---

@app.route('/api/recipes', methods=['GET'])
def api_get_recipes():
    ingredients_param = request.args.get('ingredients', '').strip()
    if ingredients_param:
        ingredient_names = [name.strip().lower() for name in ingredients_param.split(';') if name.strip()]
        recipes = filter_recipes(ingredient_names)
    else:
        recipes = get_all_recipes()
    return jsonify(recipes)


@app.route('/api/recipes/<int:recipe_id>', methods=['GET'])
def api_get_recipe(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        return jsonify({'error': 'Recipe not found'}), 404
    return jsonify(recipe)


@app.route('/api/recipes', methods=['POST'])
def api_add_recipe():
    if _check_scrape_rate_limit():
        return jsonify({'error': 'Too many requests. Please wait a moment before adding another recipe.'}), 429

    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400

    url = data['url'].strip()
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        result = scrape_recipe(url)
    except ValueError as e:
        return jsonify({'error': str(e)}), 422

    recipe_id = add_recipe(
        title=result['title'],
        url=url,
        instructions=result['instructions'],
        ingredients=result['ingredients']
    )

    # Download scraped image if available
    if result.get('image_url'):
        image_filename = download_image(result['image_url'], UPLOAD_FOLDER)
        if image_filename:
            update_image(recipe_id, image_filename)

    recipe = get_recipe(recipe_id)
    return jsonify(recipe), 201


@app.route('/api/recipes/<int:recipe_id>/rating', methods=['PUT'])
def api_update_rating(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        return jsonify({'error': 'Recipe not found'}), 404

    data = request.get_json()
    if not data or 'rating' not in data:
        return jsonify({'error': 'Rating is required'}), 400

    rating = data['rating']
    if not isinstance(rating, int) or not (0 <= rating <= 5):
        return jsonify({'error': 'Rating must be an integer between 0 and 5'}), 400

    update_rating(recipe_id, rating)
    return jsonify({'id': recipe_id, 'rating': rating})


@app.route('/api/recipes/<int:recipe_id>/image', methods=['POST'])
def api_upload_image(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        return jsonify({'error': 'Recipe not found'}), 404

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Accepted: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_IMAGE_SIZE:
        return jsonify({'error': 'Image too large. Maximum size is 5MB.'}), 400

    # Validate actual file content via magic bytes
    file_header = file.read(12)
    file.seek(0)
    validated_ext = _validate_image_content(file_header)
    if not validated_ext:
        return jsonify({'error': 'File does not appear to be a valid image.'}), 400

    # Delete old image if exists
    if recipe['image_filename']:
        old_path = os.path.join(UPLOAD_FOLDER, recipe['image_filename'])
        if os.path.exists(old_path):
            os.remove(old_path)

    # Save with unique filename using validated extension
    filename = f"{uuid.uuid4().hex}.{validated_ext}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    update_image(recipe_id, filename)
    return jsonify({'id': recipe_id, 'image_filename': filename})


@app.route('/api/recipes/<int:recipe_id>/image', methods=['DELETE'])
def api_delete_image(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        return jsonify({'error': 'Recipe not found'}), 404

    if recipe['image_filename']:
        image_path = os.path.join(UPLOAD_FOLDER, recipe['image_filename'])
        if os.path.exists(image_path):
            os.remove(image_path)
        update_image(recipe_id, None)

    return jsonify({'id': recipe_id, 'image_filename': None})


@app.route('/api/recipes/<int:recipe_id>', methods=['DELETE'])
def api_delete_recipe(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        return jsonify({'error': 'Recipe not found'}), 404

    # Delete associated image file
    if recipe['image_filename']:
        image_path = os.path.join(UPLOAD_FOLDER, recipe['image_filename'])
        if os.path.exists(image_path):
            os.remove(image_path)

    delete_recipe(recipe_id)
    return jsonify({'message': 'Recipe deleted'})


@app.route('/api/ingredients', methods=['GET'])
def api_get_ingredients():
    return jsonify(get_all_ingredient_names())


init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
