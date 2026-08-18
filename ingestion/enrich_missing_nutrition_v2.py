import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from functools import lru_cache
from nutrition.calculate_nutrition import (
    calculate_recipe_nutrition,
)


# ============================================================
# Configuration
# ============================================================

load_dotenv()

API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found in .env"
    )


MODEL_NAME = "gemini-3.5-flash-lite"

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

STRUCTURED_RECIPE_DIR = (
    PROJECT_ROOT
    / "data"
    / "structured_recipes"
)

NUTRITION_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "nutrition"
)

CACHE_PATH = (
    NUTRITION_DATA_DIR
    / "gemini_nutrition_batch_cache.json"
)


# ============================================================
# Input files
# ============================================================

INPUT_FILES = [
    "italian_recipes_gemini.json",
    "italian2_recipes_gemini.json",
    "healthy_foods_recipes_gemini.json",
    "world_cuisines_recipes_gemini.json",
]


# ============================================================
# Gemini batching
# ============================================================

# 8 recipes per API request.
#
# This should keep total Gemini calls low while still producing
# manageable prompts.
GEMINI_RECIPES_PER_BATCH = 8

GEMINI_DELAY_SECONDS = 2


REQUIRED_NUTRITION_FIELDS = (
    "calories",
    "protein_g",
    "carbohydrates_g",
    "fat_g",
)


# ============================================================
# Negligible ingredients
# ============================================================

NEGLIGIBLE_PATTERNS = [
    # Salt / pepper
    r"^\s*salt\s*$",
    r"^\s*pepper\s*$",
    r"^\s*black\s+pepper\s*$",

    r"\bsalt\s+to\s+taste\b",
    r"\bpepper\s+to\s+taste\b",
    r"\bblack\s+pepper\s+to\s+taste\b",
    r"\bsalt\s+and\s+pepper\s+to\s+taste\b",

    r"\ba?\s*pinch\s+of\s+salt\b",
    r"\ba?\s*pinch\s+of\s+pepper\b",

    r"\bseason\s+to\s+taste\b",

    # Water
    r"^\s*water\s*$",
    r"^\s*cold\s+water\s*$",
    r"^\s*hot\s+water\s*$",
    r"^\s*boiling\s+water\s*$",

    r"\bwater\s+as\s+needed\b",
    r"\bwater\s+as\s+required\b",
    r"\bwater\s+if\s+needed\b",

    # Optional ingredients should not contribute to the
    # nutrition of the base recipe.
    r"\boptional\b",
]


NEGLIGIBLE_EXACT_TERMS = {
    "ice",
    "ice cubes",
}


# ============================================================
# JSON helpers
# ============================================================

