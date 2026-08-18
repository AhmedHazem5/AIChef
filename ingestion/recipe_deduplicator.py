import re
from difflib import SequenceMatcher


def normalize_text(
    text: str,
) -> str:
    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def title_similarity(
    recipe_a: dict,
    recipe_b: dict,
) -> float:
    a = normalize_text(
        recipe_a.get(
            "title",
            "",
        )
    )

    b = normalize_text(
        recipe_b.get(
            "title",
            "",
        )
    )

    if not a or not b:
        return 0.0

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


def _token_set(
    values: list[str],
) -> set[str]:
    text = " ".join(
        values
    )

    normalized = (
        normalize_text(
            text
        )
    )

    return set(
        normalized.split()
    )


def ingredient_similarity(
    recipe_a: dict,
    recipe_b: dict,
) -> float:
    a = _token_set(
        recipe_a.get(
            "ingredients",
            [],
        )
    )

    b = _token_set(
        recipe_b.get(
            "ingredients",
            [],
        )
    )

    if not a or not b:
        return 0.0

    return (
        len(
            a.intersection(
                b
            )
        )
        /
        len(
            a.union(
                b
            )
        )
    )


def step_similarity(
    recipe_a: dict,
    recipe_b: dict,
) -> float:
    a = normalize_text(
        " ".join(
            recipe_a.get(
                "steps",
                [],
            )
        )
    )

    b = normalize_text(
        " ".join(
            recipe_b.get(
                "steps",
                [],
            )
        )
    )

    if not a or not b:
        return 0.0

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


def duplicate_score(
    recipe_a: dict,
    recipe_b: dict,
) -> float:
    title = title_similarity(
        recipe_a,
        recipe_b,
    )

    ingredients = (
        ingredient_similarity(
            recipe_a,
            recipe_b,
        )
    )

    steps = step_similarity(
        recipe_a,
        recipe_b,
    )

    return (
        0.50 * title
        + 0.30 * ingredients
        + 0.20 * steps
    )


def recipe_completeness_score(
    recipe: dict,
) -> float:
    """
    Used only to decide which duplicate copy is more complete.
    """

    score = 0.0

    score += (
        len(
            recipe.get(
                "ingredients",
                [],
            )
        )
        * 1.0
    )

    score += (
        len(
            recipe.get(
                "steps",
                [],
            )
        )
        * 1.5
    )

    if recipe.get(
        "servings"
    ):
        score += 1.0

    if recipe.get(
        "category"
    ):
        score += 0.5

    return score


def merge_duplicate_metadata(
    keeper: dict,
    duplicate: dict,
) -> dict:
    """
    Do NOT merge recipe content blindly.

    We keep the more complete recipe body and only merge safe
    metadata such as source page numbers and missing servings/category.
    """

    merged = dict(
        keeper
    )

    pages = set(
        keeper.get(
            "source_pages",
            [],
        )
    )

    pages.update(
        duplicate.get(
            "source_pages",
            [],
        )
    )

    merged[
        "source_pages"
    ] = sorted(
        pages
    )

    if (
        not merged.get(
            "servings"
        )
        and duplicate.get(
            "servings"
        )
    ):
        merged[
            "servings"
        ] = duplicate[
            "servings"
        ]

    if (
        not merged.get(
            "category"
        )
        and duplicate.get(
            "category"
        )
    ):
        merged[
            "category"
        ] = duplicate[
            "category"
        ]

    return merged


def deduplicate_recipes(
    recipes: list[dict],
    threshold: float = 0.86,
):
    """
    Remove duplicate recipes created by overlapping page windows.

    Returns:
        deduplicated recipes
        duplicate audit records
    """

    deduplicated = []

    duplicates_report = []

    for candidate in recipes:

        duplicate_index = None
        best_duplicate_score = 0.0

        for index, existing in enumerate(
            deduplicated
        ):

            title_score = (
                title_similarity(
                    candidate,
                    existing,
                )
            )

            overall_score = (
                duplicate_score(
                    candidate,
                    existing,
                )
            )

            # Very similar titles OR strong overall similarity.
            is_duplicate = (
                title_score >= 0.94
                or overall_score >= threshold
            )

            if (
                is_duplicate
                and overall_score
                > best_duplicate_score
            ):
                duplicate_index = (
                    index
                )

                best_duplicate_score = (
                    overall_score
                )

        if duplicate_index is None:
            deduplicated.append(
                candidate
            )

            continue

        existing = (
            deduplicated[
                duplicate_index
            ]
        )

        existing_score = (
            recipe_completeness_score(
                existing
            )
        )

        candidate_score = (
            recipe_completeness_score(
                candidate
            )
        )

        if (
            candidate_score
            > existing_score
        ):
            keeper = candidate
            removed = existing

        else:
            keeper = existing
            removed = candidate

        keeper = (
            merge_duplicate_metadata(
                keeper,
                removed,
            )
        )

        deduplicated[
            duplicate_index
        ] = keeper

        duplicates_report.append(
            {
                "kept_title":
                    keeper.get(
                        "title"
                    ),

                "removed_title":
                    removed.get(
                        "title"
                    ),

                "similarity":
                    round(
                        best_duplicate_score,
                        4,
                    ),

                "kept_pages":
                    keeper.get(
                        "source_pages",
                        [],
                    ),

                "removed_pages":
                    removed.get(
                        "source_pages",
                        [],
                    ),
            }
        )

    return (
        deduplicated,
        duplicates_report,
    )