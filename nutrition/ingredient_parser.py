import re
from fractions import Fraction


# ============================================================
# Unit normalization
# ============================================================

UNIT_ALIASES = {
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",

    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",

    "g": "g",
    "gram": "g",
    "grams": "g",

    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",

    "tsp": "tsp",
    "tsps": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",

    "tbsp": "tbsp",
    "tbsps": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",

    "cup": "cup",
    "cups": "cup",

    "can": "can",
    "cans": "can",

    "clove": "count",
    "cloves": "count",

    "piece": "count",
    "pieces": "count",
}


# ============================================================
# Size words
#
# These normally describe a counted ingredient:
#
# 1 medium onion
# 2 large tomatoes
# ============================================================

SIZE_WORDS = {
    "small",
    "medium",
    "large",
}


# ============================================================
# Preparation words to remove
#
# Keep words such as:
#
# dried
# cooked
# raw
#
# because those can affect USDA matching.
# ============================================================

PREPARATION_WORDS = {
    "chopped",
    "minced",
    "sliced",
    "diced",
    "beaten",
    "peeled",
    "trimmed",
    "halved",
    "cubed",
    "crushed",
    "shredded",
    "seeded",
    "finely",
    "coarsely",
    "soaked",
    "drained",
    "cleaned",
    "cracked",
    "smashed",
    "softened",
    "grated",
    "de-veined",
    "deveined",
    "thin",
}


# ============================================================
# Parse numbers
# ============================================================

def parse_number(
    text: str,
):

    text = text.strip()

    # --------------------------------------------------------
    # Mixed number:
    #
    # 1 1/2
    # --------------------------------------------------------

    if re.fullmatch(
        r"\d+\s+\d+/\d+",
        text,
    ):

        whole, fraction = (
            text.split(
                maxsplit=1
            )
        )

        return (
            float(whole)
            + float(
                Fraction(
                    fraction
                )
            )
        )

    # --------------------------------------------------------
    # Fraction:
    #
    # 1/2
    # --------------------------------------------------------

    if re.fullmatch(
        r"\d+/\d+",
        text,
    ):

        return float(
            Fraction(
                text
            )
        )

    # --------------------------------------------------------
    # Decimal / integer
    # --------------------------------------------------------

    try:

        return float(
            text
        )

    except ValueError:

        return None


# ============================================================
# Singularize simple ingredient words
# ============================================================

def singularize_simple_food(
    text: str,
) -> str:

    text = text.strip()

    # Only simple cases for now.
    # We do NOT want aggressive English stemming.

    simple_plural_map = {
        "eggs": "egg",
        "onions": "onion",
        "tomatoes": "tomato",
        "potatoes": "potato",
        "mushrooms": "mushroom",
    }

    return simple_plural_map.get(
        text,
        text,
    )


# ============================================================
# Clean food name
# ============================================================

