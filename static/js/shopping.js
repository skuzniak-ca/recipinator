let allRecipes = [];
const selectedIds = new Set();

const recipeList = document.getElementById('recipe-list');
const emptyState = document.getElementById('empty-state');
const titleFilter = document.getElementById('title-filter');
const btnSelectAll = document.getElementById('btn-select-all');
const btnClearSelection = document.getElementById('btn-clear-selection');
const generateBar = document.getElementById('generate-bar');
const selectionCount = document.getElementById('selection-count');
const btnGenerate = document.getElementById('btn-generate');

const modalList = document.getElementById('modal-list');
const btnCloseModal = document.getElementById('btn-close-modal');
const listLoading = document.getElementById('list-loading');
const listError = document.getElementById('list-error');
const combinedList = document.getElementById('combined-list');
const btnCopy = document.getElementById('btn-copy');
const btnPrint = document.getElementById('btn-print');
const copyFeedback = document.getElementById('copy-feedback');

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadRecipes() {
    const res = await fetch('/api/recipes');
    allRecipes = await res.json();
    allRecipes.sort((a, b) => a.title.localeCompare(b.title));
    renderList();
}

function filteredRecipes() {
    const q = titleFilter.value.trim().toLowerCase();
    if (!q) return allRecipes;
    return allRecipes.filter(r => r.title.toLowerCase().includes(q));
}

function renderList() {
    const recipes = filteredRecipes();
    if (allRecipes.length === 0) {
        recipeList.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }
    emptyState.style.display = 'none';

    if (recipes.length === 0) {
        recipeList.innerHTML = '<li class="recipe-list-empty">No recipes match that search.</li>';
    } else {
        recipeList.innerHTML = recipes.map(r => {
            const checked = selectedIds.has(r.id) ? 'checked' : '';
            return `
                <li class="recipe-list-item">
                    <label>
                        <input type="checkbox" data-id="${r.id}" ${checked}>
                        <span class="recipe-list-title">${escapeHtml(r.title)}</span>
                    </label>
                </li>
            `;
        }).join('');
    }
    updateSelectionBar();
}

function updateSelectionBar() {
    const n = selectedIds.size;
    if (n === 0) {
        generateBar.style.display = 'none';
        return;
    }
    generateBar.style.display = 'flex';
    selectionCount.textContent = `${n} recipe${n === 1 ? '' : 's'} selected`;
}

recipeList.addEventListener('change', (e) => {
    if (e.target.matches('input[type="checkbox"]')) {
        const id = parseInt(e.target.dataset.id, 10);
        if (e.target.checked) selectedIds.add(id);
        else selectedIds.delete(id);
        updateSelectionBar();
    }
});

titleFilter.addEventListener('input', renderList);

btnSelectAll.addEventListener('click', () => {
    filteredRecipes().forEach(r => selectedIds.add(r.id));
    renderList();
});

btnClearSelection.addEventListener('click', () => {
    selectedIds.clear();
    renderList();
});

btnGenerate.addEventListener('click', async () => {
    modalList.style.display = 'flex';
    listLoading.style.display = 'flex';
    listError.style.display = 'none';
    combinedList.innerHTML = '';
    copyFeedback.style.display = 'none';

    try {
        const res = await fetch('/api/shopping-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recipe_ids: Array.from(selectedIds) }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to build shopping list.');
        renderCombined(data);
    } catch (err) {
        listError.textContent = err.message;
        listError.style.display = 'block';
    } finally {
        listLoading.style.display = 'none';
    }
});

function renderCombined(rows) {
    if (!rows.length) {
        combinedList.innerHTML = '<li class="combined-empty">No ingredients found in the selected recipes.</li>';
        return;
    }
    combinedList.innerHTML = rows.map(r => {
        const sources = r.sources && r.sources.length
            ? `<span class="combined-sources">${escapeHtml(r.sources.join(', '))}</span>`
            : '';
        return `
            <li class="combined-item">
                <span class="combined-text">${escapeHtml(r.display)}</span>
                ${sources}
            </li>
        `;
    }).join('');
}

function plainText() {
    return Array.from(combinedList.querySelectorAll('.combined-text'))
        .map(el => el.textContent)
        .join('\n');
}

btnCopy.addEventListener('click', async () => {
    const text = plainText();
    if (!text) return;
    try {
        await navigator.clipboard.writeText(text);
        copyFeedback.style.display = 'inline';
        setTimeout(() => { copyFeedback.style.display = 'none'; }, 1500);
    } catch (e) {
        listError.textContent = 'Could not copy to clipboard.';
        listError.style.display = 'block';
    }
});

btnPrint.addEventListener('click', () => window.print());

function closeModal() {
    modalList.style.display = 'none';
}

btnCloseModal.addEventListener('click', closeModal);
modalList.addEventListener('click', (e) => {
    if (e.target === modalList) closeModal();
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modalList.style.display !== 'none') closeModal();
});

loadRecipes();
