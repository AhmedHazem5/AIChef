from nutrition.ingredient_parser import (
    parse_ingredient,
)

from nutrition.weight_converter import (
    ingredient_to_grams,
)

from nutrition.nutrition_database import (
    find_complete_nutrition_fallback,
)
from functools import lru_cache
# ============================================================
# Frying oil estimation
# ============================================================

FRYING_OIL_ABSORPTION_RATE = 0.15


def get_consumed_grams(
    ingredient: str,
    parsed: dict,
    grams: float,
):

    text = ingredient.lower()

    food = (
        parsed.get(
            "food",
            ""
        )
        .lower()
    )

    is_oil = (
        "oil" in food
        or "shortening" in food
    )

    explicitly_for_frying = any(
        phrase in text
        for phrase in (
            "for frying",
            "for deep frying",
            "for deep-frying",
            "deep frying",
            "deep-frying",
        )
    )

    if (
        is_oil
        and explicitly_for_frying
    ):

        consumed_grams = (
            grams
            * FRYING_OIL_ABSORPTION_RATE
        )

        return (
            consumed_grams,
            True,
        )

    return (
        grams,
        False,
    )

# ============================================================
# Calculate nutrition for one ingredient
# ============================================================
@lru_cache(maxsize=4096)
def calculate_ingredient_nutrition(
    ingredient: str,
):

    parsed = parse_ingredient(
        ingredient
    )

    conversion = ingredient_to_grams(
        parsed
    )

    grams = conversion.get(
        "grams"
    )

    match = conversion.get(
        "match"
    )

    # ========================================================
    # Ingredient could not be resolved
    # ========================================================

    if (
        grams is None
        or not match
    ):

        return {
            "ingredient":
                ingredient,

            "parsed":
                parsed,

            "status":
                "unresolved",

            "reason":
                conversion.get(
                    "reason"
                ),

            "grams":
                grams,

            "nutrition":
                None,
        }

    # ========================================================
    # Primary USDA match
    # ========================================================

    record = match[
        "record"
    ]

    consumed_grams, frying_adjustment = (
        get_consumed_grams(
            ingredient,
            parsed,
            grams,
        )
    )

    factor = (
        consumed_grams
        / 100.0
    )

    nutrient_fields = {
        "calories":
            "calories_per_100g",

        "protein_g":
            "protein_g_per_100g",

        "carbohydrates_g":
            "carbohydrates_g_per_100g",

        "fat_g":
            "fat_g_per_100g",
    }

    values_per_100g = {}

    missing_fields = []

    for output_field, database_field in (
        nutrient_fields.items()
    ):

        value = record.get(
            database_field
        )

        values_per_100g[
            output_field
        ] = value

        if value is None:

            missing_fields.append(
                output_field
            )

    # ========================================================
    # Nutrition fallback
    #
    # IMPORTANT:
    #
    # We keep:
    #
    # - original food match
    # - original gram conversion
    # - every nutrient that exists on the original record
    #
    # We ONLY fill missing nutrients from another sufficiently
    # similar USDA food with complete macro information.
    # ========================================================

    fallback_match = None

    fallback_record = None

    fallback_fields = []

    if missing_fields:

        fallback_match = (
            find_complete_nutrition_fallback(
                food_name=parsed[
                    "food"
                ],

                excluded_fdc_id=
                    record.get(
                        "fdc_id"
                    ),
            )
        )

        if fallback_match:

            fallback_record = (
                fallback_match[
                    "record"
                ]
            )

            for output_field in (
                missing_fields
            ):

                database_field = (
                    nutrient_fields[
                        output_field
                    ]
                )

                fallback_value = (
                    fallback_record.get(
                        database_field
                    )
                )

                if (
                    fallback_value
                    is not None
                ):

                    values_per_100g[
                        output_field
                    ] = (
                        fallback_value
                    )

                    fallback_fields.append(
                        output_field
                    )

    # ========================================================
    # Calculate nutrition for actual ingredient weight
    # ========================================================

    nutrition = {}

    for output_field, value in (
        values_per_100g.items()
    ):

        if value is None:

            nutrition[
                output_field
            ] = None

        else:

            nutrition[
                output_field
            ] = (
                value
                * factor
            )

    # ========================================================
    # Determine whether nutrition is fully resolved
    # ========================================================

    nutrition_complete = all(
        value is not None
        for value in nutrition.values()
    )

    return {
        "ingredient":
            ingredient,

        "parsed":
            parsed,

        "status":
            "resolved",

        "grams":
            grams,

        "consumed_grams":
            consumed_grams,

        "frying_adjustment":
            frying_adjustment,

        "match_description":
            record.get(
                "description"
            ),

        "match_score":
            match.get(
                "score"
            ),

        "conversion":
            conversion.get(
                "reason"
            ),

        "nutrition":
            nutrition,

        "nutrition_complete":
            nutrition_complete,

        "fallback_used":
            bool(
                fallback_fields
            ),

        "fallback_fields":
            fallback_fields,

        "fallback_description":
            (
                fallback_record.get(
                    "description"
                )
                if fallback_record
                else None
            ),

        "fallback_score":
            (
                fallback_match.get(
                    "score"
                )
                if fallback_match
                else None
            ),
    }

