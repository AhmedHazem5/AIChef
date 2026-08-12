import json
import re
from pathlib import Path

from pypdf import PdfReader


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHINESE_PDF = (
    PROJECT_ROOT
    / "data"
    / "recipes"
    / "Chinese"
    / "chinese.pdf"
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "structured_recipes"
)

OUTPUT_FILE = (
    OUTPUT_DIRECTORY
    / "chinese_recipes.json"
)


# ============================================================
# Expected recipe count
#
# The cover says 160 recipes, but the actual numbered
# category lists contain 162 unique recipe entries.
# We therefore use the actual content count.
# ============================================================

EXPECTED_RECIPE_COUNT = 162


# ============================================================
# Categories
# ============================================================

CATEGORY_NAMES = {
    "APPETIZERS",
    "BEEF",
    "CHICKEN",
    "CRAB",
    "DESSERTS",
    "EGG",
    "FISH",
    "LAMB",
    "NOODLES",
    "PORK",
    "RICE",
    "SHRIMP",
    "SOUP",
    "TOFU",
    "VEGETABLE",
}


# ============================================================
# Known source-title corrections
#
# These are obvious spelling/OCR errors in the cookbook.
# We are NOT creatively rewriting recipe names.
# ============================================================

TITLE_FIXES = {
    "Fried Crab in Balck Bean Sauce":
        "Fried Crab in Black Bean Sauce",

    "Szechwan Shrinp":
        "Szechwan Shrimp",

    "Pork with Baby corn":
        "Pork with Baby Corn",

    "Five-Treasure Stir fried Vegetable with Meat":
        "Five-Treasure Stir-fried Vegetable with Meat",
}


# ============================================================
# Text cleaning
# ============================================================

def clean_text(
    text: str,
) -> str:

    if not text:
        return ""

    text = text.replace(
        "\r\n",
        "\n",
    )

    text = text.replace(
        "\r",
        "\n",
    )

    text = text.replace(
        "\t",
        " ",
    )

    cleaned_lines = []

    for line in text.splitlines():

        line = re.sub(
            r"[ ]+",
            " ",
            line,
        ).strip()

        cleaned_lines.append(
            line
        )

    return "\n".join(
        cleaned_lines
    )


# ============================================================
# Load PDF
# ============================================================

def load_pdf_pages(
    pdf_path: Path,
) -> list[dict]:

    print(
        f"Reading {pdf_path.name}..."
    )

    reader = PdfReader(
        str(pdf_path)
    )

    pages = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):

        try:

            page_text = (
                page.extract_text()
                or ""
            )

        except Exception as error:

            print(
                f"Warning: page "
                f"{page_number} failed: "
                f"{error}"
            )

            continue

        pages.append(
            {
                "page_number":
                    page_number,

                "text":
                    clean_text(
                        page_text
                    ),
            }
        )

    print(
        f"Pages read: "
        f"{len(pages)}"
    )

    return pages


# ============================================================
# Flatten pages
#
# This is important because many recipes cross PDF page
# boundaries.
# ============================================================

def flatten_pages(
    pages: list[dict],
) -> list[dict]:

    records = []

    for page in pages:

        page_number = page[
            "page_number"
        ]

        for line in page[
            "text"
        ].splitlines():

            records.append(
                {
                    "text":
                        line.strip(),

                    "page":
                        page_number,
                }
            )

    return records


# ============================================================
# Numbered recipe marker
# ============================================================

def parse_numbered_marker(
    line: str,
):

    match = re.fullmatch(
        r"\[(\d+)\]\s*(.*)",
        line.strip(),
    )

    if not match:
        return None

    return {
        "number":
            int(
                match.group(1)
            ),

        "inline_title":
            match.group(2).strip(),
    }


# ============================================================
# Title normalization
# ============================================================

def normalize_title(
    title: str,
) -> str:

    title = re.sub(
        r"\s+",
        " ",
        title,
    ).strip()

    if title in TITLE_FIXES:

        return TITLE_FIXES[
            title
        ]

    return title


# ============================================================
# Ingredient detection
# ============================================================

