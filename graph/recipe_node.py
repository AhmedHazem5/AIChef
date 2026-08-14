from memory.cooking_session import (
    get_current_recipe,
    get_current_step,
    start_recipe,
)

from memory.memory_manager import (
    load_memory,
)

from memory.recommendation_context import (
    clear_pending_recipe,
    get_pending_recipe,
    set_pending_recipe,
)

from rag.allergen_filter import (
    find_conflicts,
    normalize_user_allergies,
)

from rag.dietary_filter import (
    find_dietary_conflicts,
)

from rag.structured_query_engine import (
    NoSafeRecipeError,
    SpecificRecipeAllergyError,
    SpecificRecipeDietaryError,
    UnsupportedAllergyError,
    retrieve_structured_recipe,
    structured_database_is_empty,
)

from routing.followup_classifier import (
    is_similar_recipe_followup,
)


MAX_RECIPE_ATTEMPTS = 4


def build_safe_alternative_query(
    pending_recipe: dict,
    dietary_preferences: list[str],
) -> str:
    """
    Build a safer alternative search query that preserves the
    general meal style without repeating a blocked ingredient.

    Example:
        saved preference: halal
        blocked category: Pork

        -> "savory main dish with chicken beef lamb or tofu"
    """

    title = (
        pending_recipe.get(
            "title",
            "",
        )
        or ""
    )

    cuisine = (
        pending_recipe.get(
            "cuisine",
            "",
        )
        or ""
    )

    category = (
        pending_recipe.get(
            "category",
            "",
        )
        or ""
    )

    ingredients = (
        pending_recipe.get(
            "ingredients",
            [],
        )
        or []
    )

    preferences = {
        item.lower().strip()
        for item in dietary_preferences
        if isinstance(item, str)
    }

    category_lower = category.lower()

    # --------------------------------------------------------
    # Halal alternatives
    # --------------------------------------------------------

    if (
        "halal" in preferences
        and category_lower == "pork"
    ):

        parts = []

        if cuisine:
            parts.append(
                cuisine
            )

        parts.append(
            "savory main dish with "
            "chicken beef lamb or tofu"
        )

        return " ".join(
            parts
        )

    # --------------------------------------------------------
    # Vegetarian alternatives
    # --------------------------------------------------------

    if "vegetarian" in preferences:

        parts = []

        if cuisine:
            parts.append(
                cuisine
            )

        parts.append(
            "vegetarian main dish with "
            "tofu vegetables mushrooms or noodles"
        )

        return " ".join(
            parts
        )

    # --------------------------------------------------------
    # Vegan alternatives
    # --------------------------------------------------------

    if "vegan" in preferences:

        parts = []

        if cuisine:
            parts.append(
                cuisine
            )

        parts.append(
            "vegan main dish with tofu vegetables "
            "mushrooms rice or noodles"
        )

        return " ".join(
            parts
        )

    # --------------------------------------------------------
    # Generic safe alternative
    # --------------------------------------------------------

    meaningful_parts = []

    if cuisine:
        meaningful_parts.append(
            cuisine
        )

    if category:
        meaningful_parts.append(
            category
        )

    meaningful_parts.extend(
        str(item)
        for item in ingredients[:3]
        if str(item).strip()
    )

    if meaningful_parts:

        return (
            "safe alternative recipe similar to "
            + " ".join(
                meaningful_parts
            )
        )

    return (
        "safe alternative recipe similar to "
        + title
    )