def clean_food_name(
    text: str,
) -> str:

    text = text.lower().strip()

    # --------------------------------------------------------
    # Fix common cookbook/extraction typos
    # --------------------------------------------------------

    typo_replacements = {
        "monced": "minced",
        "bonelss": "boneless",
        "bonned": "boned",
        "cornstach": "cornstarch",
        "shreded": "shredded",
        "slided": "sliced",
        "seperated": "separated",
        "magarine": "margarine",
    }

    for wrong, correct in typo_replacements.items():
        text = re.sub(
            rf"\b{re.escape(wrong)}\b",
            correct,
            text,
        )

    # --------------------------------------------------------
    # Remove secondary mixtures
    #
    # "cornstarch in 1 tsp water"
    # -> "cornstarch"
    # --------------------------------------------------------

    text = re.split(
        r"\s+in\s+\d",
        text,
        maxsplit=1,
    )[0]

    # --------------------------------------------------------
    # Remove explanatory examples
    #
    # Cookbook ingredients sometimes contain subtype examples:
    #
    # "lean boneless beef steak such as top round,
    #  flank, sirloin or New York steak"
    #
    # The examples make USDA matching much worse. The actual
    # ingredient is simply "lean boneless beef steak".
    # --------------------------------------------------------

    text = re.split(
        r"\s+such\s+as\s+",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()

    # --------------------------------------------------------
    # Remove parenthetical notes
    # --------------------------------------------------------

    text = re.sub(
        r"\([^)]*\)",
        " ",
        text,
    )

    # --------------------------------------------------------
    # Remove cookbook instructions after commas when they are
    # clearly preparation instructions.
    #
    # Keep alternatives such as:
    # chicken breasts or thighs
    # --------------------------------------------------------

    text = re.sub(
        r",\s*(?:"
        r"skinned|boned|boneless|"
        r"peeled|seeded|trimmed|"
        r"cut|chopped|minced|slice|sliced|"
        r"diced|shredded|crushed|"
        r"beaten|drained|soaked|"
        r"cleaned|cracked|smashed|"
        r"softened|grated|"
        r"de[- ]?veined|"
        r"finely|thinly|lightly|"
        r"slightly|coarsely"
        r")\b.*$",
        "",
        text,
    )

    # --------------------------------------------------------
    # Remove common preparation phrases that may occur without
    # commas.
    # --------------------------------------------------------

    preparation_phrases = [
        r"\bskinned\s+and\s+boned\b",
        r"\bskinless\s+and\s+boneless\b",
        r"\bshelled\s+and\s+de[- ]?veined\b",
        r"\bpeeled\s+and\s+de[- ]?veined\b",
        r"\bcleaned\s+and\s+cracked\b",
        r"\bskin\s+removed\b",
        r"\bcut\s+into\b.*$",
        r"\bcut\s+crosswise\b.*$",
        r"\bcut\s+lengthwise\b.*$",
        r"\broll[- ]cut\b.*$",
    ]

    for pattern in preparation_phrases:
        text = re.sub(
            pattern,
            " ",
            text,
        )

    # --------------------------------------------------------
    # Remove preference/example descriptions
    #
    # "fresh fish fillet, preferably cod or haddock"
    # -> "fresh fish fillet"
    # --------------------------------------------------------

    text = re.split(
        r"\s+preferably\s+",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()

    # --------------------------------------------------------
    # Remove approximate embedded weight descriptions
    #
    # "potatoes about 11/2 lbs"
    # -> "potatoes"
    #
    # The original ingredient text is still preserved and the
    # weight converter reads the embedded mass from there.
    # --------------------------------------------------------

    text = re.sub(
        r"\s+about\s+"
        r"\d+(?:\s+\d+/\d+|/\d+)?\s*"
        r"(?:lb|lbs|oz|g|kg)\b.*$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    
    text = re.sub(
        r"\s+about\s+.*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # --------------------------------------------------------
    # Replace punctuation
    # --------------------------------------------------------

    text = re.sub(
        r"[,;:]",
        " ",
        text,
    )

    words = []

    for word in text.split():

        cleaned_word = (
            word.strip()
            .lower()
        )

        if cleaned_word in PREPARATION_WORDS:
            continue

        if cleaned_word in SIZE_WORDS:
            continue

        words.append(
            cleaned_word
        )

    text = " ".join(
        words
    )

    # --------------------------------------------------------
    # Remove dangling connectors
    # --------------------------------------------------------

    text = re.sub(
        r"\b(?:and|or)\s*$",
        "",
        text,
    )

    text = re.sub(
        r"^of\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return singularize_simple_food(
        text
    )


# ============================================================
# Ingredient parser
# ============================================================

def parse_ingredient(
    ingredient: str,
):

    original = ingredient.strip()

    if not original:

        return {
            "original":
                original,

            "quantity":
                None,

            "unit":
                None,

            "size":
                None,

            "food":
                "",
        }

    text = original.strip()

    # ========================================================
    # Normalize cookbook shorthand
    # ========================================================

    text = re.sub(
        r"\bC\.",
        "cup",
        text,
        flags=re.IGNORECASE,
    )

    # ========================================================
    # Handle numeric ranges
    #
    # 4-6 chilies -> 5
    # 3 -4 cups   -> 3.5
    # ========================================================

    range_match = re.match(
        r"^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\b",
        text,
    )

    range_quantity = None

    if range_match:

        low = float(
            range_match.group(1)
        )

        high = float(
            range_match.group(2)
        )

        range_quantity = (
            low + high
        ) / 2.0

        text = (
            text[
                range_match.end():
            ]
            .strip()
        )

    # ========================================================
    # Quantity
    #
    # Supports:
    #
    # 1
    # 1/2
    # 1 1/2
    # 2.5
    # ========================================================

    quantity_match = re.match(
        r"^("
        r"\d+\s+\d+/\d+"
        r"|"
        r"\d+/\d+"
        r"|"
        r"\d+(?:\.\d+)?"
        r")\b",
        text,
    )

    quantity = range_quantity

    if (
        quantity is None
        and quantity_match
    ):

        quantity_text = (
            quantity_match.group(1)
        )

        quantity = parse_number(
            quantity_text
        )

        text = (
            text[
                quantity_match.end():
            ]
            .strip()
        )

    # ========================================================
    # Explicit unit
    # ========================================================

    unit = None

    if text:

        first_word_match = re.match(
            r"^([A-Za-z]+)\b",
            text,
        )

        if first_word_match:

            first_word = (
                first_word_match
                .group(1)
                .lower()
            )

            normalized_unit = (
                UNIT_ALIASES.get(
                    first_word
                )
            )

            if normalized_unit:

                unit = (
                    normalized_unit
                )

                text = (
                    text[
                        first_word_match.end():
                    ]
                    .strip()
                )

    # ========================================================
    # Preserve size descriptor
    #
    # Example:
    #
    # 1 medium onion
    #
    # quantity = 1
    # unit = count
    # size = medium
    # food = onion
    # ========================================================

    size = None

    if (
        quantity is not None
        and unit is None
    ):

        size_match = re.match(
            r"^(small|medium|large)(?:[-\s]?size(?:d)?)?\b",
            text,
            flags=re.IGNORECASE,
        )

        if size_match:

            size = (
                size_match
                .group(1)
                .lower()
            )

            text = (
                text[
                    size_match.end():
                ]
                .strip()
            )

            unit = "count"

    # ========================================================
    # Detect implicit counted ingredients
    #
    # Examples:
    #
    # 2 eggs
    # 10 water chestnuts
    # 6 dried Chinese mushrooms
    # 2 green onions
    #
    # If there is a quantity but no measurement unit, the
    # quantity represents individual pieces/items.
    # ========================================================

    if (
        quantity is not None
        and unit is None
    ):

        unit = "count"

    # ========================================================
    # Clean food
    # ========================================================

    food = clean_food_name(
        text
    )

    # ========================================================
    # Special plural cleanup
    # ========================================================

    if food == "eggs":
        food = "egg"

    return {
        "original":
            original,

        "quantity":
            quantity,

        "unit":
            unit,

        "size":
            size,

        "food":
            food,
    }

# ============================================================
# Test parser
# ============================================================

def test_parser():

    examples = [
        "1 medium crab, cleaned and crushed",
        "1 egg, slightly beaten",
        "8 thin trout fillets, skin removed",
        "3 slices fresh ginger, smashed",
        "3 -4 C. leftover mashed potatoes",
        "1 lb fresh salmon fillets, slice into 1-inch-thick",
        "1 lb fresh fish fillet, preferably cod or haddock",
        "3 large potatoes about 11/2 lbs",
        "1 lb raw shrimp (in shell), de-veined",
    ]

    print(
        "\n=============================="
    )

    print(
        "INGREDIENT PARSER TEST"
    )

    print(
        "=============================="
    )

    for ingredient in examples:

        parsed = parse_ingredient(
            ingredient
        )

        print(
            f"\nOriginal: "
            f"{parsed['original']}"
        )

        print(
            f"Quantity: "
            f"{parsed['quantity']}"
        )

        print(
            f"Unit: "
            f"{parsed['unit']}"
        )

        print(
            f"Food: "
            f"{parsed['food']}"
        )


if __name__ == "__main__":

    test_parser()