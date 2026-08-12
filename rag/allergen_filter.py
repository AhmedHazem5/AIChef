import re


# ============================================================
# Allergen → ingredient aliases
# ============================================================

ALLERGEN_ALIASES = {
    "peanuts": {
        "peanut",
        "peanuts",
        "peanut butter",
        "groundnut",
        "groundnuts",
    },

    "milk": {
        "milk",
        "butter",
        "cream",
        "cheese",
        "yogurt",
        "yoghurt",
        "whey",
        "casein",
        "ghee",
        "buttermilk",
        "milk powder",
    },

    "eggs": {
        "egg",
        "eggs",
        "egg white",
        "egg whites",
        "egg yolk",
        "egg yolks",
        "mayonnaise",
    },

    "soy": {
        "soy",
        "soya",
        "soybean",
        "soybeans",
        "soy sauce",
        "tofu",
        "tempeh",
        "edamame",
        "miso",
    },

    "wheat": {
        "wheat",
        "wheat flour",
        "flour",
        "bread flour",
        "all purpose flour",
        "all-purpose flour",
        "breadcrumbs",
        "bread crumbs",
        "semolina",
        "couscous",
        "pasta",
    },

    "gluten": {
        "gluten",
        "wheat",
        "barley",
        "rye",
        "malt",
        "wheat flour",
        "bread flour",
        "semolina",
        "couscous",
        "pasta",
    },

    "tree_nuts": {
        "almond",
        "almonds",
        "cashew",
        "cashews",
        "walnut",
        "walnuts",
        "pecan",
        "pecans",
        "pistachio",
        "pistachios",
        "hazelnut",
        "hazelnuts",
        "macadamia",
        "macadamias",
    },

    "fish": {
        "fish",
        "salmon",
        "tuna",
        "cod",
        "haddock",
        "anchovy",
        "anchovies",
        "sardine",
        "sardines",
        "trout",
        "tilapia",
    },

    "shellfish": {
        "shellfish",
        "shrimp",
        "prawn",
        "prawns",
        "crab",
        "lobster",
        "crayfish",
        "mussel",
        "mussels",
        "clam",
        "clams",
        "oyster",
        "oysters",
        "scallop",
        "scallops",
    },

    "sesame": {
        "sesame",
        "sesame seed",
        "sesame seeds",
        "sesame oil",
        "tahini",
    },
}


USER_ALLERGY_ALIASES = {
    "peanut": {"peanuts"},
    "peanuts": {"peanuts"},

    "milk": {"milk"},
    "dairy": {"milk"},
    "lactose": {"milk"},

    "egg": {"eggs"},
    "eggs": {"eggs"},

    "soy": {"soy"},
    "soya": {"soy"},

    "wheat": {"wheat"},
    "gluten": {"gluten"},

    "tree nut": {"tree_nuts"},
    "tree nuts": {"tree_nuts"},

    # Conservative interpretation.
    "nut": {"peanuts", "tree_nuts"},
    "nuts": {"peanuts", "tree_nuts"},

    "fish": {"fish"},

    "shellfish": {"shellfish"},

    "seafood": {
        "fish",
        "shellfish",
    },

    "sesame": {"sesame"},
}


def normalize_text(
    text: str,
) -> str:

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s\-]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def contains_term(
    text: str,
    term: str,
) -> bool:

    normalized_text = (
        normalize_text(text)
    )

    normalized_term = (
        normalize_text(term)
    )

    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(normalized_term)
        + r"(?![a-z0-9])"
    )

    return bool(
        re.search(
            pattern,
            normalized_text,
        )
    )


def detect_allergens(
    text: str,
) -> set[str]:

    detected = set()

    for (
        allergen,
        aliases,
    ) in ALLERGEN_ALIASES.items():

        for alias in aliases:

            if contains_term(
                text,
                alias,
            ):
                detected.add(
                    allergen
                )
                break

    return detected


def normalize_user_allergies(
    allergies: list[str],
) -> tuple[set[str], list[str]]:

    supported = set()
    unsupported = []

    for allergy in allergies:

        if not isinstance(
            allergy,
            str,
        ):
            continue

        normalized = normalize_text(
            allergy
        )

        mapped = (
            USER_ALLERGY_ALIASES
            .get(normalized)
        )

        if mapped:
            supported.update(
                mapped
            )

        elif (
            normalized
            in ALLERGEN_ALIASES
        ):
            supported.add(
                normalized
            )

        elif normalized:
            unsupported.append(
                allergy.strip()
            )

    return (
        supported,
        unsupported,
    )


def find_conflicts(
    text: str,
    user_allergens: set[str],
) -> set[str]:

    detected = detect_allergens(
        text
    )

    return (
        detected
        & user_allergens
    )