# ============================================================
# Calculate nutrition for complete recipe
# ============================================================

def calculate_recipe_nutrition(
    ingredients: list[str],
    steps: list[str] | None = None,
):

    if steps is None:
        steps = []

    steps_text = " ".join(
        steps
    ).lower()

    recipe_uses_frying = any(
        phrase in steps_text
        for phrase in (
            "deep-fry",
            "deep fry",
            "deep-frying",
            "deep frying",
            "fry ",
            "fried",
            "frying",
            "drain them",
            "drain the",
        )
    )

    ingredient_results = []

    totals = {
        "calories":
            0.0,

        "protein_g":
            0.0,

        "carbohydrates_g":
            0.0,

        "fat_g":
            0.0,
    }

    resolved_count = 0

    for ingredient in ingredients:

        result = (
            calculate_ingredient_nutrition(
                ingredient
            )
        )

        parsed = result.get(
            "parsed",
            {},
        )

        food = (
            parsed.get(
                "food",
                ""
            )
            .lower()
        )

        unit = parsed.get(
            "unit"
        )

        quantity = parsed.get(
            "quantity"
        )

        is_oil = (
            "oil" in food
            or "shortening" in food
        )

        large_oil_amount = (
            is_oil
            and quantity is not None
            and (
                unit == "cup"
                or (
                    unit == "tbsp"
                    and quantity >= 4
                )
            )
        )

        if (
            recipe_uses_frying
            and large_oil_amount
            and result.get(
                "status"
            )
            == "resolved"
        ):

            original_grams = result.get(
                "grams"
            )

            if original_grams is not None:

                consumed_grams = (
                    original_grams
                    * FRYING_OIL_ABSORPTION_RATE
                )

                factor = (
                    consumed_grams
                    / original_grams
                )

                nutrition = result.get(
                    "nutrition",
                    {},
                )

                for key, value in (
                    nutrition.items()
                ):

                    if value is not None:

                        nutrition[key] = (
                            value
                            * factor
                        )

                result[
                    "consumed_grams"
                ] = consumed_grams

                result[
                    "frying_adjustment"
                ] = True

                result[
                    "conversion"
                ] = (
                    result.get(
                        "conversion",
                        ""
                    )
                    + " + frying absorption estimate"
                )

        ingredient_results.append(
            result
        )

        if (
            result["status"]
            != "resolved"
        ):
            continue

        resolved_count += 1

        nutrition = result[
            "nutrition"
        ]

        for key in totals:

            value = nutrition.get(
                key
            )

            if value is not None:

                totals[key] += value

    total_count = len(
        ingredients
    )

    coverage = (
        resolved_count
        / total_count
        if total_count
        else 0.0
    )

    # --------------------------------------------------------
    # Round final totals
    # --------------------------------------------------------

    totals = {
        key:
            round(
                value,
                1,
            )

        for key, value
        in totals.items()
    }

    return {
        "totals":
            totals,

        "resolved_ingredients":
            resolved_count,

        "total_ingredients":
            total_count,

        "coverage":
            round(
                coverage,
                3,
            ),

        "ingredient_results":
            ingredient_results,
    }


