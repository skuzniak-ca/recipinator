"""Quantity parsing, unit conversion, and aggregation for shopping list generation."""

import re
from collections import defaultdict


# Unicode fraction characters -> decimal values
UNICODE_FRACTIONS = {
    '½': 0.5, '⅓': 1/3, '⅔': 2/3, '¼': 0.25, '¾': 0.75,
    '⅕': 0.2, '⅖': 0.4, '⅗': 0.6, '⅘': 0.8,
    '⅙': 1/6, '⅚': 5/6, '⅛': 0.125, '⅜': 0.375,
    '⅝': 0.625, '⅞': 0.875,
}


# Unit aliases -> canonical name
UNIT_ALIASES = {
    # Weight
    'g': 'g', 'gram': 'g', 'grams': 'g',
    'kg': 'kg', 'kilogram': 'kg', 'kilograms': 'kg',
    'oz': 'oz', 'ounce': 'oz', 'ounces': 'oz',
    'lb': 'lb', 'lbs': 'lb', 'pound': 'lb', 'pounds': 'lb',
    # Volume
    'ml': 'ml', 'milliliter': 'ml', 'milliliters': 'ml',
    'l': 'l', 'liter': 'l', 'liters': 'l',
    'cup': 'cup', 'cups': 'cup',
    'tbsp': 'tbsp', 'tablespoon': 'tbsp', 'tablespoons': 'tbsp',
    'tsp': 'tsp', 'teaspoon': 'tsp', 'teaspoons': 'tsp',
    'qt': 'qt', 'quart': 'qt', 'quarts': 'qt',
    'pt': 'pt', 'pint': 'pt', 'pints': 'pt',
    'gal': 'gal', 'gallon': 'gal', 'gallons': 'gal',
    # Count-likes (kept distinct: don't combine cans + slices)
    'clove': 'clove', 'cloves': 'clove',
    'can': 'can', 'cans': 'can',
    'package': 'package', 'packages': 'package', 'pkg': 'package',
    'bag': 'bag', 'bags': 'bag',
    'bottle': 'bottle', 'bottles': 'bottle',
    'jar': 'jar', 'jars': 'jar',
    'stick': 'stick', 'sticks': 'stick',
    'slice': 'slice', 'slices': 'slice',
    'piece': 'piece', 'pieces': 'piece',
    'head': 'head', 'heads': 'head',
    'sprig': 'sprig', 'sprigs': 'sprig',
    'stalk': 'stalk', 'stalks': 'stalk',
    'bunch': 'bunch', 'bunches': 'bunch',
    'pinch': 'pinch', 'pinches': 'pinch',
    'dash': 'dash', 'dashes': 'dash',
    'handful': 'handful', 'handfuls': 'handful',
}

WEIGHT_UNITS = {'g', 'kg', 'oz', 'lb'}
VOLUME_UNITS = {'ml', 'l', 'cup', 'tbsp', 'tsp', 'qt', 'pt', 'gal', 'fl oz'}
COUNT_UNITS = {'clove', 'can', 'package', 'bag', 'bottle', 'jar', 'stick',
               'slice', 'piece', 'head', 'sprig', 'stalk', 'bunch',
               'pinch', 'dash', 'handful'}

TO_GRAMS = {
    'g': 1.0,
    'kg': 1000.0,
    'oz': 28.3495,
    'lb': 453.592,
}

TO_ML = {
    'ml': 1.0,
    'l': 1000.0,
    'cup': 236.588,
    'tbsp': 14.7868,
    'tsp': 4.92892,
    'qt': 946.353,
    'pt': 473.176,
    'gal': 3785.41,
    'fl oz': 29.5735,
}

