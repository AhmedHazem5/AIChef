from nutrition.ingredient_parser import (
    parse_ingredient,
)

from nutrition.ingredient_parser import (
    parse_number,
)

from nutrition.nutrition_database import (
    find_food_match,
    find_top_food_matches,
)

import re

# ============================================================
# Direct mass conversions
# ============================================================

STANDARD_DENSITY_GRAMS = {

    "flour": {
        "cup": 125.0,
    },

    "crab": {
        "count": 163.0,
    },
    "ground pork": {
        "cup": 225.0,
    },

    "trout fillets": {
        "count": 62.0,
    },

    "salted peanuts": {
        "cup": 146.0,
    },

    "salted walnuts": {
        "cup": 117.0,
    },

    "flour tortillas": {
        "count": 30.0,
    },

    "6-inch flour tortillas": {
        "count": 30.0,
    },

    "boneless skinless chicken breast half": {
        "count": 174.0,
    },

    "shallots": {
        "count": 44.0,
    },

    "leek": {
        "count": 89.0,
    },

    "tofu cake": {
        "count": 100.0,
    },

    "water": {
        "cup": 236.588,
        "tbsp": 14.787,
        "tsp": 4.929,
    },

    "cooking oil": {
        "cup": 218.0,
        "tbsp": 13.6,
        "tsp": 4.53,
    },

    "vegetable oil": {
        "cup": 218.0,
        "tbsp": 13.6,
        "tsp": 4.53,
    },

    "shrimp": {
        "cup": 145.0,
    },

    "cooked shrimp": {
        "cup": 145.0,
    },

    "shelled cooked shrimp": {
        "cup": 145.0,
    },

    "eggplant": {
        "count": 458.0,
    },

    # Raw shredded/chopped Napa cabbage.
    # Used only when the matched USDA record does not
    # provide the requested cup portion.
    "napa cabbage": {
        "cup": 109.0,
    },

    "roasted sesame seeds": {
        "tbsp": 9.0,
        "tsp": 3.0,
    },

    "sesame seeds": {
        "tbsp": 9.0,
        "tsp": 3.0,
    },
}

DIRECT_GRAM_CONVERSIONS = {
    "g": 1.0,
    "kg": 1000.0,
    "oz": 28.349523125,
    "lb": 453.59237,
}


# ============================================================
# Normalize portion unit names
# ============================================================

def normalize_portion_unit(
    unit: str,
) -> str:

    unit = (
        unit
        .lower()
        .strip()
    )

    aliases = {
        "tablespoon":
            "tbsp",

        "tablespoons":
            "tbsp",

        "tbsp":
            "tbsp",

        "teaspoon":
            "tsp",

        "teaspoons":
            "tsp",

        "tsp":
            "tsp",

        "cup":
            "cup",

        "cups":
            "cup",

        "large":
            "large",

        "medium":
            "medium",

        "small":
            "small",
    }

    return aliases.get(
        unit,
        unit,
    )


# ============================================================
# Search USDA portion data
# ============================================================

