import re


DIETARY_BLOCKED_TERMS = {

    "halal": {
        "pork",
        "ham",
        "bacon",
        "prosciutto",
        "pancetta",
        "lard",
        "pork belly",
        "pork chop",
        "pork chops",
        "pork loin",
        "pork tenderloin",
        "spareribs",
        "spare ribs",

        # Alcoholic cooking ingredients
        "wine",
        "rice wine",
        "sherry",
        "mirin",
        "sake",
        "beer",
        "brandy",
        "rum",
    },

    "vegetarian": {
        "beef",
        "steak",
        "chicken",
        "turkey",
        "duck",
        "pork",
        "ham",
        "bacon",
        "lamb",
        "fish",
        "salmon",
        "tuna",
        "cod",
        "halibut",
        "trout",
        "shrimp",
        "prawn",
        "crab",
        "lobster",
        "oyster",
        "scallop",
        "clam",
        "chicken stock",
        "beef stock",
        "fish stock",
    },

    "vegan": {
        "beef",
        "steak",
        "chicken",
        "turkey",
        "duck",
        "pork",
        "ham",
        "bacon",
        "lamb",
        "fish",
        "salmon",
        "tuna",
        "cod",
        "halibut",
        "trout",
        "shrimp",
        "prawn",
        "crab",
        "lobster",
        "oyster",
        "scallop",
        "clam",

        "egg",
        "eggs",
        "milk",
        "butter",
        "cream",
        "cheese",
        "yogurt",
        "yoghurt",
        "ghee",
        "honey",

        "chicken stock",
        "beef stock",
        "fish stock",
    },
}


def normalize_text(
    text: str,
) -> str:

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\\s\\-]",
        " ",
        text,
    )

    text = re.sub(
        r"\\s+",
        " ",
        text,
    )

    return text.strip()


def contains_term(
    text: str,
    term: str,
) -> bool:

    normalized_text = normalize_text(
        text
    )

    normalized_term = normalize_text(
        term
    )

    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(
            normalized_term
        )
        + r"(?![a-z0-9])"
    )

    return bool(
        re.search(
            pattern,
            normalized_text,
        )
    )


def find_dietary_conflicts(
    ingredients: list[str],
    dietary_preferences: list[str],
) -> set[str]:

    ingredient_text = " ".join(
        ingredients
    )

    conflicts = set()

    for preference in dietary_preferences:

        if not isinstance(
            preference,
            str,
        ):
            continue

        preference = (
            preference
            .lower()
            .strip()
        )

        blocked_terms = (
            DIETARY_BLOCKED_TERMS
            .get(preference)
        )

        if not blocked_terms:
            continue

        for term in blocked_terms:

            if contains_term(
                ingredient_text,
                term,
            ):

                conflicts.add(
                    preference
                )

                break

    return conflicts