# Grams per US cup (~236.588 ml). Used only to merge mixed weight+volume entries
# for the same ingredient. Densities vary - kept narrow on purpose: we'd rather
# list the entry separately than invent a wrong total.
DENSITY_G_PER_CUP = {
    'flour': 125, 'all-purpose flour': 125, 'all purpose flour': 125,
    'bread flour': 130, 'whole wheat flour': 120, 'cake flour': 115,
    'sugar': 200, 'granulated sugar': 200, 'white sugar': 200,
    'brown sugar': 220, 'packed brown sugar': 220, 'light brown sugar': 220,
    'dark brown sugar': 220,
    'powdered sugar': 120, 'confectioners sugar': 120, 'icing sugar': 120,
    'butter': 227,
    'rice': 195, 'white rice': 195, 'brown rice': 190, 'jasmine rice': 195,
    'oats': 90, 'rolled oats': 90, 'oatmeal': 90, 'quick oats': 90,
    'cornmeal': 160, 'polenta': 160,
    'cocoa powder': 100, 'cocoa': 100,
    'chocolate chips': 175,
    'breadcrumbs': 110, 'bread crumbs': 110, 'panko': 60,
    'honey': 340, 'maple syrup': 322,
    'milk': 245, 'water': 237, 'oil': 218, 'olive oil': 216,
    'vegetable oil': 218, 'canola oil': 218,
    'yogurt': 245, 'sour cream': 230, 'cream': 240, 'heavy cream': 238,
    'salt': 273, 'kosher salt': 218, 'table salt': 292,
    'baking powder': 192, 'baking soda': 220,
    'cornstarch': 120, 'corn starch': 120,
    'peanut butter': 258,
}


def _replace_unicode_fractions(text):
    """Replace unicode fractions with decimal equivalents.

    A digit immediately preceding the fraction (e.g. ``1½``) is merged into
    the same number; otherwise the fraction stands alone.
    """
    for ch, val in UNICODE_FRACTIONS.items():
        text = re.sub(
            r'(\d+)' + re.escape(ch),
            lambda m, v=val: f"{int(m.group(1)) + v}",
            text,
        )
        text = text.replace(ch, str(val))
    return text


_QTY_RE = re.compile(
    r'^(\d+/\d+|\d+(?:\.\d+)?(?:\s+\d+/\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?)'
)


def _qty_to_float(qty_str):
    """Convert a captured quantity expression to float."""
    qty_str = qty_str.strip()

    # Range "2-3" -> conservative lower bound
    if '-' in qty_str:
        return float(qty_str.split('-')[0].strip())

    # Mixed number "1 1/2"
    if ' ' in qty_str and '/' in qty_str:
        whole, frac = qty_str.split(' ', 1)
        num, den = frac.split('/')
        return float(whole) + float(num) / float(den)

    # Plain fraction "1/2"
    if '/' in qty_str:
        num, den = qty_str.split('/')
        return float(num) / float(den)

    return float(qty_str)


def parse_quantity(raw_text):
    """Parse the leading quantity and unit out of an ingredient string.

    Returns ``(qty, unit, note)``:
      - ``qty`` is a float or None.
      - ``unit`` is a canonical unit string (e.g. 'g', 'cup', 'clove') or None.
      - ``note`` captures phrases like 'to taste' / 'as needed' worth preserving
        in the shopping list when no usable quantity is present.
    """
    if not raw_text:
        return None, None, None

    text = raw_text.strip()
    lower = text.lower()
    note = None
    if 'to taste' in lower:
        note = 'to taste'
    elif 'as needed' in lower:
        note = 'as needed'

    # Drop parentheticals: the outer quantity is the shopping unit.
    text = re.sub(r'\([^)]*\)', '', text).strip()
    text = _replace_unicode_fractions(text)

    match = _QTY_RE.match(text)
    if not match:
        return None, None, note

    try:
        qty = _qty_to_float(match.group(1))
    except (ValueError, ZeroDivisionError):
        return None, None, note

    rest = text[match.end():].strip()
    rest_tokens = rest.split()
    unit = None
    if rest_tokens:
        first = rest_tokens[0].lower().strip('.,;:!?')
        # "fl oz" is the only two-word unit we care about
        if first == 'fl' and len(rest_tokens) > 1:
            second = rest_tokens[1].lower().strip('.,;:!?')
            if second in ('oz', 'ounce', 'ounces'):
                unit = 'fl oz'
        if unit is None and first in UNIT_ALIASES:
            unit = UNIT_ALIASES[first]

    return qty, unit, note