def find_portion_grams(
    nutrition_record: dict,
    requested_unit: str,
):

    portions = nutrition_record.get(
        "portions",
        [],
    )

    requested_unit = (
        normalize_portion_unit(
            requested_unit
        )
    )

    matches = []

    # ========================================================
    # Relative volume conversions
    #
    # 1 cup = 16 tbsp = 48 tsp
    # ========================================================

    volume_in_teaspoons = {
        "cup": 48.0,
        "tbsp": 3.0,
        "tsp": 1.0,
    }

    for portion in portions:

        portion_unit = (
            normalize_portion_unit(
                portion.get(
                    "unit",
                    "",
                )
            )
        )

        description = (
            portion.get(
                "description",
                ""
            )
            .lower()
            .strip()
        )

        gram_weight = portion.get(
            "gram_weight"
        )

        amount = portion.get(
            "amount",
            1.0,
        )

        if gram_weight is None:
            continue

        if not amount:
            amount = 1.0

        # ====================================================
        # Try to determine the actual volume unit.
        #
        # USDA often stores:
        #
        # unit = "undetermined"
        # description = "1.0 undetermined cup"
        #
        # so we also inspect the description.
        # ====================================================

        detected_unit = portion_unit

        description_words = (
            description
            .replace(",", " ")
            .replace("(", " ")
            .replace(")", " ")
            .split()
        )

        for possible_unit in (
            "cup",
            "tbsp",
            "tablespoon",
            "tsp",
            "teaspoon",
        ):

            if possible_unit in description_words:

                detected_unit = (
                    normalize_portion_unit(
                        possible_unit
                    )
                )

                break

        # ====================================================
        # Exact requested unit
        # ====================================================

        if detected_unit == requested_unit:

            matches.append(
                {
                    "score":
                        5,

                    "grams_per_unit":
                        gram_weight
                        / amount,

                    "description":
                        description,
                }
            )

            continue

        # ====================================================
        # Convert between volume units
        #
        # Example:
        #
        # USDA:
        # 1 cup cornstarch = 128 g
        #
        # Recipe:
        # 1 tsp cornstarch
        #
        # 128 / 48 = 2.67 g/tsp
        # ====================================================

        if (
            detected_unit
            in volume_in_teaspoons
            and requested_unit
            in volume_in_teaspoons
        ):

            source_teaspoons = (
                volume_in_teaspoons[
                    detected_unit
                ]
            )

            target_teaspoons = (
                volume_in_teaspoons[
                    requested_unit
                ]
            )

            grams_per_source_unit = (
                gram_weight
                / amount
            )

            grams_per_requested_unit = (
                grams_per_source_unit
                * (
                    target_teaspoons
                    / source_teaspoons
                )
            )

            matches.append(
                {
                    "score":
                        4,

                    "grams_per_unit":
                        grams_per_requested_unit,

                    "description":
                        (
                            f"{description} "
                            f"(converted "
                            f"{detected_unit}"
                            f"→"
                            f"{requested_unit})"
                        ),
                }
            )

    if not matches:
        return None

    matches.sort(
        key=lambda item:
            item["score"],
        reverse=True,
    )

    return matches[0]

# ============================================================
# Count-based conversion
# ============================================================

