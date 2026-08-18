from typing import Any


def _clean_string(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(
        value
    ).strip()


def _clean_string_list(
    value: Any,
) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        return []

    cleaned = []

    for item in value:
        text = _clean_string(
            item
        )

        if text:
            cleaned.append(
                text
            )

    return cleaned


def _clean_page_list(
    value: Any,
) -> list[int]:
    if not isinstance(
        value,
        list,
    ):
        return []

    pages = []

    for item in value:
        try:
            page = int(
                item
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if page > 0:
            pages.append(
                page
            )

    return sorted(
        set(
            pages
        )
    )


def validate_recipe(
    recipe: dict,
) -> tuple[
    bool,
    dict,
    list[str],
]:
    """
    Validate one LLM-extracted recipe.

    Returns:
        valid
        cleaned recipe
        list of problems
    """

    problems = []

    title = _clean_string(
        recipe.get(
            "title"
        )
    )

    cuisine = _clean_string(
        recipe.get(
            "cuisine"
        )
    )

    category = _clean_string(
        recipe.get(
            "category"
        )
    )

    servings = _clean_string(
        recipe.get(
            "servings"
        )
    )

    ingredients = (
        _clean_string_list(
            recipe.get(
                "ingredients"
            )
        )
    )

    steps = (
        _clean_string_list(
            recipe.get(
                "steps"
            )
        )
    )

    source_pages = (
        _clean_page_list(
            recipe.get(
                "source_pages"
            )
        )
    )

    complete = bool(
        recipe.get(
            "complete",
            False,
        )
    )

    # ========================================================
    # Required completeness checks
    # ========================================================

    if not title:
        problems.append(
            "Missing title."
        )

    if not cuisine:
        problems.append(
            "Missing cuisine."
        )

    if not ingredients:
        problems.append(
            "No ingredients."
        )

    if not steps:
        problems.append(
            "No cooking steps."
        )

    if not source_pages:
        problems.append(
            "No source page information."
        )

    if not complete:
        problems.append(
            "LLM marked recipe incomplete."
        )

    # ========================================================
    # Suspiciously small recipes
    #
    # Do NOT automatically reject one-step recipes because
    # some legitimate simple recipes really are short.
    # We flag them for the audit report instead.
    # ========================================================

    if (
        len(ingredients) == 1
        and len(steps) == 1
    ):
        problems.append(
            "Recipe contains only one ingredient "
            "and one step; manual review required."
        )

    cleaned = {
        "title":
            title,

        "cuisine":
            cuisine,

        "category":
            category,

        "servings":
            servings,

        "ingredients":
            ingredients,

        "steps":
            steps,

        "source_pages":
            source_pages,

        "complete":
            complete,
    }

    valid = (
        len(problems)
        == 0
    )

    return (
        valid,
        cleaned,
        problems,
    )


def validate_recipes(
    recipes: list[dict],
):
    """
    Validate an entire list of extracted recipes.
    """

    valid_recipes = []

    rejected = []

    for recipe in recipes:
        (
            valid,
            cleaned,
            problems,
        ) = validate_recipe(
            recipe
        )

        if valid:
            valid_recipes.append(
                cleaned
            )

        else:
            rejected.append(
                {
                    "recipe":
                        cleaned,

                    "problems":
                        problems,
                }
            )

    return (
        valid_recipes,
        rejected,
    )