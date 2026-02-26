import os
import uuid
from flask import Flask, request, jsonify, render_template, send_from_directory
from database import init_db, add_recipe, get_all_recipes, get_recipe, \
    update_rating, update_image, filter_recipes, delete_recipe, get_all_ingredient_names
from scraper import scrape_recipe

app = Flask(__name__)

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

    # Delete old image if exists
    if recipe['image_filename']:
        old_path = os.path.join(UPLOAD_FOLDER, recipe['image_filename'])
        if os.path.exists(old_path):
            os.remove(old_path)

    # Save with unique filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    update_image(recipe_id, filename)
    return jsonify({'id': recipe_id, 'image_filename': filename})


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


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