def find_count_grams(
    nutrition_record: dict,
    requested_size: str | None = None,
    requested_food: str | None = None,
):

    portions = nutrition_record.get(
        "portions",
        [],
    )

    candidates = []

    count_words = {
        "large",
        "medium",
        "small",
        "piece",
        "pieces",
        "item",
        "items",
        "each",
        "whole",
        "wrapper",
        "wrappers",
        "head",
        "heads",
        "pod",
        "pods",
        "stalk",
        "stalks",
    }

    count_nouns = {
        "mushroom",
        "mushrooms",
        "egg",
        "eggs",
        "onion",
        "onions",
        "clove",
        "cloves",
        "waterchestnut",
        "waterchestnuts",
        "piece",
        "pieces",
        "item",
        "items",
        "wrapper",
        "wrappers",
        "head",
        "heads",
        "pod",
        "pods",
        "pepper",
        "peppers",
        "carrot",
        "carrots",
        "stalk",
        "stalks",
    }

    volume_words = {
        "cup",
        "cups",
        "tbsp",
        "tablespoon",
        "tablespoons",
        "tsp",
        "teaspoon",
        "teaspoons",
        "fl",
        "oz",
    }

    partial_item_words = {
        "slice",
        "slices",
        "ring",
        "rings",
        "chopped",
        "shredded",
        "diced",
        "minced",
        "cup",
        "cups",
        "tbsp",
        "tablespoon",
        "tablespoons",
        "tsp",
        "teaspoon",
        "teaspoons",
    }

    requested_food_lower = (
        requested_food.lower().strip()
        if requested_food
        else ""
    )

    for portion in portions:

        if not isinstance(
            portion,
            dict,
        ):
            continue

        gram_weight = portion.get(
            "gram_weight"
        )

        amount = portion.get(
            "amount",
            1.0,
        )

        if gram_weight is None:
            continue

        if not amount:
            amount = 1.0

        description = (
            portion.get(
                "description",
                ""
            )
            .lower()
            .strip()
        )

        unit = (
            portion.get(
                "unit",
                ""
            )
            .lower()
            .strip()
        )

        modifier = (
            portion.get(
                "modifier",
                ""
            )
            .lower()
            .strip()
        )

        description_words = set(
            description
            .replace("(", " ")
            .replace(")", " ")
            .replace(",", " ")
            .replace('"', " ")
            .split()
        )

        # ====================================================
        # Volume portion
        # ====================================================

        is_volume = (
            unit in volume_words
            or bool(
                description_words
                & volume_words
            )
        )

        if is_volume:

            count_match = re.search(
                r"\(([\d.]+)\s+"
                r"(?:(small|medium|large)\s+)?"
                r"(?:"
                r"egg|eggs|"
                r"mushroom|mushrooms|"
                r"waterchestnut|waterchestnuts|"
                r"piece|pieces|"
                r"item|items"
                r")"
                r"\)",
                description,
            )

            if count_match:

                count = float(
                    count_match.group(1)
                )

                contained_size = (
                    count_match.group(2)
                )

                if count > 0:

                    score = 5

                    if requested_size:

                        if (
                            contained_size
                            == requested_size
                        ):

                            score += 10

                        elif contained_size:

                            score -= 3

                    candidates.append(
                        {
                            "score":
                                score,

                            "grams_per_count":
                                gram_weight
                                / count,

                            "description":
                                description,
                        }
                    )

            continue

        # ====================================================
        # Count portion
        # ====================================================

        score = 0

        if unit in count_words:

            score = 4

        elif modifier in count_words:

            score = 4

        elif (
            description_words
            & count_words
        ):

            score = 3

        elif (
            description_words
            & count_nouns
        ):

            score = 2

        if score == 0:
            continue

        is_partial_item = bool(
            description_words
            & partial_item_words
        )

        # ====================================================
        # Match explicit size
        # ====================================================

        if requested_size:

            size_matched = False

            if unit == requested_size:
                size_matched = True

            if modifier == requested_size:
                size_matched = True

            if (
                requested_size
                in description_words
            ):

                size_matched = True

            if size_matched:

                if is_partial_item:
                    score -= 5

                else:
                    score += 10

            else:

                other_sizes = {
                    "small",
                    "medium",
                    "large",
                }

                found_sizes = (
                    description_words
                    & other_sizes
                )

                if (
                    found_sizes
                    and requested_size
                    not in found_sizes
                ):

                    score -= 3

        if is_partial_item:
            score -= 2

        # ====================================================
        # Prefer subtype-specific portion
        #
        # Example:
        #
        # requested food = wanton skins
        #
        # USDA record contains:
        #
        # wrapper, eggroll = 32 g
        # wrapper, wonton = 8 g
        #
        # We want the wonton wrapper.
        # ====================================================

        if requested_food_lower:

            if (
                "wanton" in requested_food_lower
                or "wonton" in requested_food_lower
            ):

                if "wonton" in description:
                    score += 100

                if "eggroll" in description:
                    score -= 100

            if (
                "egg roll" in requested_food_lower
                or "eggroll" in requested_food_lower
            ):

                if "eggroll" in description:
                    score += 100

                if "wonton" in description:
                    score -= 100

        grams_per_count = (
            gram_weight
            / amount
        )

        candidates.append(
            {
                "score":
                    score,

                "grams_per_count":
                    grams_per_count,

                "description":
                    description,
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item:
            item["score"],
        reverse=True,
    )

    return candidates[0]


# ============================================================
# Candidate USDA matches for portion fallback
# ============================================================

def get_food_match_candidates(
    food: str,
    limit: int = 12,
):

    primary = find_food_match(
        food
    )

    candidates = []
    seen_ids = set()

    if primary:

        candidates.append(
            primary
        )

        fdc_id = primary[
            "record"
        ].get(
            "fdc_id"
        )

        if fdc_id is not None:
            seen_ids.add(
                fdc_id
            )

    for item in find_top_food_matches(
        food,
        limit=limit,
    ):

        record = item[
            "record"
        ]

        score = float(
            item["score"]
        )

        if score < 0.80:
            continue

        fdc_id = record.get(
            "fdc_id"
        )

        if (
            fdc_id is not None
            and fdc_id in seen_ids
        ):
            continue

        candidates.append(
            {
                "query":
                    food,

                "normalized_query":
                    food,

                "score":
                    round(
                        score,
                        3,
                    ),

                "record":
                    record,
            }
        )

        if fdc_id is not None:
            seen_ids.add(
                fdc_id
            )

    return candidates


def find_count_portion_with_fallback(
    food: str,
    requested_size: str | None = None,
):

    candidates = get_food_match_candidates(
        food
    )

    for match in candidates:

        portion = find_count_grams(
            match["record"],
            requested_size=requested_size,
            requested_food=food,
        )

        if portion:

            return match, portion

    return (
        candidates[0]
        if candidates
        else None,
        None,
    )


def find_volume_portion_with_fallback(
    food: str,
    requested_unit: str,
):

    candidates = get_food_match_candidates(
        food
    )

    for match in candidates:

        portion = find_portion_grams(
            match["record"],
            requested_unit,
        )

        if portion:

            return match, portion

    return (
        candidates[0]
        if candidates
        else None,
        None,
    )

def find_embedded_mass(
    parsed: dict,
):

    original = (
        parsed.get(
            "original",
            ""
        )
        .lower()
    )

    # ========================================================
    # Normalize malformed mixed fractions from cookbook text
    #
    # Example:
    # "11/2 lbs" -> "1 1/2 lbs"
    # ========================================================

    original = re.sub(
        r"\b(\d)(\d/\d)\b",
        r"\1 \2",
        original,
    )

    quantity = parsed.get(
        "quantity"
    )

    mixed_mass = re.search(
        r"(?:about|~)?\s*"
        r"(\d+\s+\d+/\d+)\s*"
        r"(lb|lbs|oz|g|kg)\b",
        original,
    )

    if mixed_mass:

        amount = parse_number(
            mixed_mass.group(1)
        )

        unit = (
            mixed_mass.group(2)
            .lower()
        )

        if unit == "lbs":
            unit = "lb"

        return (
            amount
            * DIRECT_GRAM_CONVERSIONS[
                unit
            ]
        )

    # ----------------------------------------------------
    # Example:
    # 1 (~2 lb) whole snapper
    # 1 (14 oz) canned bamboo shoots
    # 1 (3 oz.) package ramen noodles
    # ----------------------------------------------------

    parenthetical = re.search(
        r"\(\s*~?\s*"
        r"(\d+(?:\.\d+)?)\s*"
        r"(lb|lbs|oz|g|kg)"
        r"\.?\s*\)",
        original,
    )

    if parenthetical:

        amount = float(
            parenthetical.group(1)
        )

        unit = (
            parenthetical
            .group(2)
            .lower()
        )

        if unit == "lbs":
            unit = "lb"

        return (
            amount
            * DIRECT_GRAM_CONVERSIONS[
                unit
            ]
        )

    # ----------------------------------------------------
    # Example:
    # 1 can (8oz) bamboo shoots
    # ----------------------------------------------------

    can_weight = re.search(
        r"\bcan\s*\(\s*"
        r"(\d+(?:\.\d+)?)\s*"
        r"(oz|lb|g|kg)"
        r"\s*\)",
        original,
    )

    if can_weight:

        amount = float(
            can_weight.group(1)
        )

        unit = (
            can_weight
            .group(2)
            .lower()
        )

        return (
            amount
            * DIRECT_GRAM_CONVERSIONS[
                unit
            ]
        )

    # ----------------------------------------------------
    # Example:
    # 4 cod steaks, ~6 oz each
    # ----------------------------------------------------

    each_weight = re.search(
        r"~?\s*"
        r"(\d+(?:\.\d+)?)\s*"
        r"(oz|lb|g|kg)"
        r"\s+each\b",
        original,
    )

    if (
        each_weight
        and quantity is not None
    ):

        amount = float(
            each_weight.group(1)
        )

        unit = (
            each_weight
            .group(2)
            .lower()
        )

        return (
            quantity
            * amount
            * DIRECT_GRAM_CONVERSIONS[
                unit
            ]
        )

    return None


# ============================================================
# Convert parsed ingredient to grams
# ============================================================

def ingredient_to_grams(
    parsed: dict,
):

    quantity = parsed.get(
        "quantity"
    )

    unit = parsed.get(
        "unit"
    )

    size = parsed.get(
        "size"
    )

    food = parsed.get(
        "food",
        "",
    )

    # ========================================================
    # Validate parsed ingredient
    # ========================================================

    if (
        quantity is None
        or not food
    ):

        return {
            "grams":
                None,

            "reason":
                "missing quantity or food",

            "match":
                None,
        }


    # ========================================================
    # Embedded mass conversion
    #
    # Examples:
    #
    # 1 (~2 lb) whole snapper
    # 1 can (8oz) bamboo shoots
    # 1 (3 oz.) package ramen noodles
    # 4 cod steaks, ~6 oz each
    #
    # In these cases, the useful mass is embedded somewhere
    # inside the original ingredient text rather than being
    # the main parsed unit.
    # ========================================================

    embedded_grams = (
        find_embedded_mass(
            parsed
        )
    )

    if embedded_grams is not None:

        match = find_food_match(
            food
        )

        return {
            "grams":
                embedded_grams,

            "reason":
                "embedded mass conversion",

            "match":
                match,
        }

    # ========================================================
    # Direct mass conversion
    #
    # Examples:
    #
    # 1 lb shrimp
    # 8 oz chicken
    # 100 g rice
    # 1 kg potatoes
    #
    # These do not need USDA portion information.
    # ========================================================

    if unit in DIRECT_GRAM_CONVERSIONS:

        grams = (
            quantity
            * DIRECT_GRAM_CONVERSIONS[
                unit
            ]
        )

        match = find_food_match(
            food
        )

        return {
            "grams":
                grams,

            "reason":
                (
                    "direct mass conversion"
                    if match
                    else
                    "direct mass conversion; no nutrition match"
                ),

            "match":
                match,
        }

    # ========================================================
    # Find USDA food record
    # ========================================================

    match = find_food_match(
        food
    )

    if not match:

        return {
            "grams":
                None,

            "reason":
                "no nutrition match",

            "match":
                None,
        }

    # ========================================================
    # Count-based ingredient
    #
    # If the best USDA match lacks a useful count portion,
    # try another very close USDA record before failing.
    # ========================================================

    if unit == "count":

        selected_match, portion = (
            find_count_portion_with_fallback(
                food,
                requested_size=size,
            )
        )

        if not portion:

            food_key = (
                food
                .lower()
                .strip()
            )

            fallback_count = (
                STANDARD_DENSITY_GRAMS
                .get(
                    food_key,
                    {}
                )
                .get(
                    "count"
                )
            )

            if fallback_count is not None:

                return {
                    "grams":
                        quantity
                        * fallback_count,

                    "reason":
                        "standard local count conversion",

                    "match":
                        match,
                }

            return {
                "grams":
                    None,

                "reason":
                    "no count portion found",

                "match":
                    selected_match
                    or match,
            }

        grams = (
            quantity
            * portion[
                "grams_per_count"
            ]
        )

        return {
            "grams":
                grams,

            "reason":
                (
                    "USDA count portion: "
                    + portion[
                        "description"
                    ]
                ),

            "match":
                selected_match,
        }

    # ========================================================
    # Volume units
    #
    # Examples:
    #
    # 1 cup cabbage
    # 2 tbsp oil
    # 1/2 tsp salt
    #
    # First try USDA portion information.
    # ========================================================

    if unit in {
        "cup",
        "tbsp",
        "tsp",
    }:

        selected_match, portion = (
            find_volume_portion_with_fallback(
                food,
                unit,
            )
        )

        # ====================================================
        # USDA has the requested volume information
        # ====================================================

        if portion:

            grams = (
                quantity
                * portion[
                    "grams_per_unit"
                ]
            )

            return {
                "grams":
                    grams,

                "reason":
                    (
                        "USDA portion: "
                        + portion[
                            "description"
                        ]
                    ),

                "match":
                    selected_match,
            }

        # ====================================================
        # Local trusted fallback
        #
        # Used only for foods where we explicitly defined
        # a reasonable local conversion.
        #
        # Examples:
        #
        # cooking oil
        # water
        # Napa cabbage
        # ====================================================

        food_key = (
            food
            .lower()
            .strip()
        )

        density = (
            STANDARD_DENSITY_GRAMS
            .get(
                food_key,
                {}
            )
            .get(
                unit
            )
        )

        if density is not None:

            grams = (
                quantity
                * density
            )

            return {
                "grams":
                    grams,

                "reason":
                    (
                        "standard local "
                        f"{unit} conversion"
                    ),

                "match":
                    match,
            }

        # ====================================================
        # No safe volume conversion
        # ====================================================

        return {
            "grams":
                None,

            "reason":
                (
                    "no USDA portion "
                    f"for {unit}"
                ),

            "match":
                match,
        }

    # ========================================================
    # Other currently unsupported units
    #
    # Examples might eventually include:
    #
    # can
    # clove
    # package
    #
    # We deliberately do NOT guess their weights.
    # ========================================================

    return {
        "grams":
            None,

        "reason":
            (
                f"unsupported unit: "
                f"{unit}"
            ),

        "match":
            match,
    }

# ============================================================
# Test helper
# ============================================================

def test_ingredient(
    ingredient: str,
):

    parsed = parse_ingredient(
        ingredient
    )

    result = ingredient_to_grams(
        parsed
    )

    print(
        "\n=============================="
    )

    print(
        f"Ingredient: {ingredient}"
    )

    print(
        "=============================="
    )

    print(
        f"Parsed food: "
        f"{parsed['food']}"
    )

    print(
        f"Quantity: "
        f"{parsed['quantity']}"
    )

    print(
        f"Unit: "
        f"{parsed['unit']}"
    )

    if result[
        "match"
    ]:

        record = result[
            "match"
        ][
            "record"
        ]

        print(
            f"Matched USDA food: "
            f"{record['description']}"
        )

        print(
            f"Match score: "
            f"{result['match']['score']}"
        )

    print(
        f"Grams: "
        f"{result['grams']}"
    )

    print(
        f"Conversion: "
        f"{result['reason']}"
    )


# ============================================================
# Tests
# ============================================================

if __name__ == "__main__":

    test_ingredients = [
        "1 medium crab, cleaned and crushed",
        "8 thin trout fillets, skin removed",
        "3/4 lb of halibut fillets, about 1/2-inch thick, cut into 1-by-3-inch strips",
        "1/2 C. flour",
    ]

    for ingredient in test_ingredients:

        test_ingredient(
            ingredient
        )