def recipe_node(state):

    memory = load_memory()

    allergies = memory.get(
        "allergies",
        [],
    )

    dietary_preferences = memory.get(
        "dietary_preferences",
        [],
    )

    (
        normalized_allergies,
        unsupported,
    ) = normalize_user_allergies(
        allergies
    )

    if unsupported:

        return {
            "answer": (
                "I cannot safely verify recipes "
                "for all of your saved allergies."
            ),
            "memory": memory,
        }

    user_message = state[
        "user_message"
    ]

    excluded_recipe_ids = set()

    # ========================================================
    # Is this a follow-up to a blocked recipe?
    # ========================================================

    pending_recipe = (
        get_pending_recipe()
    )

    alternative_mode = False
    alternative_search_query = None

    if pending_recipe:

        if is_similar_recipe_followup(
            user_message,
            pending_recipe,
        ):

            alternative_mode = True

            blocked_id = (
                pending_recipe.get(
                    "id"
                )
            )

            if blocked_id:

                excluded_recipe_ids.add(
                    blocked_id
                )

            title = pending_recipe.get(
                "title",
                "",
            )

            cuisine = pending_recipe.get(
                "cuisine",
                "",
            )

            # Build a dietary-safe alternative query.
            #
            # Important:
            # If a halal user asked for pork, do NOT search
            # primarily for "pork recipe" again. Search for a
            # comparable safe main dish instead.
            alternative_search_query = (
                build_safe_alternative_query(
                    pending_recipe,
                    dietary_preferences,
                )
            )

            print(
                "\nSimilar-safe-recipe "
                "follow-up detected."
            )

            print(
                f"Original blocked recipe: "
                f"{title}"
            )

            print(
                f"Alternative search query: "
                f"{alternative_search_query}"
            )

        else:

            # User moved on to another topic/request.
            clear_pending_recipe()

    # ========================================================
    # Retrieve recipe
    # ========================================================

    for attempt in range(
        1,
        MAX_RECIPE_ATTEMPTS + 1,
    ):

        print(
            "\n================================"
        )

        print(
            f"STRUCTURED RECIPE ATTEMPT "
            f"{attempt}/{MAX_RECIPE_ATTEMPTS}"
        )

        print(
            "================================"
        )

        try:

            result = retrieve_structured_recipe(
                query=user_message,
                allergies=allergies,
                dietary_preferences=
                    dietary_preferences,
                excluded_recipe_ids=
                    excluded_recipe_ids,

                # When looking for an alternative,
                # DON'T interpret the old recipe name
                # as another exact request.
                allow_specific_match=(
                    not alternative_mode
                ),

                search_query_override=(
                    alternative_search_query
                ),
            )

        except SpecificRecipeAllergyError as error:

            set_pending_recipe(
                error.recipe
            )

            conflicts = ", ".join(
                sorted(
                    error.conflicts
                )
            )

            return {
                "answer": (
                    f"{error.title} conflicts "
                    f"with your saved {conflicts} "
                    "allergy, so I won't recommend "
                    "that recipe. Would you like "
                    "me to suggest a similar safe "
                    "recipe instead?"
                ),
                "memory": memory,
            }

        except SpecificRecipeDietaryError as error:

            set_pending_recipe(
                error.recipe
            )

            preferences = ", ".join(
                sorted(
                    error.conflicts
                )
            )

            return {
                "answer": (
                    f"{error.title} does not match "
                    f"your saved {preferences} "
                    "dietary preference, so I won't "
                    "recommend that recipe. "
                    "Would you like a similar safe "
                    "recipe instead?"
                ),
                "memory": memory,
            }

        except UnsupportedAllergyError as error:

            return {
                "answer": str(error),
                "memory": memory,
            }

        except NoSafeRecipeError as error:

            clear_pending_recipe()

            return {
                "answer": str(error),
                "memory": memory,
            }

        if not result:

            if structured_database_is_empty():

                return {
                    "answer": (
                        "My structured recipe "
                        "database is currently empty."
                    ),
                    "memory": memory,
                }

            break

        recipe_id = result[
            "recipe_id"
        ]

        recipe = result[
            "recipe"
        ]

        specific_request = result.get(
            "specific_request",
            False,
        )

        excluded_recipe_ids.add(
            recipe_id
        )

        title = recipe.get(
            "title",
            "Recipe",
        )

        ingredients = recipe.get(
            "ingredients",
            [],
        )

        steps = recipe.get(
            "steps",
            [],
        )

        servings = recipe.get(
            "servings",
            "",
        )

        nutrition = recipe.get(
            "nutrition",
            {},
        )

        calories = nutrition.get(
            "calories"
        )

        protein = nutrition.get(
            "protein_g"
        )

        carbohydrates = nutrition.get(
            "carbohydrates_g"
        )

        fat = nutrition.get(
            "fat_g"
        )

        if (
            not ingredients
            or not steps
        ):

            if specific_request:

                return {
                    "answer": (
                        f"I found {title}, but its "
                        "recipe data is incomplete."
                    ),
                    "memory": memory,
                }

            continue

        # ====================================================
        # Final allergy validation
        # ====================================================

        conflicts = find_conflicts(
            " ".join(ingredients),
            normalized_allergies,
        )

        if conflicts:

            if specific_request:

                set_pending_recipe(
                    recipe
                )

                conflict_text = ", ".join(
                    sorted(conflicts)
                )

                return {
                    "answer": (
                        f"{title} conflicts with "
                        f"your saved {conflict_text} "
                        "allergy. Would you like "
                        "a similar safe recipe?"
                    ),
                    "memory": memory,
                }

            continue

        # ====================================================
        # Final dietary preference validation
        #
        # This is a second safety check after retrieval.
        # ====================================================

        dietary_text_parts = (
            list(ingredients)
            + list(steps)
            + [
                title,
                recipe.get(
                    "category",
                    "",
                ),
            ]
        )

        dietary_conflicts = (
            find_dietary_conflicts(
                dietary_text_parts,
                dietary_preferences,
            )
        )

        if dietary_conflicts:

            dietary_text = ", ".join(
                sorted(
                    dietary_conflicts
                )
            )

            if specific_request:

                set_pending_recipe(
                    recipe
                )

                return {
                    "answer": (
                        f"{title} does not match "
                        f"your saved {dietary_text} "
                        "dietary preference. "
                        "Would you like a similar "
                        "safe recipe instead?"
                    ),
                    "memory": memory,
                }

            continue

        # ====================================================
        # Safe recipe found
        # ====================================================

        clear_pending_recipe()

        print(
            "\nSAFE STRUCTURED RECIPE FOUND!"
        )

        start_recipe(
            title=title,
            ingredients=ingredients,
            steps=steps,
            servings=servings,
            nutrition=nutrition,
        )

        print(
            "\nRecipe session created:"
        )

        print(
            get_current_recipe()
        )

        first_step = get_current_step()

        if not first_step:
            continue

        ingredients_text = (
            "\n\nIngredients:\n- "
            + "\n- ".join(
                ingredients
            )
        )

        servings_text = ""

        if servings:

            servings_text = (
                f"\nServings: {servings}"
            )

        nutrition_lines = []

        if calories is not None:

            nutrition_lines.append(
                f"Calories: {calories}"
            )

        if protein is not None:

            nutrition_lines.append(
                f"Protein: {protein} g"
            )

        if carbohydrates is not None:

            nutrition_lines.append(
                f"Carbohydrates: "
                f"{carbohydrates} g"
            )

        if fat is not None:

            nutrition_lines.append(
                f"Fat: {fat} g"
            )

        nutrition_text = ""

        if nutrition_lines:

            nutrition_text = (
                "\n\nNutrition:\n"
                + "\n".join(
                    nutrition_lines
                )
            )

        intro = (
            "Here's a similar safe option. "
            if alternative_mode
            else ""
        )

        answer = (
            f"{intro}"
            f"Let's make {title}."
            f"{servings_text}"
            f"{ingredients_text}"
            f"{nutrition_text}"
            f"\n\nStep 1:\n"
            f"{first_step}"
            "\n\nSay \"next\" "
            "when you're ready."
        )

        return {
            "answer": answer,
            "memory": memory,
        }

    clear_pending_recipe()

    return {
        "answer": (
            "I couldn't find a safe recipe "
            "that matches your request."
        ),
        "memory": memory,
    }