def _unit_type(unit):
    if unit in WEIGHT_UNITS:
        return 'weight'
    if unit in VOLUME_UNITS:
        return 'volume'
    if unit in COUNT_UNITS:
        return 'count'
    if unit is None:
        return 'none'
    return 'other'


def _format_qty(qty):
    """Format a float as int, common fraction, or 2-decimal trimmed."""
    if qty is None:
        return ''
    if abs(qty - round(qty)) < 0.01:
        return str(int(round(qty)))
    whole = int(qty) if qty >= 1 else 0
    frac = qty - whole
    common = [
        (0.125, '1/8'), (0.25, '1/4'), (1/3, '1/3'), (0.375, '3/8'),
        (0.5, '1/2'), (0.625, '5/8'), (2/3, '2/3'), (0.75, '3/4'),
        (0.875, '7/8'),
    ]
    for value, label in common:
        if abs(frac - value) < 0.02:
            return f"{whole} {label}" if whole else label
    return f"{qty:.2f}".rstrip('0').rstrip('.')


def _format_numeric(qty):
    """Format a quantity as a decimal number (no fraction snapping).

    Used for weight/volume units like g, kg, ml, l where fractions look wrong.
    """
    if qty is None:
        return ''
    if abs(qty - round(qty)) < 0.01:
        return str(int(round(qty)))
    rounded = round(qty, 2)
    return f"{rounded:g}"


def _pluralize(unit, qty):
    """Apply plural form for count-like units. Cookbook convention: qty > 1 -> plural."""
    short = {'g', 'kg', 'mg', 'ml', 'l', 'oz', 'lb', 'tsp', 'tbsp',
             'qt', 'pt', 'gal', 'fl oz'}
    if unit in short:
        return unit
    if qty is not None and qty <= 1.0 + 1e-9:
        return unit
    plural_map = {
        'cup': 'cups', 'clove': 'cloves', 'can': 'cans',
        'package': 'packages', 'bag': 'bags', 'bottle': 'bottles',
        'jar': 'jars', 'stick': 'sticks', 'slice': 'slices',
        'piece': 'pieces', 'head': 'heads', 'sprig': 'sprigs',
        'stalk': 'stalks', 'bunch': 'bunches', 'pinch': 'pinches',
        'dash': 'dashes', 'handful': 'handfuls',
    }
    return plural_map.get(unit, unit)


def _smart_weight(grams):
    if grams >= 1000:
        return _format_numeric(grams / 1000), 'kg'
    return _format_numeric(round(grams, 1)), 'g'


_COMMON_FRACTIONS = (0.125, 0.25, 1/3, 0.375, 0.5, 0.625, 2/3, 0.75, 0.875)


def _is_clean(qty):
    """True if qty is close to an int or a common cookbook fraction.

    Tolerance matches _format_qty so the two agree: if _is_clean accepts a
    value, _format_qty will render it as that int/fraction (not as a decimal).
    """
    if abs(qty - round(qty)) < 0.02:
        return True
    frac = qty - int(qty)
    return any(abs(frac - v) < 0.02 for v in _COMMON_FRACTIONS)


def _smart_volume(ml):
    """Pick the most readable volume unit. Prefer larger units when they
    produce a clean fraction; otherwise step down to the next unit."""
    if ml >= 1000:
        return _format_numeric(ml / 1000), 'l'
    if ml >= TO_ML['cup'] * 0.24:  # >= ~1/4 cup
        cups = ml / TO_ML['cup']
        if _is_clean(cups):
            return _format_qty(cups), _pluralize('cup', cups)
        tbsp = ml / TO_ML['tbsp']
        if _is_clean(tbsp) and tbsp <= 16:
            return _format_qty(tbsp), 'tbsp'
        return _format_numeric(cups), _pluralize('cup', cups)
    if ml >= TO_ML['tbsp']:
        tbsp = ml / TO_ML['tbsp']
        if _is_clean(tbsp):
            return _format_qty(tbsp), 'tbsp'
        tsp = ml / TO_ML['tsp']
        if _is_clean(tsp):
            return _format_qty(tsp), 'tsp'
        return _format_numeric(tbsp), 'tbsp'
    if ml >= 1:
        return _format_qty(ml / TO_ML['tsp']), 'tsp'
    return _format_numeric(round(ml, 1)), 'ml'


