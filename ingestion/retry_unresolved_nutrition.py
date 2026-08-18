import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from ingestion.enrich_missing_nutrition_v2 import (
    estimate_batch_with_gemini,
    apply_gemini_response,
    apply_cached_estimates,
    finalize_recipe,
    load_cache,
    save_cache,
    save_json,
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


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "structured_recipes"
    / "italian_recipes_gemini_nutrition_enriched.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "structured_recipes"
    / "italian_recipes_gemini_nutrition_final.json"
)


BATCH_SIZE = 8

MAX_RETRIES = 3

RETRY_DELAY_SECONDS = 3


REQUIRED_NUTRITION_FIELDS = (
    "calories",
    "protein_g",
    "carbohydrates_g",
    "fat_g",
)


# ============================================================
# Helpers
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


def nutrition_complete(
    recipe: dict,
) -> bool:

    nutrition = recipe.get(
        "nutrition",
        {}
    )

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


def has_unresolved_ingredients(
    recipe: dict,
) -> bool:

    metadata = recipe.get(
        "nutrition_metadata",
        {}
    )

    if not isinstance(
        metadata,
        dict,
    ):
        return False

    unresolved = metadata.get(
        "still_unresolved",
        []
    )

    return bool(
        unresolved
    )


def build_retry_state(
    recipe: dict,
) -> dict:
    """
    Build a Gemini retry state directly from the existing
    enriched recipe.

    IMPORTANT:
    The recipe's current nutrition values already contain
    contributions from ingredients that were resolved locally.

    We therefore use those values as the starting totals and
    ask Gemini ONLY for ingredients listed in still_unresolved.
    """

    nutrition = recipe.get(
        "nutrition",
        {}
    )

    metadata = recipe.get(
        "nutrition_metadata",
        {}
    )

    unresolved = metadata.get(
        "still_unresolved",
        []
    )

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

    totals = {
        "calories":
            float(
                nutrition.get(
                    "calories",
                    0.0,
                )
                or 0.0
            ),

        "protein_g":
            float(
                nutrition.get(
                    "protein_g",
                    0.0,
                )
                or 0.0
            ),

        "carbohydrates_g":
            float(
                nutrition.get(
                    "carbohydrates_g",
                    0.0,
                )
                or 0.0
            ),

        "fat_g":
            float(
                nutrition.get(
                    "fat_g",
                    0.0,
                )
                or 0.0
            ),
    }

    return {
        "recipe":
            recipe,

        "recipe_id":
            recipe_id,

        "title":
            title,

        "status":
            "needs_gemini",

        "source":
            recipe.get(
                "nutrition_source",
                "calculated_local",
            ),

        # Existing totals from all successfully resolved
        # ingredients.
        "totals":
            totals,

        # ONLY ingredients that remain unresolved.
        "unresolved":
            list(
                unresolved
            ),

        "omitted":
            metadata.get(
                "omitted_ingredients",
                [],
            ),

        "local_coverage":
            metadata.get(
                "local_coverage",
                0.0,
            ),

        # Keep previous Gemini estimates if there were any.
        "gemini_estimates":
            list(
                metadata.get(
                    "gemini_estimated_ingredients",
                    [],
                )
            ),

        "cache_hits":
            list(
                metadata.get(
                    "cache_hits",
                    [],
                )
            ),
    }


# ============================================================
# Main
# ============================================================