def looks_like_ingredient_line(
    line: str,
) -> bool:

    line = line.strip()

    if not line:
        return False

    lowered = line.lower()

    # ========================================================
    # Reject obvious cooking-time / instruction fragments
    # BEFORE checking numeric ingredient patterns.
    #
    # Examples:
    #
    # 10 minutes.
    # 2 minutes.
    # 30 seconds.
    # 1 hour.
    # 2 hours.
    # ========================================================

    time_only_patterns = (
        r"^\d+(?:\.\d+)?\s+seconds?\.?$",
        r"^\d+(?:\.\d+)?\s+minutes?\.?$",
        r"^\d+(?:\.\d+)?\s+hours?\.?$",
        r"^\d+(?:\.\d+)?\s+mins?\.?$",
        r"^\d+(?:\.\d+)?\s+hrs?\.?$",
    )

    for pattern in time_only_patterns:

        if re.fullmatch(
            pattern,
            lowered,
        ):
            return False

    # ========================================================
    # Reject temperature-only fragments
    # ========================================================

    if re.fullmatch(
        r"\d+\s*°?\s*[fc]\.?",
        lowered,
    ):
        return False

    # ========================================================
    # Numeric ingredient formats
    #
    # Examples:
    #
    # 2 lbs chicken
    # 1/2 cup sugar
    # 1 1/2 tsps oil
    # 3 eggs
    # ========================================================

    numeric_patterns = (
        r"^\d+\s+\d+/\d+\s+",
        r"^\d+/\d+\s+",
        r"^\d+(?:\.\d+)?\s+",
        r"^\d+\s*\(",
    )

    for pattern in numeric_patterns:

        if re.match(
            pattern,
            line,
        ):
            return True

    # ========================================================
    # Non-numeric ingredients
    # ========================================================

    ingredient_terms = (
        "cooking oil",
        "oil for",
        "shortening",
        "salt",
        "pepper",
        "salad greens",
        "whipped cream",
        "parsley",
        "cilantro",
        "water",
        "broth",
        "stock",
        "soy sauce",
        "oyster sauce",
        "hoisin sauce",
        "vinegar",
        "cornstarch",
        "flour",
        "sugar",
        "sesame seeds",
        "sesame oil",
    )

    if any(
        lowered == term
        or lowered.startswith(
            term + " "
        )
        for term in ingredient_terms
    ):
        return True

    return False

# ============================================================
# Ingredient subsection headings
# ============================================================

def is_ingredient_section_heading(
    line: str,
) -> bool:

    line = line.strip()

    lowered = line.lower()

    # Most subsection headings end with ":".
    if (
        line.endswith(":")
        and len(line) <= 40
    ):
        return True

    known_headings = {
        "spring roll skins",
        "spring roll filling",
        "spring rolls",
        "marinade",
        "marinade sauce",
        "barbecue sauce",
        "cooking sauce",
        "sauce",
        "dressing",
        "filling",
        "batter",
        "plum sauce",
        "sweet and sour sauce",
        "garnish",
    }

    return lowered in known_headings


# ============================================================
# Cooking instruction detection
# ============================================================

INSTRUCTION_STARTS = (
    "add ",
    "allow ",
    "arrange ",
    "bake ",
    "baste ",
    "beat ",
    "blanch ",
    "blend ",
    "boil",
    "bring ",
    "brush ",
    "carve ",
    "chill ",
    "chop ",
    "coat ",
    "combine ",
    "cook ",
    "cover ",
    "cut ",
    "deep-fry ",
    "dip ",
    "discard ",
    "drain ",
    "dry ",
    "fill ",
    "finely ",
    "fold ",
    "fry ",
    "garnish ",
    "halve ",
    "heat ",
    "increase ",
    "lay ",
    "let ",
    "lower ",
    "marinate ",
    "marinade ",
    "mash ",
    "mix ",
    "pat ",
    "peel ",
    "place ",
    "pour ",
    "prepare ",
    "preheat ",
    "pull ",
    "put ",
    "reduce ",
    "refrigerate ",
    "reheat ",
    "remove ",
    "repeat ",
    "reserve ",
    "return ",
    "rinse ",
    "roll ",
    "season ",
    "serve ",
    "set ",
    "sieve ",
    "skim ",
    "slice ",
    "soak ",
    "spoon ",
    "sprinkle ",
    "squeeze ",
    "stack ",
    "stir ",
    "stir-fry ",
    "steam ",
    "transfer ",
    "trim ",
    "turn ",
    "toss ",
    "wash ",
    "when ",
    "while ",
    "wrap ",
)