def _lookup_density(name):
    """Return grams-per-cup for an ingredient name, trying progressive matches."""
    name = name.lower().strip()
    if name in DENSITY_G_PER_CUP:
        return DENSITY_G_PER_CUP[name]
    # Substring match: "all-purpose flour" should match an entry for "flour"
    for key, val in DENSITY_G_PER_CUP.items():
        if key in name or name in key:
            return val
    return None


def combine_ingredients(recipes):
    """Aggregate ingredients across recipes into shopping-list rows.

    Args:
        recipes: list of recipe dicts each with 'title' and 'ingredients'
                 (list of {'name': normalized, 'raw_text': original}).

    Returns:
        List of dicts: {'display', 'name', 'note', 'sources'} sorted by name.
    """
    groups = defaultdict(list)
    for recipe in recipes:
        title = recipe.get('title', '')
        for ing in recipe.get('ingredients', []):
            qty, unit, note = parse_quantity(ing['raw_text'])
            groups[ing['name']].append({
                'qty': qty, 'unit': unit, 'note': note,
                'raw': ing['raw_text'], 'recipe_title': title,
            })

    output = []
    for name in sorted(groups):
        output.extend(_combine_group(name, groups[name]))
    return output


def _combine_group(name, items):
    sources = sorted({i['recipe_title'] for i in items if i['recipe_title']})

    weight_total_g = 0.0
    volume_total_ml = 0.0
    count_subtotals = defaultdict(float)  # unit -> qty (or '__bare__' for no-unit counts)
    note_only = []  # 'to taste' / 'as needed' / None
    has_weight = has_volume = False

    for it in items:
        qty, unit, note = it['qty'], it['unit'], it['note']
        if qty is None:
            note_only.append(note)
            continue
        utype = _unit_type(unit)
        if utype == 'weight':
            weight_total_g += qty * TO_GRAMS[unit]
            has_weight = True
        elif utype == 'volume':
            volume_total_ml += qty * TO_ML[unit]
            has_volume = True
        elif utype == 'count':
            count_subtotals[unit] += qty
        elif utype == 'none':
            count_subtotals['__bare__'] += qty
        else:
            note_only.append(it['raw'])

    # Mixed weight + volume: merge via density if known; else leave as separate rows.
    if has_weight and has_volume:
        density = _lookup_density(name)
        if density is not None:
            weight_total_g += (volume_total_ml / TO_ML['cup']) * density
            volume_total_ml = 0.0
            has_volume = False

    rows = []

    if has_weight and weight_total_g > 0:
        qty_str, unit_str = _smart_weight(weight_total_g)
        rows.append({
            'display': f"{qty_str} {unit_str} {name}",
            'name': name, 'note': None, 'sources': sources,
        })

    if has_volume and volume_total_ml > 0:
        qty_str, unit_str = _smart_volume(volume_total_ml)
        rows.append({
            'display': f"{qty_str} {unit_str} {name}",
            'name': name, 'note': None, 'sources': sources,
        })

    for unit, qty in sorted(count_subtotals.items()):
        if unit == '__bare__':
            display = f"{_format_qty(qty)} {name}"
        else:
            display = f"{_format_qty(qty)} {_pluralize(unit, qty)} {name}"
        rows.append({
            'display': display, 'name': name, 'note': None, 'sources': sources,
        })

    if note_only and not rows:
        # No measurable quantities at all - keep one descriptive line.
        chosen = next((n for n in ('to taste', 'as needed') if n in note_only), None)
        if chosen:
            rows.append({
                'display': f"{name} ({chosen})",
                'name': name, 'note': chosen, 'sources': sources,
            })
        else:
            rows.append({
                'display': name, 'name': name, 'note': None, 'sources': sources,
            })
    # If both note-only and measurable rows exist, the measurable rows already
    # cover what the shopper needs - drop the redundant "to taste" note.

    return rows