# ============================================================
# Test: Shrimp Chow Mein
# ============================================================

def test_shrimp_chow_mein():

    ingredients = [
        "1/2 lb dried egg noodles",
        "1 lb shelled cooked shrimp",
        "2 eggs, beaten",
        "2 tsps cooking oil",
        "1 medium onion, sliced",
        "10 water chestnuts, sliced",
        "6 dried Chinese mushrooms, soaked, sliced",
        "1/2 cup water",
        "1 1/3 cups Napa cabbage",
        "1/2 tsp salt",
        "1/2 tsp instant chicken bouillon granules",
        "1 tsp cornstarch in 1 tsp water",
        "2 green onions, chopped",
    ]

    result = (
        calculate_recipe_nutrition(
            ingredients
        )
    )

    print(
        "\n================================"
    )

    print(
        "SHRIMP CHOW MEIN NUTRITION TEST"
    )

    print(
        "================================"
    )

    for item in result[
        "ingredient_results"
    ]:

        print(
            f"\nIngredient: "
            f"{item['ingredient']}"
        )

        print(
            f"Status: "
            f"{item['status']}"
        )

        if (
            item["status"]
            == "resolved"
        ):

            print(
                f"Matched USDA: "
                f"{item['match_description']}"
            )

            print(
                f"Match score: "
                f"{item['match_score']}"
            )

            print(
                f"Grams: "
                f"{round(item['grams'], 2)}"
            )

            print(
                f"Conversion: "
                f"{item['conversion']}"
            )

            if item.get(
                "fallback_used"
            ):

                print(
                    "Nutrition fallback:"
                )

                print(
                    f"  Matched: "
                    f"{item['fallback_description']}"
                )

                print(
                    f"  Score: "
                    f"{item['fallback_score']}"
                )

                print(
                    f"  Filled fields: "
                    f"{item['fallback_fields']}"
                )

            print(
                "Nutrition:"
            )

            nutrition = item[
                "nutrition"
            ]

            print(
                f"  Calories: "
                f"{round(nutrition['calories'], 1) if nutrition['calories'] is not None else None}"
            )

            print(
                f"  Protein: "
                f"{round(nutrition['protein_g'], 1) if nutrition['protein_g'] is not None else None}"
            )

            print(
                f"  Carbs: "
                f"{round(nutrition['carbohydrates_g'], 1) if nutrition['carbohydrates_g'] is not None else None}"
            )

            print(
                f"  Fat: "
                f"{round(nutrition['fat_g'], 1) if nutrition['fat_g'] is not None else None}"
            )

        else:

            print(
                f"Reason: "
                f"{item['reason']}"
            )

    print(
        "\n================================"
    )

    print(
        "TOTALS"
    )

    print(
        "================================"
    )

    totals = result[
        "totals"
    ]

    print(
        f"Calories: "
        f"{totals['calories']}"
    )

    print(
        f"Protein: "
        f"{totals['protein_g']} g"
    )

    print(
        f"Carbohydrates: "
        f"{totals['carbohydrates_g']} g"
    )

    print(
        f"Fat: "
        f"{totals['fat_g']} g"
    )

    print(
        f"\nResolved ingredients: "
        f"{result['resolved_ingredients']}"
        f"/"
        f"{result['total_ingredients']}"
    )

    print(
        f"Coverage: "
        f"{result['coverage'] * 100:.1f}%"
    )


if __name__ == "__main__":

    test_shrimp_chow_mein()