def looks_like_instruction_line(
    line: str,
) -> bool:

    line = line.strip()

    if not line:
        return False

    lowered = line.lower()

    if any(
        lowered.startswith(
            start
        )
        for start in INSTRUCTION_STARTS
    ):
        return True

    # Common cookbook instruction phrases.
    instruction_phrases = (
        "to make ",
        "for batter",
        "for sauce",
        "for a whole chicken",
        "for chicken pieces",
        "each guest ",
        "over high heat",
        "over medium heat",
    )

    if any(
        lowered.startswith(
            phrase
        )
        for phrase in instruction_phrases
    ):
        return True

    return False


# ============================================================
# Serving statements
# ============================================================

def extract_servings_from_text(
    text: str,
) -> str:

    patterns = (
        # Makes 4 servings.
        # Makes about 6 servings.
        # Make 4 servings.
        r"\bMakes?\s+"
        r"((?:about\s+)?\d+(?:-\d+)?)"
        r"\s+servings?\b",

        # Serves 4.
        r"\bServes\s+"
        r"(\d+(?:-\d+)?)\b",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            return (
                match.group(1)
                .strip()
            )

    return ""


def is_serving_only_line(
    line: str,
) -> bool:

    return bool(
        re.match(
            r"^\s*"
            r"(?:Makes?|Serves)"
            r"\b",
            line,
            flags=re.IGNORECASE,
        )
    )


# ============================================================
# Ignore cookbook notes as cooking steps
# ============================================================

def is_note_line(
    line: str,
) -> bool:

    lowered = (
        line.strip()
        .lower()
    )

    return (
        lowered.startswith(
            "note:"
        )
        or lowered.startswith(
            "notes:"
        )
    )


# ============================================================
# Get title
# ============================================================

def get_candidate_title(
    records: list[dict],
    marker_index: int,
    marker_info: dict,
):

    inline_title = marker_info[
        "inline_title"
    ]

    if inline_title:

        return (
            normalize_title(
                inline_title
            ),
            marker_index + 1,
        )

    for index in range(
        marker_index + 1,
        min(
            marker_index + 8,
            len(records),
        ),
    ):

        line = records[
            index
        ][
            "text"
        ].strip()

        if not line:
            continue

        return (
            normalize_title(
                line
            ),
            index + 1,
        )

    return (
        "",
        marker_index + 1,
    )


# ============================================================
# Validate recipe marker
# ============================================================

def validate_recipe_candidate(
    records: list[dict],
    marker_index: int,
    marker_info: dict,
):

    (
        title,
        content_start,
    ) = get_candidate_title(
        records,
        marker_index,
        marker_info,
    )

    if not title:
        return None

    if title in CATEGORY_NAMES:
        return None

    if title.upper() in {
        "COOKING TIPS",
        "EATING WITH CHOPSTICKS",
        "ABOUT THE AUTHOR",
    }:
        return None

    checked = 0

    for index in range(
        content_start,
        min(
            content_start + 20,
            len(records),
        ),
    ):

        line = records[
            index
        ][
            "text"
        ].strip()

        if not line:
            continue

        if line in CATEGORY_NAMES:
            return None

        if parse_numbered_marker(
            line
        ):
            return None

        if looks_like_ingredient_line(
            line
        ):

            return {
                "title":
                    title,

                "number":
                    marker_info[
                        "number"
                    ],

                "page":
                    records[
                        marker_index
                    ][
                        "page"
                    ],

                "marker_index":
                    marker_index,

                "content_start":
                    content_start,
            }

        checked += 1

        if checked >= 10:
            break

    return None


# ============================================================
# Detect all real recipe markers
# ============================================================

def detect_recipe_markers(
    pages: list[dict],
):

    records = flatten_pages(
        pages
    )

    detected = []

    current_category = None

    toc_started = False
    recipe_section_started = False
    highest_number_seen = 0

    for index, record in enumerate(
        records
    ):

        line = record[
            "text"
        ]

        page_number = record[
            "page"
        ]

        # ----------------------------------------------------
        # New category
        # ----------------------------------------------------

        if line in CATEGORY_NAMES:

            current_category = line

            toc_started = False
            recipe_section_started = False
            highest_number_seen = 0

            print(
                f"\nCategory detected: "
                f"{current_category} "
                f"(page {page_number})"
            )

            continue

        if not current_category:
            continue

        marker_info = (
            parse_numbered_marker(
                line
            )
        )

        if not marker_info:
            continue

        number = marker_info[
            "number"
        ]

        # ----------------------------------------------------
        # Ignore category TOC until numbering restarts at 1.
        # ----------------------------------------------------

        if not recipe_section_started:

            if not toc_started:

                toc_started = True
                highest_number_seen = number

                continue

            if (
                number == 1
                and highest_number_seen > 1
            ):

                recipe_section_started = (
                    True
                )

            else:

                highest_number_seen = max(
                    highest_number_seen,
                    number,
                )

                continue

        candidate = (
            validate_recipe_candidate(
                records,
                index,
                marker_info,
            )
        )

        if not candidate:
            continue

        candidate[
            "category"
        ] = current_category

        detected.append(
            candidate
        )

    return (
        records,
        detected,
    )


# ============================================================
# Find end of one recipe
# ============================================================

def find_recipe_end(
    records: list[dict],
    markers: list[dict],
    marker_position: int,
) -> int:

    current = markers[
        marker_position
    ]

    start = current[
        "content_start"
    ]

    if (
        marker_position + 1
        < len(markers)
    ):

        next_marker_index = (
            markers[
                marker_position + 1
            ][
                "marker_index"
            ]
        )

    else:

        next_marker_index = (
            len(records)
        )

    # --------------------------------------------------------
    # If a new category begins before the next actual recipe,
    # stop there. This prevents the next category's TOC from
    # leaking into the final recipe of the previous category.
    # --------------------------------------------------------

    for index in range(
        start,
        next_marker_index,
    ):

        if (
            records[index][
                "text"
            ]
            in CATEGORY_NAMES
        ):

            return index

    return next_marker_index


# ============================================================
# Clean ingredient
# ============================================================

def clean_ingredient(
    text: str,
) -> str:

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


# ============================================================
# Clean instruction
# ============================================================

def clean_instruction(
    text: str,
) -> str:

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # Fix spacing before punctuation.
    text = re.sub(
        r"\s+([,.!?;:])",
        r"\1",
        text,
    )

    # Obvious missing-space source artifacts.
    replacements = {
        "andstir-fry":
            "and stir-fry",

        "sitr ":
            "stir ",

        "tir until":
            "stir until",
    }

    for old, new in (
        replacements.items()
    ):

        text = text.replace(
            old,
            new,
        )

    return text


# ============================================================
# Split accumulated cooking text into steps
# ============================================================

def split_instruction_text(
    instruction_blocks: list[str],
) -> list[str]:

    if not instruction_blocks:
        return []

    full_text = " ".join(
        instruction_blocks
    )

    full_text = clean_instruction(
        full_text
    )

    raw_steps = re.split(
        r"(?<=[.!?])\s+",
        full_text,
    )

    steps = []

    for step in raw_steps:

        step = clean_instruction(
            step
        )

        if not step:
            continue

        if is_serving_only_line(
            step
        ):
            continue

        if is_note_line(
            step
        ):
            continue

        steps.append(
            step
        )

    return steps


# ============================================================
# Parse recipe body
# ============================================================

def parse_recipe_body(
    body_lines: list[str],
):

    ingredients = []
    instruction_blocks = []

    phase = "ingredients"

    index = 0

    while index < len(
        body_lines
    ):

        line = body_lines[
            index
        ].strip()

        if not line:

            index += 1
            continue

        # ----------------------------------------------------
        # Skip serving/yield statements.
        #
        # Examples:
        #
        # Makes 4 servings.
        # Serves 6.
        #
        # Servings are stored separately.
        # ----------------------------------------------------

        if is_serving_only_line(
            line
        ):

            index += 1
            continue

        # ----------------------------------------------------
        # Ignore cookbook notes as recipe steps.
        #
        # Examples:
        #
        # note: ...
        # notes: ...
        # ----------------------------------------------------

        if is_note_line(
            line
        ):

            index += 1
            continue

        # ----------------------------------------------------
        # Ingredient subsection heading.
        #
        # Examples:
        #
        # Marinade:
        # Sauce:
        # Cooking sauce:
        # Filling:
        #
        # Some recipes such as Spring Rolls switch between
        # ingredients and instructions multiple times.
        # ----------------------------------------------------

        if is_ingredient_section_heading(
            line
        ):

            has_ingredient_after = False

            for lookahead in range(
                index + 1,
                min(
                    index + 5,
                    len(body_lines),
                ),
            ):

                next_line = (
                    body_lines[
                        lookahead
                    ].strip()
                )

                if not next_line:
                    continue

                if looks_like_ingredient_line(
                    next_line
                ):

                    has_ingredient_after = True

                break

            if has_ingredient_after:

                phase = "ingredients"

            index += 1
            continue

        # ----------------------------------------------------
        # Strong ingredient evidence.
        # ----------------------------------------------------

        if looks_like_ingredient_line(
            line
        ):

            ingredients.append(
                clean_ingredient(
                    line
                )
            )

            phase = "ingredients"

            index += 1
            continue

        # ----------------------------------------------------
        # Strong cooking instruction evidence.
        # ----------------------------------------------------

        if looks_like_instruction_line(
            line
        ):

            instruction_blocks.append(
                line
            )

            phase = "steps"

            index += 1
            continue

        # ----------------------------------------------------
        # TIME-ONLY CONTINUATION
        #
        # PDF line wrapping sometimes creates:
        #
        # "cover and marinade for"
        # "30 minutes."
        #
        # or:
        #
        # "marinade for 30 minutes to"
        # "6 hours."
        #
        # The second line must continue the previous
        # instruction. It must NEVER become an ingredient.
        # ----------------------------------------------------

        time_fragment = re.fullmatch(
            r"\d+(?:\.\d+)?\s+"
            r"(?:seconds?|minutes?|hours?|mins?|hrs?)\.?",
            line,
            flags=re.IGNORECASE,
        )

        if time_fragment:

            if instruction_blocks:

                instruction_blocks[-1] = (
                    instruction_blocks[-1]
                    + " "
                    + line
                )

            else:

                # This should be extremely rare.
                # Still safer to classify a duration as
                # instruction text than as an ingredient.
                instruction_blocks.append(
                    line
                )

            phase = "steps"

            index += 1
            continue

        # ----------------------------------------------------
        # Temperature-only continuation.
        #
        # Similar protection for fragments such as:
        #
        # 350F.
        # 375 F.
        # ----------------------------------------------------

        temperature_fragment = re.fullmatch(
            r"\d+\s*°?\s*[FCfc]\.?",
            line,
        )

        if temperature_fragment:

            if instruction_blocks:

                instruction_blocks[-1] = (
                    instruction_blocks[-1]
                    + " "
                    + line
                )

            else:

                instruction_blocks.append(
                    line
                )

            phase = "steps"

            index += 1
            continue

        # ----------------------------------------------------
        # Other ambiguous lines
        #
        # If we're still in the ingredient section, preserve
        # the line as an ingredient. This catches ingredients
        # without measurements such as:
        #
        # Whipped cream
        # Salad greens
        #
        # Once directions have begun, ambiguous lines are
        # treated as continuations of the previous instruction.
        # ----------------------------------------------------

        if phase == "ingredients":

            ingredients.append(
                clean_ingredient(
                    line
                )
            )

        else:

            if instruction_blocks:

                instruction_blocks[-1] = (
                    instruction_blocks[-1]
                    + " "
                    + line
                )

            else:

                instruction_blocks.append(
                    line
                )

        index += 1

    # ========================================================
    # Remove exact duplicate ingredients while preserving
    # their original order.
    # ========================================================

    cleaned_ingredients = []

    seen = set()

    for ingredient in ingredients:

        ingredient = (
            clean_ingredient(
                ingredient
            )
        )

        normalized = (
            ingredient
            .strip()
            .lower()
        )

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        cleaned_ingredients.append(
            ingredient
        )

    # ========================================================
    # Convert accumulated instruction text into individual
    # cooking steps.
    # ========================================================

    steps = split_instruction_text(
        instruction_blocks
    )

    return (
        cleaned_ingredients,
        steps,
    )

# ============================================================
# Build structured recipes
# ============================================================

def build_recipe_records(
    records: list[dict],
    markers: list[dict],
) -> list[dict]:

    recipes = []

    for marker_position, marker in enumerate(
        markers
    ):

        body_start = marker[
            "content_start"
        ]

        body_end = find_recipe_end(
            records,
            markers,
            marker_position,
        )

        body_lines = [
            records[index][
                "text"
            ]
            for index in range(
                body_start,
                body_end,
            )
        ]

        raw_body_text = "\n".join(
            body_lines
        )

        servings = (
            extract_servings_from_text(
                raw_body_text
            )
        )

        (
            ingredients,
            steps,
        ) = parse_recipe_body(
            body_lines
        )

        recipe = {
            "id": (
                f"chinese_"
                f"{marker_position + 1:04d}"
            ),

            "title":
                marker[
                    "title"
                ],

            "cuisine":
                "Chinese",

            "category":
                marker[
                    "category"
                ].title(),

            "source_file":
                "chinese.pdf",

            "servings":
                servings,

            "ingredients":
                ingredients,

            "steps":
                steps,

            # Nutrition will be calculated later from
            # structured ingredients.
            "nutrition": {
                "calories":
                    None,

                "protein_g":
                    None,

                "carbohydrates_g":
                    None,

                "fat_g":
                    None,
            },
        }

        recipes.append(
            recipe
        )

    return recipes


# ============================================================
# Validation
# ============================================================

def validate_recipes(
    recipes: list[dict],
):

    problems = []

    seen_ids = set()
    seen_titles = set()

    for index, recipe in enumerate(
        recipes,
        start=1,
    ):

        recipe_id = recipe[
            "id"
        ]

        title = recipe[
            "title"
        ]

        ingredients = recipe[
            "ingredients"
        ]

        steps = recipe[
            "steps"
        ]

        if recipe_id in seen_ids:

            problems.append(
                f"{index:03d}. Duplicate ID: "
                f"{recipe_id}"
            )

        seen_ids.add(
            recipe_id
        )

        normalized_title = (
            title.lower()
            .strip()
        )

        if normalized_title in seen_titles:

            problems.append(
                f"{index:03d}. Duplicate title: "
                f"{title}"
            )

        seen_titles.add(
            normalized_title
        )

        if not title:

            problems.append(
                f"{index:03d}. Missing title"
            )

        if len(ingredients) < 2:

            problems.append(
                f"{index:03d}. "
                f"{title}: only "
                f"{len(ingredients)} "
                "ingredient(s)"
            )

        if len(steps) < 1:

            problems.append(
                f"{index:03d}. "
                f"{title}: no steps"
            )

    return problems


# ============================================================
# Suspicious extraction report
# ============================================================

def print_suspicious_recipes(
    recipes: list[dict],
):

    print(
        "\n=============================="
    )

    print(
        "SUSPICIOUS RECIPE CHECK"
    )

    print(
        "=============================="
    )

    found = 0

    for index, recipe in enumerate(
        recipes,
        start=1,
    ):

        suspicious = False

        reasons = []

        if len(
            recipe[
                "ingredients"
            ]
        ) < 3:

            suspicious = True

            reasons.append(
                "few ingredients"
            )

        if len(
            recipe[
                "steps"
            ]
        ) < 2:

            suspicious = True

            reasons.append(
                "few steps"
            )

        for ingredient in recipe[
            "ingredients"
        ]:

            if len(ingredient) > 180:

                suspicious = True

                reasons.append(
                    "very long ingredient"
                )

            if re.fullmatch(
                r"\d+(?:\.\d+)?\s+"
                r"(?:seconds?|minutes?|hours?|mins?|hrs?)\.?",
                ingredient.strip(),
                flags=re.IGNORECASE,
            ):

                suspicious = True

                reasons.append(
                    f"time stored as ingredient: "
                    f"{ingredient}"
                )

        if suspicious:

            found += 1

            print(
                f"{index:03d}. "
                f"{recipe['title']} "
                f"-> "
                f"{', '.join(reasons)}"
            )

    print(
        f"\nSuspicious recipes found: "
        f"{found}"
    )


# ============================================================
# Preview
# ============================================================

def print_preview(
    recipes: list[dict],
):

    print(
        "\n=============================="
    )

    print(
        "EXTRACTION PREVIEW"
    )

    print(
        "=============================="
    )

    for recipe in recipes[:5]:

        print(
            f"\nTitle: "
            f"{recipe['title']}"
        )

        print(
            f"Category: "
            f"{recipe['category']}"
        )

        print(
            f"Servings: "
            f"{recipe['servings']}"
        )

        print(
            "\nIngredients:"
        )

        for ingredient in recipe[
            "ingredients"
        ][:10]:

            print(
                f"  - {ingredient}"
            )

        print(
            "\nFirst steps:"
        )

        for step in recipe[
            "steps"
        ][:3]:

            print(
                f"  - {step}"
            )

        print(
            "------------------------------"
        )


# ============================================================
# Print all titles
# ============================================================

def print_all_titles(
    recipes: list[dict],
):

    print(
        "\n=============================="
    )

    print(
        "ALL CHINESE RECIPE TITLES"
    )

    print(
        "=============================="
    )

    for index, recipe in enumerate(
        recipes,
        start=1,
    ):

        print(
            f"{index:03d}. "
            f"{recipe['title']}"
        )

    print(
        "=============================="
    )

    print(
        f"TOTAL: "
        f"{len(recipes)}"
    )


# ============================================================
# Save
# ============================================================

def save_recipes(
    recipes: list[dict],
):

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            recipes,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"\nSaved "
        f"{len(recipes)} recipes to:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# Main
# ============================================================

def main():

    pages = load_pdf_pages(
        CHINESE_PDF
    )

    (
        records,
        markers,
    ) = detect_recipe_markers(
        pages
    )

    print(
        f"\nDetected real recipe blocks: "
        f"{len(markers)}"
    )

    recipes = build_recipe_records(
        records,
        markers,
    )

    print(
        f"Structured recipes created: "
        f"{len(recipes)}"
    )

    print_preview(
        recipes
    )

    print_all_titles(
        recipes
    )

    problems = validate_recipes(
        recipes
    )

    print(
        "\n=============================="
    )

    print(
        "VALIDATION"
    )

    print(
        "=============================="
    )

    if problems:

        for problem in problems:

            print(
                problem
            )

        print(
            f"\nValidation problems: "
            f"{len(problems)}"
        )

    else:

        print(
            "No basic validation problems found."
        )

    print_suspicious_recipes(
        recipes
    )

    # ========================================================
    # SAFETY GATE
    #
    # Do not overwrite/create the final Chinese JSON unless
    # all 162 real recipe blocks made it into structured data.
    # ========================================================

    if (
        len(markers)
        != EXPECTED_RECIPE_COUNT
    ):

        print(
            "\nBUILD STOPPED."
        )

        print(
            f"Expected "
            f"{EXPECTED_RECIPE_COUNT} "
            "recipe blocks, but detected "
            f"{len(markers)}."
        )

        print(
            "chinese_recipes.json "
            "was NOT written."
        )

        return

    if (
        len(recipes)
        != EXPECTED_RECIPE_COUNT
    ):

        print(
            "\nBUILD STOPPED."
        )

        print(
            f"Expected "
            f"{EXPECTED_RECIPE_COUNT} "
            "structured recipes, but created "
            f"{len(recipes)}."
        )

        print(
            "chinese_recipes.json "
            "was NOT written."
        )

        return

    if problems:

        print(
            "\nBUILD STOPPED."
        )

        print(
            "Validation problems were found."
        )

        print(
            "Fix them before saving "
            "chinese_recipes.json."
        )

        return

    save_recipes(
        recipes
    )

    print(
        "\nChinese structured extraction "
        "completed successfully."
    )


if __name__ == "__main__":
    main()