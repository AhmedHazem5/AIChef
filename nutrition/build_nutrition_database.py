import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "nutrition"
    / "raw"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "nutrition"
    / "nutrition_database.json"
)

FOUNDATION_FILE = (
    RAW_DATA_DIR
    / "FoodData_Central_foundation_food_json_2026-04-30.json"
)

SR_LEGACY_FILE = (
    RAW_DATA_DIR
    / "FoodData_Central_sr_legacy_food_json_2018-04.json"
)


# ============================================================
# Nutrients we care about
# ============================================================

NUTRIENT_NAMES = {
    "Energy": "calories",
    "Protein": "protein_g",
    "Total lipid (fat)": "fat_g",
    "Carbohydrate, by difference": "carbohydrates_g",
}


# ============================================================
# Load USDA JSON
# ============================================================

def load_usda_file(
    path: Path,
):

    print(
        f"\nReading {path.name}..."
    )

    if not path.exists():

        raise FileNotFoundError(
            f"USDA file not found:\n{path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


# ============================================================
# Locate food list
# ============================================================

def get_foods(
    data,
):

    if "FoundationFoods" in data:
        return data["FoundationFoods"]

    if "SRLegacyFoods" in data:
        return data["SRLegacyFoods"]

    # Fallback in case USDA changes the outer key.
    for key, value in data.items():

        if (
            isinstance(value, list)
            and value
            and isinstance(value[0], dict)
        ):

            print(
                f"Using detected food list: {key}"
            )

            return value

    raise ValueError(
        "Could not locate food records "
        "inside USDA JSON file."
    )


# ============================================================
# Extract nutrients
# ============================================================

def extract_nutrients(
    food: dict,
):

    result = {
        "calories": None,
        "protein_g": None,
        "carbohydrates_g": None,
        "fat_g": None,
    }

    food_nutrients = food.get(
        "foodNutrients",
        [],
    )

    for food_nutrient in food_nutrients:

        if not isinstance(
            food_nutrient,
            dict,
        ):
            continue

        nutrient = food_nutrient.get(
            "nutrient",
            {},
        )

        if not isinstance(
            nutrient,
            dict,
        ):
            continue

        nutrient_name = nutrient.get(
            "name"
        )

        output_name = NUTRIENT_NAMES.get(
            nutrient_name
        )

        if not output_name:
            continue

        amount = food_nutrient.get(
            "amount"
        )

        if amount is None:
            continue

        # Energy can appear as kJ.
        # Only store kcal.
        if nutrient_name == "Energy":

            unit = (
                nutrient.get(
                    "unitName",
                    "",
                )
                .upper()
            )

            if unit != "KCAL":
                continue

        result[
            output_name
        ] = amount

    return result


# ============================================================
# Normalize portion text
# ============================================================

def clean_portion_text(
    text,
):

    if text is None:
        return ""

    return (
        str(text)
        .strip()
        .lower()
    )


# ============================================================
# Extract USDA food portions
#
# Example result:
#
# [
#     {
#         "amount": 1.0,
#         "unit": "large",
#         "modifier": "",
#         "description": "1 large",
#         "gram_weight": 50.0
#     }
# ]
# ============================================================

def extract_food_portions(
    food: dict,
):

    raw_portions = food.get(
        "foodPortions",
        [],
    )

    portions = []

    if not isinstance(
        raw_portions,
        list,
    ):
        return portions

    for portion in raw_portions:

        if not isinstance(
            portion,
            dict,
        ):
            continue

        gram_weight = portion.get(
            "gramWeight"
        )

        if gram_weight is None:
            continue

        amount = portion.get(
            "amount"
        )

        if amount is None:
            amount = 1.0

        measure_unit = portion.get(
            "measureUnit",
            {},
        )

        unit_name = ""

        if isinstance(
            measure_unit,
            dict,
        ):

            unit_name = (
                measure_unit.get(
                    "name",
                    ""
                )
                or measure_unit.get(
                    "abbreviation",
                    ""
                )
                or ""
            )

        modifier = (
            portion.get(
                "modifier"
            )
            or ""
        )

        portion_description = (
            portion.get(
                "portionDescription"
            )
            or ""
        )

        unit_name = clean_portion_text(
            unit_name
        )

        modifier = clean_portion_text(
            modifier
        )

        portion_description = (
            clean_portion_text(
                portion_description
            )
        )

        # Build a readable description even if USDA
        # didn't include portionDescription.
        if portion_description:

            description = (
                portion_description
            )

        else:

            description_parts = [
                str(amount),
            ]

            if unit_name:
                description_parts.append(
                    unit_name
                )

            if modifier:
                description_parts.append(
                    modifier
                )

            description = " ".join(
                description_parts
            ).strip()

        portions.append(
            {
                "amount":
                    amount,

                "unit":
                    unit_name,

                "modifier":
                    modifier,

                "description":
                    description,

                "gram_weight":
                    gram_weight,
            }
        )

    return portions


# ============================================================
# Convert one USDA food record
# ============================================================

def convert_food(
    food,
    source,
):

    if not isinstance(
        food,
        dict,
    ):
        return None

    description = (
        food.get(
            "description",
            ""
        )
        .strip()
    )

    if not description:
        return None

    nutrients = extract_nutrients(
        food
    )

    if all(
        value is None
        for value in nutrients.values()
    ):
        return None

    portions = extract_food_portions(
        food
    )

    return {
        "fdc_id":
            food.get(
                "fdcId"
            ),

        "description":
            description,

        "source":
            source,

        "calories_per_100g":
            nutrients[
                "calories"
            ],

        "protein_g_per_100g":
            nutrients[
                "protein_g"
            ],

        "carbohydrates_g_per_100g":
            nutrients[
                "carbohydrates_g"
            ],

        "fat_g_per_100g":
            nutrients[
                "fat_g"
            ],

        "portions":
            portions,
    }


# ============================================================
# Process one USDA dataset
# ============================================================

def process_dataset(
    path: Path,
    source: str,
):

    data = load_usda_file(
        path
    )

    foods = get_foods(
        data
    )

    print(
        f"Food records found: "
        f"{len(foods)}"
    )

    converted = []

    skipped_invalid = 0

    records_with_portions = 0

    total_portions = 0

    for food in foods:

        if not isinstance(
            food,
            dict,
        ):

            skipped_invalid += 1
            continue

        record = convert_food(
            food,
            source,
        )

        if not record:
            continue

        portions = record.get(
            "portions",
            [],
        )

        if portions:

            records_with_portions += 1

            total_portions += len(
                portions
            )

        converted.append(
            record
        )

    print(
        f"Usable nutrition records: "
        f"{len(converted)}"
    )

    if skipped_invalid:

        print(
            f"Skipped invalid/null records: "
            f"{skipped_invalid}"
        )

    print(
        f"Records with portion data: "
        f"{records_with_portions}"
    )

    print(
        f"Total portion records: "
        f"{total_portions}"
    )

    return converted


# ============================================================
# Build local nutrition database
# ============================================================

def build_nutrition_database():

    print(
        "Building local USDA "
        "nutrition database..."
    )

    foundation_records = (
        process_dataset(
            FOUNDATION_FILE,
            "USDA Foundation",
        )
    )

    sr_records = (
        process_dataset(
            SR_LEGACY_FILE,
            "USDA SR Legacy",
        )
    )

    all_records = (
        foundation_records
        + sr_records
    )

    records_with_portions = sum(
        1
        for record in all_records
        if record.get(
            "portions"
        )
    )

    total_portions = sum(
        len(
            record.get(
                "portions",
                [],
            )
        )
        for record in all_records
    )

    print(
        "\n================================"
    )

    print(
        f"Foundation records: "
        f"{len(foundation_records)}"
    )

    print(
        f"SR Legacy records: "
        f"{len(sr_records)}"
    )

    print(
        f"Total nutrition records: "
        f"{len(all_records)}"
    )

    print(
        f"Records with portion data: "
        f"{records_with_portions}"
    )

    print(
        f"Total stored portions: "
        f"{total_portions}"
    )

    print(
        "================================"
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            all_records,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        "\nNutrition database saved to:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    build_nutrition_database()