def main():

    if not INPUT_PATH.exists():

        raise FileNotFoundError(
            f"Input file not found: "
            f"{INPUT_PATH}"
        )

    recipes = load_json(
        INPUT_PATH
    )

    if not isinstance(
        recipes,
        list,
    ):

        raise RuntimeError(
            "Input JSON is not a recipe list."
        )

    cache = load_cache()

    client = genai.Client(
        api_key=API_KEY
    )

    unresolved_states = []

    # ========================================================
    # Find ONLY recipes that still have unresolved ingredients
    # ========================================================

    for recipe in recipes:

        if not has_unresolved_ingredients(
            recipe
        ):
            continue

        state = build_retry_state(
            recipe
        )

        # ----------------------------------------------------
        # First check the persistent Gemini cache.
        #
        # Some of these ingredients may already have been
        # estimated in another run.
        # ----------------------------------------------------

        apply_cached_estimates(
            state,
            cache,
        )

        # Cache may completely solve the recipe.
        if not state[
            "unresolved"
        ]:

            state[
                "status"
            ] = "complete_local"

        unresolved_states.append(
            state
        )

    print(
        "\n================================"
    )

    print(
        "UNRESOLVED NUTRITION RETRY"
    )

    print(
        "================================"
    )

    print(
        f"Recipes requiring cleanup: "
        f"{len(unresolved_states)}"
    )

    if not unresolved_states:

        print(
            "Nothing to retry."
        )

        save_json(
            OUTPUT_PATH,
            recipes,
        )

        return

    # --------------------------------------------------------
    # Only states STILL requiring Gemini after cache lookup.
    # --------------------------------------------------------

    gemini_states = [
        state
        for state in unresolved_states

        if state[
            "unresolved"
        ]
    ]

    batches = [
        gemini_states[
            index:
            index + BATCH_SIZE
        ]

        for index in range(
            0,
            len(
                gemini_states
            ),
            BATCH_SIZE,
        )
    ]

    print(
        f"Recipes still requiring Gemini: "
        f"{len(gemini_states)}"
    )

    print(
        f"Retry batches: "
        f"{len(batches)}"
    )

    total_calls = 0

    # ========================================================
    # Retry Gemini batches
    # ========================================================

    for batch_index, batch in enumerate(
        batches,
        start=1,
    ):

        print(
            "\n--------------------------------"
        )

        print(
            f"RETRY BATCH "
            f"{batch_index}/"
            f"{len(batches)}"
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

        success = False

        # ----------------------------------------------------
        # Retry malformed JSON / temporary API failures.
        # ----------------------------------------------------

        for attempt in range(
            1,
            MAX_RETRIES + 1,
        ):

            try:

                print(
                    f"Attempt "
                    f"{attempt}/"
                    f"{MAX_RETRIES}"
                )

                response = (
                    estimate_batch_with_gemini(
                        client,
                        batch,
                    )
                )

                total_calls += 1

                apply_gemini_response(
                    batch,
                    response,
                    cache,
                )

                print(
                    "Retry batch successful."
                )

                success = True

                break

            except Exception as error:

                print(
                    f"Retry failed: "
                    f"{error}"
                )

                if (
                    attempt
                    < MAX_RETRIES
                ):

                    print(
                        "Trying again..."
                    )

                    time.sleep(
                        RETRY_DELAY_SECONDS
                    )

        if not success:

            print(
                "Batch failed after "
                "all retry attempts."
            )

    # ========================================================
    # Finalize cleaned recipes
    # ========================================================

    updated_by_id = {}

    for state in unresolved_states:

        updated_recipe = (
            finalize_recipe(
                state
            )
        )

        updated_by_id[
            str(
                state[
                    "recipe_id"
                ]
            )
        ] = updated_recipe

    # ========================================================
    # Merge updated recipes back into complete cookbook
    # ========================================================

    final_recipes = []

    for recipe in recipes:

        recipe_id = str(
            recipe.get(
                "id",
                "",
            )
        )

        if recipe_id in (
            updated_by_id
        ):

            final_recipes.append(
                updated_by_id[
                    recipe_id
                ]
            )

        else:

            final_recipes.append(
                recipe
            )

    # ========================================================
    # Save
    # ========================================================

    save_json(
        OUTPUT_PATH,
        final_recipes,
    )

    save_cache(
        cache
    )

    # ========================================================
    # REAL final validation
    #
    # We check BOTH:
    #
    # 1. nutrition numbers exist
    # 2. no unresolved ingredients remain
    # ========================================================

    missing_nutrition = [
        recipe
        for recipe in final_recipes

        if not nutrition_complete(
            recipe
        )
    ]

    still_unresolved = [
        recipe
        for recipe in final_recipes

        if has_unresolved_ingredients(
            recipe
        )
    ]

    print(
        "\n================================"
    )

    print(
        "RETRY COMPLETE"
    )

    print(
        "================================"
    )

    print(
        f"Gemini calls used: "
        f"{total_calls}"
    )

    print(
        f"Recipes missing nutrition: "
        f"{len(missing_nutrition)}"
    )

    print(
        f"Recipes still containing "
        f"unresolved ingredients: "
        f"{len(still_unresolved)}"
    )

    print(
        f"\nSaved final file:\n"
        f"{OUTPUT_PATH}"
    )

    if still_unresolved:

        print(
            "\nStill unresolved:"
        )

        for recipe in (
            still_unresolved
        ):

            unresolved = (
                recipe
                .get(
                    "nutrition_metadata",
                    {},
                )
                .get(
                    "still_unresolved",
                    [],
                )
            )

            print(
                f"\n- "
                f"{recipe.get('id')} "
                f"{recipe.get('title')}"
            )

            for ingredient in (
                unresolved
            ):

                print(
                    f"    ? {ingredient}"
                )


if __name__ == "__main__":
    main()