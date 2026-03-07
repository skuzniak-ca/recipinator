// --- State ---
let allRecipes = [];
let currentRecipeId = null;
let knownIngredients = [];

// --- DOM refs ---
const grid = document.getElementById('recipe-grid');
const emptyState = document.getElementById('empty-state');
const filterInput = document.getElementById('filter-input');
const btnFilter = document.getElementById('btn-filter');
const btnClearFilter = document.getElementById('btn-clear-filter');
const btnAddRecipe = document.getElementById('btn-add-recipe');

const modalAdd = document.getElementById('modal-add');
const recipeUrlInput = document.getElementById('recipe-url');
const addError = document.getElementById('add-error');
const addLoading = document.getElementById('add-loading');
const btnSubmitRecipe = document.getElementById('btn-submit-recipe');

const modalDetail = document.getElementById('modal-detail');
const detailTitle = document.getElementById('detail-title');
const detailImage = document.getElementById('detail-image');
const detailLink = document.getElementById('detail-link');
const detailStars = document.getElementById('detail-stars');
const detailIngredientsList = document.getElementById('detail-ingredients-list');
const detailTags = document.getElementById('detail-tags');
const detailInstructionsText = document.getElementById('detail-instructions-text');
const imageUploadInput = document.getElementById('image-upload-input');
const btnRemoveImage = document.getElementById('btn-remove-image');
const btnDeleteRecipe = document.getElementById('btn-delete-recipe');

// --- Formatting helpers ---
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatInstructions(text) {
    const escaped = escapeHtml(text);
    // Try splitting on newlines first
    let lines = escaped.split('\n').filter(l => l.trim());
    // If it's a single block, try splitting on numbered step patterns ("1. ..., 2. ...")
    if (lines.length <= 1) {
        const steps = escaped.split(/(?<=\s)(?=\d+\.\s)/).filter(s => s.trim());
        if (steps.length > 1) lines = steps;
    }
    // Render as ordered list if lines look numbered
    const isNumbered = lines.length > 1 && lines.every(l => /^\d+\.\s/.test(l.trim()));
    if (isNumbered) {
        const items = lines.map(l => `<li>${l.replace(/^\d+\.\s*/, '').trim()}</li>`).join('');
        return `<ol>${items}</ol>`;
    }
    // Fall back to paragraph breaks
    return lines.map(l => `<p>${l}</p>`).join('');
}

// --- API helpers ---
async function api(url, options = {}) {
    const res = await fetch(url, options);
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.error || 'Request failed');
    }
    return data;
}

// --- Recipes ---
async function loadRecipes(ingredientFilter = '') {
    let url = '/api/recipes';
    if (ingredientFilter) {
        url += '?ingredients=' + encodeURIComponent(ingredientFilter);
    }
    allRecipes = await api(url);
    renderGrid();
}

function getImageUrl(recipe) {
    if (recipe.image_filename) {
        return '/static/uploads/' + recipe.image_filename;
    }
    return '/static/placeholder.svg';
}

function renderStarsHTML(rating, size = 'small') {
    let html = '';
    for (let i = 1; i <= 5; i++) {
        if (i <= rating) {
            html += '<span class="star-filled">&#9733;</span>';
        } else {
            html += '<span class="star-empty">&#9733;</span>';
        }
    }
    return html;
}