def load_json(
    path: Path,
):
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def save_json(
    path: Path,
    data,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        path.with_suffix(
            path.suffix + ".tmp"
        )
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temporary_path.replace(
        path
    )


def clean_json_text(
    raw: str,
) -> str:

    raw = raw.strip()

    if raw.startswith(
        "```json"
    ):

        raw = raw[
            len("```json"):
        ]

    elif raw.startswith(
        "```"
    ):

        raw = raw[
            len("```"):
        ]

    if raw.endswith(
        "```"
    ):
        raw = raw[:-3]

    return raw.strip()


# ============================================================
# Cache helpers
# ============================================================

def load_cache():

    if not CACHE_PATH.exists():

        return {
            "context_estimates": {}
        }

    data = load_json(
        CACHE_PATH
    )

    if not isinstance(
        data,
        dict,
    ):
        data = {}

    data.setdefault(
        "context_estimates",
        {},
    )

    return data


def save_cache(
    cache,
):

    save_json(
        CACHE_PATH,
        cache,
    )


def normalize_text(
    text: str,
) -> str:

    text = str(
        text
    ).lower().strip()

    text = text.replace(
        "’",
        "'",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def build_context_cache_key(
    recipe_id: str,
    ingredient: str,
):

    return (
        f"{recipe_id}|"
        f"{normalize_text(ingredient)}"
    )


# ============================================================
# Ingredient filtering
# ============================================================

def is_negligible_ingredient(
    ingredient: str,
) -> bool:

    text = (
        str(
            ingredient
        )
        .lower()
        .strip()
    )

    normalized = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    if normalized in (
        NEGLIGIBLE_EXACT_TERMS
    ):
        return True

    for pattern in (
        NEGLIGIBLE_PATTERNS
    ):

        if re.search(
            pattern,
            text,
        ):
            return True

    return False


# ============================================================
# Existing nutrition
# ============================================================

def nutrition_complete(
    nutrition,
):

    if not isinstance(
        nutrition,
        dict,
    ):
        return False

    return all(
        nutrition.get(
            field
        )
        is not None
        for field
        in REQUIRED_NUTRITION_FIELDS
    )


def extract_serving_count(
    servings,
):

    if servings is None:
        return None

    if isinstance(
        servings,
        (int, float),
    ):

        value = float(
            servings
        )

        return (
            value
            if value > 0
            else None
        )

    match = re.search(
        r"\d+(?:\.\d+)?",
        str(
            servings
        ),
    )

    if not match:
        return None

    value = float(
        match.group()
    )

    return (
        value
        if value > 0
        else None
    )


def normalize_existing_nutrition(
    recipe: dict,
):
    """
    Existing nutrition from a cookbook always wins.

    If it is per-serving, convert it to whole-recipe totals.
    """

    nutrition = recipe.get(
        "nutrition",
        {}
    )

    if not nutrition_complete(
        nutrition
    ):
        return False

    basis = nutrition.get(
        "basis"
    )

    # Already correct.
    if basis == "whole_recipe":

        recipe[
            "nutrition_source"
        ] = recipe.get(
            "nutrition_source",
            "source_book",
        )

        return True

    # Convert cookbook per-serving values.
    if basis == "per_serving":

        servings = (
            extract_serving_count(
                recipe.get(
                    "servings"
                )
            )
        )

        if servings is None:

            # Preserve source data rather than guessing.
            recipe[
                "nutrition_source"
            ] = "source_book"

            return True

        recipe[
            "nutrition"
        ] = {
            "calories":
                round(
                    float(
                        nutrition[
                            "calories"
                        ]
                    )
                    * servings,
                    1,
                ),

            "protein_g":
                round(
                    float(
                        nutrition[
                            "protein_g"
                        ]
                    )
                    * servings,
                    1,
                ),

            "carbohydrates_g":
                round(
                    float(
                        nutrition[
                            "carbohydrates_g"
                        ]
                    )
                    * servings,
                    1,
                ),

            "fat_g":
                round(
                    float(
                        nutrition[
                            "fat_g"
                        ]
                    )
                    * servings,
                    1,
                ),

            "basis":
                "whole_recipe",
        }

        recipe[
            "nutrition_source"
        ] = "source_book"

        recipe[
            "nutrition_original_basis"
        ] = "per_serving"

        return True

    # Complete but basis unknown.
    #
    # Do not change the actual numbers.
    recipe[
        "nutrition_source"
    ] = "source_book"

    return True


# ============================================================
# Local calculator helpers
# ============================================================

def get_local_totals(
    calculation,
):

    totals = calculation.get(
        "totals",
        {},
    )

    return {
        "calories":
            float(
                totals.get(
                    "calories",
                    0,
                )
                or 0
            ),

        "protein_g":
            float(
                totals.get(
                    "protein_g",
                    0,
                )
                or 0
            ),

        "carbohydrates_g":
            float(
                totals.get(
                    "carbohydrates_g",
                    0,
                )
                or 0
            ),

        "fat_g":
            float(
                totals.get(
                    "fat_g",
                    0,
                )
                or 0
            ),
    }


def get_unresolved_ingredients(
    calculation,
):

    unresolved = []

    for item in calculation.get(
        "ingredient_results",
        [],
    ):

        if item.get(
            "status"
        ) == "resolved":
            continue

        ingredient = str(
            item.get(
                "ingredient",
                "",
            )
        ).strip()

        if not ingredient:
            continue

        unresolved.append(
            ingredient
        )

    return unresolved


def add_to_totals(
    totals,
    nutrition,
):

    for field in (
        REQUIRED_NUTRITION_FIELDS
    ):

        totals[
            field
        ] += float(
            nutrition.get(
                field,
                0,
            )
            or 0
        )


# ============================================================
# Prepare recipe
# ============================================================

def prepare_recipe(
    recipe,
):
    """
    Do everything possible without Gemini.

    Returns a state object describing what remains unresolved.
    """

    recipe_id = recipe.get(
        "id",
        recipe.get(
            "title",
            "unknown_recipe",
        ),
    )

    title = recipe.get(
        "title",
        "Unknown recipe",
    )

    # --------------------------------------------------------
    # Cookbook nutrition already exists
    # --------------------------------------------------------

    if normalize_existing_nutrition(
        recipe
    ):

        return {
            "recipe":
                recipe,

            "recipe_id":
                recipe_id,

            "title":
                title,

            "status":
                "complete",

            "source":
                "source_book",

            "totals":
                None,

            "unresolved":
                [],

            "omitted":
                [],
        }

    ingredients = recipe.get(
        "ingredients",
        []
    )

    if not ingredients:

        return {
            "recipe":
                recipe,

            "recipe_id":
                recipe_id,

            "title":
                title,

            "status":
                "failed",

            "reason":
                "No ingredients",

            "totals":
                None,

            "unresolved":
                [],

            "omitted":
                [],
        }

    calculation_ingredients = []

    omitted = []

    # --------------------------------------------------------
    # Remove negligible ingredients
    # --------------------------------------------------------

    for ingredient in ingredients:

        ingredient = str(
            ingredient
        ).strip()

        if is_negligible_ingredient(
            ingredient
        ):

            omitted.append(
                ingredient
            )

        else:

            calculation_ingredients.append(
                ingredient
            )

    if not calculation_ingredients:

        return {
            "recipe":
                recipe,

            "recipe_id":
                recipe_id,

            "title":
                title,

            "status":
                "failed",

            "reason":
                "No meaningful ingredients",

            "totals":
                None,

            "unresolved":
                [],

            "omitted":
                omitted,
        }

    # --------------------------------------------------------
    # Local calculation
    # --------------------------------------------------------

    calculation = (
        calculate_recipe_nutrition(
            calculation_ingredients
        )
    )

    totals = get_local_totals(
        calculation
    )

    unresolved = (
        get_unresolved_ingredients(
            calculation
        )
    )

    # Remove anything negligible that survived local parsing.
    filtered_unresolved = []

    for ingredient in unresolved:

        if is_negligible_ingredient(
            ingredient
        ):

            omitted.append(
                ingredient
            )

        else:

            filtered_unresolved.append(
                ingredient
            )

    unresolved = (
        filtered_unresolved
    )

    return {
        "recipe":
            recipe,

        "recipe_id":
            recipe_id,

        "title":
            title,

        "status":
            (
                "needs_gemini"
                if unresolved
                else
                "complete_local"
            ),

        "source":
            "calculated_local",

        "totals":
            totals,

        "unresolved":
            unresolved,

        "omitted":
            sorted(
                set(
                    omitted
                )
            ),

        "local_coverage":
            calculation.get(
                "coverage",
                0.0,
            ),
    }


# ============================================================
# Cache resolution
# ============================================================

def apply_cached_estimates(
    state,
    cache,
):
    """
    Apply estimates we've already obtained from Gemini.

    Returns list of ingredients that still need Gemini.
    """

    still_unresolved = []

    context_cache = cache[
        "context_estimates"
    ]

    for ingredient in (
        state[
            "unresolved"
        ]
    ):

        cache_key = (
            build_context_cache_key(
                state[
                    "recipe_id"
                ],
                ingredient,
            )
        )

        if cache_key in (
            context_cache
        ):

            estimate = (
                context_cache[
                    cache_key
                ]
            )

            add_to_totals(
                state[
                    "totals"
                ],
                estimate,
            )

            state.setdefault(
                "cache_hits",
                [],
            ).append(
                ingredient
            )

        else:

            still_unresolved.append(
                ingredient
            )

    state[
        "unresolved"
    ] = still_unresolved


# ============================================================
# Gemini batched request
# ============================================================

def estimate_batch_with_gemini(
    client,
    states,
):
    """
    ONE Gemini call can process unresolved ingredients
    from up to GEMINI_RECIPES_PER_BATCH recipes.
    """

    request_recipes = []

    for state in states:

        request_recipes.append(
            {
                "recipe_id":
                    state[
                        "recipe_id"
                    ],

                "title":
                    state[
                        "title"
                    ],

                "ingredients":
                    state[
                        "recipe"
                    ].get(
                        "ingredients",
                        [],
                    ),

                "unresolved_ingredients":
                    state[
                        "unresolved"
                    ],
            }
        )

    request_json = json.dumps(
        request_recipes,
        indent=2,
        ensure_ascii=False,
    )

    prompt = f"""
You are helping an OFFLINE recipe-ingestion system estimate
nutrition for ingredients that could not be resolved by its
local nutrition database.

You are processing multiple recipes in ONE request.

============================================================
RECIPES
============================================================

{request_json}

============================================================
TASK
============================================================

For every unresolved ingredient listed above, estimate ONLY
the nutrition contribution of that ingredient AS USED IN
that specific recipe.

Use the complete ingredient list to understand context.

Examples:

If an ingredient says:

"2 tablespoons butter"

estimate the nutrition of exactly 2 tablespoons butter.

If it says:

"some butter"

estimate a conservative typical amount for that recipe.

If it says:

"meat"

use the recipe context to infer a reasonable ingredient and
amount.

If it says:

"pieces of bones"

and the recipe is a stock or broth, estimate only the likely
nutrition contribution transferred into the prepared recipe.

============================================================
IMPORTANT RULES
============================================================

- Do NOT calculate complete recipe nutrition.

- Only estimate ingredients listed under unresolved_ingredients.

- Do NOT include nutrition from locally resolved ingredients.

- Do NOT estimate salt.

- Do NOT estimate pepper.

- Do NOT estimate plain water.

- Do NOT estimate ice.

- Do NOT include optional ingredients.

- Use conservative estimates when quantities are vague.

- Never invent additional recipe ingredients.

- Keep all numbers numeric.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON:

{{
  "recipes": [
    {{
      "recipe_id": "recipe_id",
      "estimates": [
        {{
          "ingredient": "ingredient exactly as provided",
          "calories": 0.0,
          "protein_g": 0.0,
          "carbohydrates_g": 0.0,
          "fat_g": 0.0,
          "estimated_amount": "estimated quantity or interpretation",
          "confidence": "medium"
        }}
      ]
    }}
  ]
}}

confidence must be:

"high"
"medium"
or
"low"

Return every requested recipe_id.

Return every unresolved ingredient exactly once.

Do not output markdown.

Do not output explanations outside the JSON.
"""

    interaction = (
        client.interactions.create(
            model=MODEL_NAME,
            input=prompt,
        )
    )

    raw = clean_json_text(
        interaction.output_text
    )

    result = json.loads(
        raw
    )

    recipes = result.get(
        "recipes",
        []
    )

    if not isinstance(
        recipes,
        list,
    ):

        raise RuntimeError(
            "Gemini response has no recipe list."
        )

    return recipes


# ============================================================
# Apply Gemini response
# ============================================================

def apply_gemini_response(
    states,
    response_recipes,
    cache,
):
    states_by_id = {
        str(
            state[
                "recipe_id"
            ]
        ):
            state
        for state in states
    }

    for response_recipe in (
        response_recipes
    ):

        recipe_id = str(
            response_recipe.get(
                "recipe_id",
                "",
            )
        )

        if recipe_id not in (
            states_by_id
        ):
            continue

        state = states_by_id[
            recipe_id
        ]

        requested_lookup = {
            normalize_text(
                ingredient
            ):
                ingredient

            for ingredient in (
                state[
                    "unresolved"
                ]
            )
        }

        processed = set()

        for estimate in (
            response_recipe.get(
                "estimates",
                []
            )
        ):

            ingredient = str(
                estimate.get(
                    "ingredient",
                    "",
                )
            ).strip()

            normalized = (
                normalize_text(
                    ingredient
                )
            )

            if normalized not in (
                requested_lookup
            ):
                continue

            original_ingredient = (
                requested_lookup[
                    normalized
                ]
            )

            cleaned_estimate = {
                "calories":
                    float(
                        estimate.get(
                            "calories",
                            0,
                        )
                        or 0
                    ),

                "protein_g":
                    float(
                        estimate.get(
                            "protein_g",
                            0,
                        )
                        or 0
                    ),

                "carbohydrates_g":
                    float(
                        estimate.get(
                            "carbohydrates_g",
                            0,
                        )
                        or 0
                    ),

                "fat_g":
                    float(
                        estimate.get(
                            "fat_g",
                            0,
                        )
                        or 0
                    ),

                "estimated_amount":
                    str(
                        estimate.get(
                            "estimated_amount",
                            "",
                        )
                    ),

                "confidence":
                    str(
                        estimate.get(
                            "confidence",
                            "low",
                        )
                    ),

                "source":
                    "gemini_estimate",
            }

            add_to_totals(
                state[
                    "totals"
                ],
                cleaned_estimate,
            )

            state.setdefault(
                "gemini_estimates",
                [],
            ).append(
                {
                    "ingredient":
                        original_ingredient,

                    "estimated_amount":
                        cleaned_estimate[
                            "estimated_amount"
                        ],

                    "confidence":
                        cleaned_estimate[
                            "confidence"
                        ],
                }
            )

            cache_key = (
                build_context_cache_key(
                    recipe_id,
                    original_ingredient,
                )
            )

            cache[
                "context_estimates"
            ][
                cache_key
            ] = (
                cleaned_estimate
            )

            processed.add(
                normalized
            )

        # Any ingredient Gemini failed to return stays unresolved.
        state[
            "unresolved"
        ] = [
            ingredient
            for ingredient in (
                state[
                    "unresolved"
                ]
            )
            if normalize_text(
                ingredient
            )
            not in processed
        ]

    save_cache(
        cache
    )


# ============================================================
# Finalize recipe
# ============================================================

def finalize_recipe(
    state,
):
    recipe = state[
        "recipe"
    ]

    if state[
        "status"
    ] == "complete":

        return recipe

    if state.get(
        "totals"
    ) is None:

        return recipe

    totals = state[
        "totals"
    ]

    recipe[
        "nutrition"
    ] = {
        "calories":
            round(
                totals[
                    "calories"
                ],
                1,
            ),

        "protein_g":
            round(
                totals[
                    "protein_g"
                ],
                1,
            ),

        "carbohydrates_g":
            round(
                totals[
                    "carbohydrates_g"
                ],
                1,
            ),

        "fat_g":
            round(
                totals[
                    "fat_g"
                ],
                1,
            ),

        "basis":
            "whole_recipe",
    }

    has_gemini = bool(
        state.get(
            "gemini_estimates"
        )
        or state.get(
            "cache_hits"
        )
    )

    recipe[
        "nutrition_source"
    ] = (
        "calculated_with_gemini_fallback"
        if has_gemini
        else
        "calculated_local"
    )

    recipe[
        "nutrition_metadata"
    ] = {
        "local_coverage":
            state.get(
                "local_coverage"
            ),

        "gemini_estimated_ingredients":
            state.get(
                "gemini_estimates",
                [],
            ),

        "cache_hits":
            state.get(
                "cache_hits",
                [],
            ),

        "omitted_ingredients":
            state.get(
                "omitted",
                [],
            ),

        "still_unresolved":
            state.get(
                "unresolved",
                [],
            ),
    }

    return recipe


# ============================================================
# Process file
# ============================================================

def process_file(
    path,
    client,
    cache,
):

    print(
        "\n========================================"
    )

    print(
        f"PROCESSING: {path.name}"
    )

    print(
        "========================================"
    )

    recipes = load_json(
        path
    )

    states = []

    # ========================================================
    # Pass 1 — local calculation only
    # ========================================================

    for index, recipe in enumerate(
        recipes,
        start=1,
    ):

        print(
            f"[LOCAL {index}/{len(recipes)}] "
            f"{recipe.get('title')}"
        )

        state = prepare_recipe(
            recipe
        )

        if (
            state[
                "status"
            ] == "needs_gemini"
        ):

            apply_cached_estimates(
                state,
                cache,
            )

            # Cache may have solved everything.
            if not state[
                "unresolved"
            ]:

                state[
                    "status"
                ] = "complete_local"

        states.append(
            state
        )

    # ========================================================
    # Build Gemini recipe batches
    # ========================================================

    gemini_states = [
        state
        for state in states
        if (
            state[
                "status"
            ] == "needs_gemini"
            and state[
                "unresolved"
            ]
        )
    ]

    batches = [
        gemini_states[
            index:
            index
            + GEMINI_RECIPES_PER_BATCH
        ]

        for index in range(
            0,
            len(
                gemini_states
            ),
            GEMINI_RECIPES_PER_BATCH,
        )
    ]

    print(
        f"\nRecipes needing Gemini: "
        f"{len(gemini_states)}"
    )

    print(
        f"Gemini API batches required: "
        f"{len(batches)}"
    )

    # ========================================================
    # Gemini batches
    # ========================================================

    gemini_calls = 0

    for batch_index, batch in enumerate(
        batches,
        start=1,
    ):

        print(
            "\n--------------------------------"
        )

        print(
            f"GEMINI BATCH "
            f"{batch_index}/{len(batches)}"
        )

        print(
            f"Recipes: "
            f"{len(batch)}"
        )

        print(
            "--------------------------------"
        )

        for state in batch:

            print(
                f"{state['recipe_id']} "
                f"{state['title']}"
            )

            for ingredient in (
                state[
                    "unresolved"
                ]
            ):

                print(
                    f"    ? {ingredient}"
                )

        try:

            response = (
                estimate_batch_with_gemini(
                    client,
                    batch,
                )
            )

            gemini_calls += 1

            apply_gemini_response(
                batch,
                response,
                cache,
            )

            print(
                "Gemini batch successful."
            )

        except Exception as error:

            print(
                f"GEMINI BATCH FAILED: "
                f"{error}"
            )

            # Keep these unresolved rather than fabricating data.

        time.sleep(
            GEMINI_DELAY_SECONDS
        )

    # ========================================================
    # Finalize all recipes
    # ========================================================

    final_recipes = []

    unresolved_count = 0

    source_count = 0

    for state in states:

        recipe = finalize_recipe(
            state
        )

        final_recipes.append(
            recipe
        )

        if state[
            "status"
        ] == "complete":

            source_count += 1

        if state.get(
            "unresolved"
        ):

            unresolved_count += 1

    # ========================================================
    # Save
    # ========================================================

    output_path = (
        path.with_name(
            path.stem
            + "_nutrition_enriched.json"
        )
    )

    report_path = (
        path.with_name(
            path.stem
            + "_nutrition_report.json"
        )
    )

    save_json(
        output_path,
        final_recipes,
    )

    report = {
        "source_file":
            path.name,

        "recipe_count":
            len(
                recipes
            ),

        "source_nutrition_count":
            source_count,

        "recipes_needing_gemini":
            len(
                gemini_states
            ),

        "gemini_calls":
            gemini_calls,

        "gemini_batch_size":
            GEMINI_RECIPES_PER_BATCH,

        "recipes_still_unresolved":
            unresolved_count,

        "unresolved_recipes":
            [
                {
                    "id":
                        state[
                            "recipe_id"
                        ],

                    "title":
                        state[
                            "title"
                        ],

                    "ingredients":
                        state.get(
                            "unresolved",
                            [],
                        ),
                }

                for state in states

                if state.get(
                    "unresolved"
                )
            ],
    }

    save_json(
        report_path,
        report,
    )

    print(
        "\n================================"
    )

    print(
        "FILE COMPLETE"
    )

    print(
        "================================"
    )

    print(
        f"Recipes: "
        f"{len(recipes)}"
    )

    print(
        f"Source-book nutrition: "
        f"{source_count}"
    )

    print(
        f"Recipes needing Gemini: "
        f"{len(gemini_states)}"
    )

    print(
        f"Gemini calls used: "
        f"{gemini_calls}"
    )

    print(
        f"Still unresolved: "
        f"{unresolved_count}"
    )

    print(
        f"\nOutput:\n"
        f"{output_path}"
    )

    print(
        f"\nReport:\n"
        f"{report_path}"
    )

    return {
        "recipes":
            len(
                recipes
            ),

        "gemini_calls":
            gemini_calls,

        "unresolved":
            unresolved_count,
    }


# ============================================================
# Main
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "CHEFAI NUTRITION ENRICHMENT V2"
    )

    print(
        "========================================"
    )

    print(
        f"Gemini recipes per API call: "
        f"{GEMINI_RECIPES_PER_BATCH}"
    )

    NUTRITION_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache = load_cache()

    print(
        f"Cached Gemini estimates: "
        f"{len(cache['context_estimates'])}"
    )

    client = genai.Client(
        api_key=API_KEY
    )

    total_recipes = 0
    total_calls = 0
    total_unresolved = 0

    for filename in (
        INPUT_FILES
    ):

        path = (
            STRUCTURED_RECIPE_DIR
            / filename
        )

        if not path.exists():

            print(
                f"\nSkipping missing file: "
                f"{filename}"
            )

            continue

        summary = process_file(
            path,
            client,
            cache,
        )

        total_recipes += (
            summary[
                "recipes"
            ]
        )

        total_calls += (
            summary[
                "gemini_calls"
            ]
        )

        total_unresolved += (
            summary[
                "unresolved"
            ]
        )

    print(
        "\n========================================"
    )

    print(
        "OVERALL COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        f"Recipes processed: "
        f"{total_recipes}"
    )

    print(
        f"Gemini API calls used: "
        f"{total_calls}"
    )

    print(
        f"Recipes still unresolved: "
        f"{total_unresolved}"
    )

    print(
        f"\nCache:\n"
        f"{CACHE_PATH}"
    )


if __name__ == "__main__":
    main()