function renderGrid() {
    grid.innerHTML = '';

    if (allRecipes.length === 0) {
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';

    allRecipes.forEach(recipe => {
        const tile = document.createElement('div');
        tile.className = 'recipe-tile';
        tile.dataset.id = recipe.id;
        tile.innerHTML = `
            <img class="tile-image" src="${getImageUrl(recipe)}" alt="${escapeHtml(recipe.title)}" loading="lazy">
            <div class="tile-overlay">
                <div class="tile-title">${escapeHtml(recipe.title)}</div>
                ${recipe.rating > 0 ? `<div class="tile-stars">${renderStarsHTML(recipe.rating)}</div>` : ''}
            </div>
        `;
        tile.addEventListener('click', () => openDetail(recipe.id));
        grid.appendChild(tile);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// --- Add Recipe ---
function openAddModal() {
    recipeUrlInput.value = '';
    addError.style.display = 'none';
    addLoading.style.display = 'none';
    btnSubmitRecipe.disabled = false;
    modalAdd.style.display = 'flex';
    recipeUrlInput.focus();
}

function closeAddModal() {
    modalAdd.style.display = 'none';
}

async function submitRecipe() {
    const url = recipeUrlInput.value.trim();
    if (!url) {
        addError.textContent = 'Please enter a URL.';
        addError.style.display = 'block';
        return;
    }

    addError.style.display = 'none';
    addLoading.style.display = 'flex';
    btnSubmitRecipe.disabled = true;

    try {
        await api('/api/recipes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        closeAddModal();
        await loadRecipes();
        await loadIngredients();
    } catch (err) {
        addError.textContent = err.message;
        addError.style.display = 'block';
    } finally {
        addLoading.style.display = 'none';
        btnSubmitRecipe.disabled = false;
    }
}

// --- Detail Modal ---
function openDetail(recipeId) {
    const recipe = allRecipes.find(r => r.id === recipeId);
    if (!recipe) return;

    currentRecipeId = recipeId;

    detailTitle.textContent = recipe.title;
    detailImage.src = getImageUrl(recipe);
    detailLink.href = recipe.url;
    btnRemoveImage.style.display = recipe.image_filename ? 'inline-block' : 'none';

    // Stars
    updateStarsDisplay(recipe.rating);

    // Ingredients
    detailIngredientsList.innerHTML = '';
    detailTags.innerHTML = '';
    recipe.ingredients.forEach(ing => {
        const li = document.createElement('li');
        li.textContent = ing.raw_text;
        detailIngredientsList.appendChild(li);

        const tag = document.createElement('span');
        tag.className = 'ingredient-tag';
        tag.textContent = ing.name;
        detailTags.appendChild(tag);
    });

    // Instructions
    detailInstructionsText.innerHTML = formatInstructions(recipe.instructions || 'No instructions available.');

    modalDetail.style.display = 'flex';
}

function closeDetailModal() {
    modalDetail.style.display = 'none';
    currentRecipeId = null;
}

function updateStarsDisplay(rating) {
    detailStars.querySelectorAll('.star').forEach(star => {
        const val = parseInt(star.dataset.value);
        star.classList.toggle('active', val <= rating);
    });
}

async function setRating(rating) {
    if (!currentRecipeId) return;
    try {
        await api(`/api/recipes/${currentRecipeId}/rating`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rating }),
        });
        updateStarsDisplay(rating);
        // Update local state
        const recipe = allRecipes.find(r => r.id === currentRecipeId);
        if (recipe) recipe.rating = rating;
        renderGrid();
    } catch (err) {
        alert('Failed to update rating: ' + err.message);
    }
}

// --- Image Upload ---
async function uploadImage(file) {
    if (!currentRecipeId) return;

    const formData = new FormData();
    formData.append('image', file);

    try {
        const result = await api(`/api/recipes/${currentRecipeId}/image`, {
            method: 'POST',
            body: formData,
        });
        // Update display
        detailImage.src = '/static/uploads/' + result.image_filename;
        btnRemoveImage.style.display = 'inline-block';
        // Update local state
        const recipe = allRecipes.find(r => r.id === currentRecipeId);
        if (recipe) recipe.image_filename = result.image_filename;
        renderGrid();
    } catch (err) {
        alert('Failed to upload image: ' + err.message);
    }
}

// --- Remove Image ---
async function removeImage() {
    if (!currentRecipeId) return;
    if (!confirm('Remove the image for this recipe?')) return;

    try {
        await api(`/api/recipes/${currentRecipeId}/image`, {
            method: 'DELETE',
        });
        detailImage.src = '/static/placeholder.svg';
        btnRemoveImage.style.display = 'none';
        const recipe = allRecipes.find(r => r.id === currentRecipeId);
        if (recipe) recipe.image_filename = null;
        renderGrid();
    } catch (err) {
        alert('Failed to remove image: ' + err.message);
    }
}

// --- Delete ---
async function deleteRecipe() {
    if (!currentRecipeId) return;
    if (!confirm('Are you sure you want to delete this recipe?')) return;

    try {
        await api(`/api/recipes/${currentRecipeId}`, { method: 'DELETE' });
        closeDetailModal();
        await loadRecipes();
        await loadIngredients();
    } catch (err) {
        alert('Failed to delete recipe: ' + err.message);
    }
}

// --- Filter ---
function applyFilter() {
    const value = filterInput.value.trim();
    if (value) {
        btnClearFilter.style.display = 'inline-block';
        loadRecipes(value);
    }
}

function clearFilter() {
    filterInput.value = '';
    btnClearFilter.style.display = 'none';
    loadRecipes();
}

// --- Ingredients Autocomplete ---
async function loadIngredients() {
    knownIngredients = await api('/api/ingredients');
}

// --- Event Listeners ---
btnAddRecipe.addEventListener('click', openAddModal);
btnSubmitRecipe.addEventListener('click', submitRecipe);
btnFilter.addEventListener('click', applyFilter);
btnClearFilter.addEventListener('click', clearFilter);
btnRemoveImage.addEventListener('click', removeImage);
btnDeleteRecipe.addEventListener('click', deleteRecipe);

// Enter key in URL input
recipeUrlInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') submitRecipe();
});

// Enter key in filter input
filterInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') applyFilter();
});

// Stars click
detailStars.querySelectorAll('.star').forEach(star => {
    star.addEventListener('click', () => {
        setRating(parseInt(star.dataset.value));
    });
});

// Image upload
document.getElementById('btn-upload-image').addEventListener('click', () => {
    imageUploadInput.click();
});
imageUploadInput.addEventListener('change', e => {
    if (e.target.files.length > 0) {
        uploadImage(e.target.files[0]);
        e.target.value = '';
    }
});

// Modal close buttons
document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => {
        modalAdd.style.display = 'none';
        modalDetail.style.display = 'none';
        currentRecipeId = null;
    });
});

// Close modal on backdrop click
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', e => {
        if (e.target === modal) {
            modal.style.display = 'none';
            currentRecipeId = null;
        }
    });
});

// Close modal on Escape
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        modalAdd.style.display = 'none';
        modalDetail.style.display = 'none';
        currentRecipeId = null;
    }
});

// --- Init ---
loadRecipes();
loadIngredients();
