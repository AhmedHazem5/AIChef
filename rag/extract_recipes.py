import json
import re
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parent.parent

JAPANESE_PDF = (
    PROJECT_ROOT
    / "data"
    / "recipes"
    / "Japanese"
    / "Japanese.pdf"
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "structured_recipes"
)

OUTPUT_FILE = (
    OUTPUT_DIRECTORY
    / "japanese_recipes.json"
)


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\t", " ")

    cleaned_lines = []

    for line in text.splitlines():
        line = re.sub(
            r"[ ]+",
            " ",
            line,
        ).strip()

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


# ============================================================
# LOAD PDF
# ============================================================

def load_pdf_text(
    pdf_path: Path,
) -> str:

    print(
        f"Reading {pdf_path.name}..."
    )

    reader = PdfReader(
        str(pdf_path)
    )

    text_parts = []

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

        # Preserve a strong page separator.
        text_parts.append(
            page_text
        )

    full_text = "\n\f\n".join(
        text_parts
    )

    full_text = clean_text(
        full_text
    )

    print(
        f"Pages: {len(reader.pages)}"
    )

    print(
        f"Extracted "
        f"{len(full_text):,} characters."
    )

    return full_text


# ============================================================
# TITLE CLEANING
# ============================================================

def looks_like_ingredient_text(
    title: str,
) -> bool:
    """
    Reject strings that clearly look like ingredient lists
    rather than recipe titles.
    """

    lowered = title.lower()

    # Common measurement/unit indicators.
    measurement_terms = (
        " tbsp ",
        " tsp ",
        " cup ",
        " cups ",
        " oz ",
        " lb ",
        " lbs ",
        " gram ",
        " grams ",
        " kg ",
        " ml ",
        " c. ",
    )

    measurement_hits = sum(
        1
        for term in measurement_terms
        if term in f" {lowered} "
    )

    # Numbers/fractions appearing repeatedly are suspicious.
    number_hits = len(
        re.findall(
            r"\b\d+(?:/\d+)?\b",
            title,
        )
    )

    # Ingredient-title text tends to contain multiple commas.
    comma_count = title.count(",")

    if measurement_hits >= 2:
        return True

    if number_hits >= 3:
        return True

    if comma_count >= 2 and number_hits >= 1:
        return True

    return False


def normalize_title(title: str) -> str:

    # ========================================================
    # Basic cleanup
    # ========================================================

    title = re.sub(
        r"\s+",
        " ",
        title.strip(),
    )

    # ========================================================
    # Repair PDF split-letter artifacts
    #
    # Examples:
    #
    # R AMEN       -> RAMEN
    # S OUP        -> SOUP
    # J APANESE    -> JAPANESE
    # ========================================================

    previous = None

    while previous != title:

        previous = title

        title = re.sub(
            r"\b([A-Za-z])\s+([A-Za-z]{2,})\b",
            lambda match: (
                match.group(1)
                + match.group(2)
            ),
            title,
        )

    # ========================================================
    # Fix hyphenated split words
    #
    # 4-I NGREDIENT
    # -> 4-INGREDIENT
    # ========================================================

    title = re.sub(
        r"([A-Za-z0-9])-([A-Za-z])\s+([A-Za-z]+)",
        lambda match: (
            match.group(1)
            + "-"
            + match.group(2)
            + match.group(3)
        ),
        title,
    )

    # ========================================================
    # Recipe 1:
    # remove all front matter before the real title
    # ========================================================

    first_recipe_match = re.search(
        r"4-Ingredient\s+Ramen",
        title,
        flags=re.IGNORECASE,
    )

    if first_recipe_match:

        title = title[
            first_recipe_match.start():
        ]

    # ========================================================
    # Known PDF extraction artifacts
    # ========================================================

    title = re.sub(
        r"\bDevil\s*'\s*Seggs\b",
        "Devil's Eggs",
        title,
        flags=re.IGNORECASE,
    )

    title = re.sub(
        r"\bXjapan\b",
        "X Japan",
        title,
        flags=re.IGNORECASE,
    )

    # ========================================================
    # Remove Japanese subtitle / broken parenthetical text
    #
    # Cucumber Salad In Japan ( キュウリ...
    # -> Cucumber Salad In Japan
    # ========================================================

    title = re.sub(
        r"\s*\(.*$",
        "",
        title,
    )

    # ========================================================
    # Remove accidental cookbook heading prefix
    # ========================================================

    title = re.sub(
        r"^(Recipes|Recipe)\s+",
        "",
        title,
        flags=re.IGNORECASE,
    )

    # ========================================================
    # Remove junk around edges
    # ========================================================

    title = title.strip(
        " -_:;,.|—"
    )

    # ========================================================
    # Reject things that cannot be titles
    # ========================================================

    invalid_titles = {
        "",
        "ingredients",
        "directions",
        "timing information",
        "nutritional information",
        "servings per recipe",
    }

    if title.lower() in invalid_titles:
        return ""

    # ========================================================
    # Normal title capitalization
    # ========================================================

    title = title.title()

    # Python's .title() produces:
    #
    # Devil'S
    #
    # Fix possessives/apostrophes afterward.
    title = re.sub(
        r"'S\b",
        "'s",
        title,
    )

    if looks_like_ingredient_text(
        title
    ):
        return ""

    return title

def find_recipe_title(
    text: str,
    ingredients_position: int,
) -> str:
    """
    Extract the complete recipe title immediately before
    the Ingredients heading.

    This PDF frequently splits titles across many lines
    and inserts blank lines inside titles.
    """

    before = text[:ingredients_position]
    lines = before.splitlines()

    title_lines = []

    index = len(lines) - 1

    # Skip blank lines immediately above Ingredients.
    while index >= 0 and not lines[index].strip():
        index -= 1

    stop_markers = (
        "calories",
        "protein",
        "fat",
        "carbohydrates",
        "cholesterol",
        "sodium",
        "timing information",
        "nutritional information",
        "servings per recipe",
        "percent daily values",
        "total time",
        "preparation",
        "cooking",
    )

    while index >= 0:

        line = lines[index].strip()
        lowered = line.lower()

        # ----------------------------------------
        # Blank lines are allowed inside titles.
        # ----------------------------------------

        if not line:
            index -= 1
            continue

        # ----------------------------------------
        # Stop when we reach metadata belonging
        # to the previous recipe.
        # ----------------------------------------

        if any(
            marker in lowered
            for marker in stop_markers
        ):
            break

        # The end of the previous recipe is also
        # a reliable boundary.
        if lowered == "enjoy." or lowered == "enjoy":
            break

        # ----------------------------------------
        # Ignore obvious page-number-only lines.
        # ----------------------------------------

        if line.isdigit():
            index -= 1
            continue

        title_lines.append(line)

        # Safety limit only.
        if len(title_lines) >= 40:
            break

        index -= 1

    if not title_lines:
        return ""

    title_lines.reverse()

    title = " ".join(
        title_lines
    )

    return normalize_title(
        title
    )
# ============================================================
# FIND REAL RECIPE SECTIONS
# ============================================================

def extract_recipe_sections(
    text: str,
):
    """
    Extract recipe sections without allowing one recipe
    to bleed into the next recipe.

    A recipe begins at a standalone Ingredients heading.
    We isolate everything until the next standalone
    Ingredients heading, then parse Directions and Servings
    only inside that block.
    """

    # Find every real Ingredients heading.
    ingredient_matches = list(
        re.finditer(
            r"^[ \t]*Ingredients[ \t]*$",
            text,
            flags=(
                re.IGNORECASE
                | re.MULTILINE
            ),
        )
    )

    sections = []

    for index, ingredient_match in enumerate(
        ingredient_matches
    ):
        block_start = (
            ingredient_match.start()
        )

        # Stop before the next recipe's Ingredients heading.
        if index + 1 < len(
            ingredient_matches
        ):
            block_end = (
                ingredient_matches[
                    index + 1
                ].start()
            )
        else:
            block_end = len(text)

        block = text[
            block_start:block_end
        ]

        # ------------------------------------------
        # Find Directions inside THIS recipe only.
        # ------------------------------------------

        directions_match = re.search(
            r"^[ \t]*Directions[ \t]*$",
            block,
            flags=(
                re.IGNORECASE
                | re.MULTILINE
            ),
        )

        if not directions_match:
            continue

        ingredients_text = block[
            ingredient_match.end()
            - block_start:
            directions_match.start()
        ]

        # ------------------------------------------
        # Find Servings inside THIS recipe only.
        # ------------------------------------------

        servings_match = re.search(
            r"""
            ^[ \t]*Servings
            [ \t]+per
            [ \t]+Recipe:
            [ \t]*$
            \s*
            (?P<servings>[0-9]+)
            """,
            block[
                directions_match.end():
            ],
            flags=(
                re.IGNORECASE
                | re.MULTILINE
                | re.VERBOSE
            ),
        )

        if servings_match:

            directions_start = (
                directions_match.end()
            )

            directions_end = (
                directions_match.end()
                + servings_match.start()
            )

            directions_text = block[
                directions_start:
                directions_end
            ]

            servings = (
                servings_match.group(
                    "servings"
                )
            )

            absolute_end = (
                block_start
                + directions_match.end()
                + servings_match.end()
            )

        else:
            # Some recipes may have malformed/missing
            # serving metadata. Still preserve their
            # directions, but NEVER enter the next recipe.
            directions_text = block[
                directions_match.end():
            ]

            servings = ""

            absolute_end = block_end

        sections.append(
            {
                "start":
                    block_start,

                "ingredients_start":
                    ingredient_match.start(),

                "ingredients":
                    ingredients_text,

                "directions":
                    directions_text,

                "servings":
                    servings,

                "end":
                    absolute_end,
            }
        )

    print(
        f"Found "
        f"{len(sections)} "
        "recipe sections."
    )

    return sections

# ============================================================
# INGREDIENTS
# ============================================================

def parse_ingredients(
    text: str,
) -> list[str]:

    ingredients = []

    for line in text.splitlines():

        line = re.sub(
            r"\s+",
            " ",
            line,
        ).strip()

        if not line:
            continue

        lowered = line.lower()

        if lowered in {
            "ingredients",
            "directions",
        }:
            continue

        ingredients.append(
            line
        )

    return ingredients


# ============================================================
# DIRECTIONS
# ============================================================

def clean_instruction_text(
    text: str,
) -> str:
    """
    Fix obvious PDF extraction artifacts without
    changing the intended cooking instruction.
    """

    if not text:
        return ""

    # Collapse whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # --------------------------------------------------------
    # Common missing-space artifacts
    # --------------------------------------------------------

    text = re.sub(
        r"\bStirthe\b",
        "Stir the",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bAddthe\b",
        "Add the",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bPlacethe\b",
        "Place the",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bServethe\b",
        "Serve the",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bCookthe\b",
        "Cook the",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bMixthe\b",
        "Mix the",
        text,
        flags=re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Fix obvious negative-time OCR artifact:
    #
    # "cook for -5 min"
    # -> "cook for 5 min"
    #
    # A negative cooking time is impossible, so this is a
    # safe mechanical correction.
    # --------------------------------------------------------

    text = re.sub(
        r"\bfor\s+-([0-9]+)\s*(min|mins|minute|minutes)\b",
        r"for \1 \2",
        text,
        flags=re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Remove double punctuation / awkward spacing
    # --------------------------------------------------------

    text = re.sub(
        r"\s+([,.!?;:])",
        r"\1",
        text,
    )

    text = re.sub(
        r"([,.!?;:]){2,}",
        r"\1",
        text,
    )

    return text


def parse_directions(
    text: str,
) -> list[str]:

    text = clean_instruction_text(
        text
    )

    # Remove cookbook filler.
    text = re.sub(
        r"\bEnjoy\.?\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    raw_steps = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    steps = []

    for step in raw_steps:

        step = clean_instruction_text(
            step
        )

        if not step:
            continue

        if step.lower() in {
            "enjoy",
            "enjoy.",
        }:
            continue

        steps.append(
            step
        )

    return steps

# ============================================================
# NUTRITION
# ============================================================

def extract_number(
    text: str,
    label: str,
):
    pattern = re.compile(
        rf"""
        ^[ \t]*{re.escape(label)}[ \t]*$
        \s*
        ([0-9]+(?:\.[0-9]+)?)
        """,
        re.IGNORECASE
        | re.MULTILINE
        | re.VERBOSE,
    )

    match = pattern.search(text)

    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None

def get_after_recipe_section(
    text: str,
    start_position: int,
) -> str:
    """
    Read the nutrition/timing information after the
    Servings line, stopping before the next Ingredients heading.
    """

    section = text[
        start_position:
        start_position + 3000
    ]

    next_recipe = re.search(
        r"""
        ^[ \t]*Ingredients[ \t]*$
        """,
        section,
        flags=(
            re.IGNORECASE
            | re.MULTILINE
            | re.VERBOSE
        ),
    )

    if next_recipe:
        section = section[
            :next_recipe.start()
        ]

    return section


# ============================================================
# BUILD STRUCTURED RECIPES
# ============================================================

def build_recipe_records(
    text: str,
    matches,
) -> list[dict]:

    recipes = []

    for match in matches:

        title = find_recipe_title(
            text,
            match[
                "ingredients_start"
            ],
        )

        ingredients = (
            parse_ingredients(
                match[
                    "ingredients"
                ]
            )
        )

        steps = (
            parse_directions(
                match[
                    "directions"
                ]
            )
        )

        if not title:
            continue

        if len(ingredients) < 2:
            continue

        if len(steps) < 1:
            continue

        nutrition_text = (
            get_after_recipe_section(
                text,
                match[
                    "end"
                ],
            )
        )

        recipe = {
            "id": (
                f"japanese_"
                f"{len(recipes) + 1:04d}"
            ),

            "title":
                title,

            "cuisine":
                "Japanese",

            "source_file":
                "Japanese.pdf",

            "servings":
                match[
                    "servings"
                ].strip(),

            "ingredients":
                ingredients,

            "steps":
                steps,

            "nutrition": {
                "calories":
                    extract_number(
                        nutrition_text,
                        "Calories",
                    ),

                "protein_g":
                    extract_number(
                        nutrition_text,
                        "Protein",
                    ),

                "carbohydrates_g":
                    extract_number(
                        nutrition_text,
                        "Carbohydrates",
                    ),

                "fat_g":
                    extract_number(
                        nutrition_text,
                        "Fat",
                    ),
            },
        }

        recipes.append(
            recipe
        )

    return recipes


# ============================================================
# SAVE
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
        f"{len(recipes)} "
        "recipes to:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# PREVIEW
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
            f"Servings: "
            f"{recipe['servings']}"
        )

        print(
            "Ingredients:"
        )

        for ingredient in (
            recipe["ingredients"][:6]
        ):
            print(
                f"  - {ingredient}"
            )

        print(
            "First step:"
        )

        print(
            f"  "
            f"{recipe['steps'][0]}"
        )

        nutrition = (
            recipe["nutrition"]
        )

        print(
            f"Calories: "
            f"{nutrition['calories']}"
        )

        print(
            f"Protein: "
            f"{nutrition['protein_g']} g"
        )

    print(
        "\n=============================="
    )

def print_all_titles(
    recipes: list[dict],
):
    print(
        "\n=============================="
    )
    print(
        "ALL EXTRACTED RECIPE TITLES"
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
        f"TOTAL: {len(recipes)} recipes"
    )

def print_all_recipe_titles(
    recipes: list[dict],
):
    print(
        "\n=============================="
    )
    print(
        "ALL RECIPE TITLES"
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
        f"TOTAL: {len(recipes)}"
    )

def print_duplicate_titles(
    recipes: list[dict],
):
    seen = {}
    duplicates = []

    for index, recipe in enumerate(
        recipes,
        start=1,
    ):
        title = recipe[
            "title"
        ].strip().lower()

        if title in seen:
            duplicates.append(
                (
                    seen[title],
                    index,
                    recipe["title"],
                )
            )
        else:
            seen[title] = index

    print(
        "\n=============================="
    )
    print(
        "DUPLICATE TITLES"
    )
    print(
        "=============================="
    )

    if not duplicates:
        print(
            "No duplicate titles found."
        )

    for first, second, title in duplicates:
        print(
            f"{first:03d} and "
            f"{second:03d}: "
            f"{title}"
        )

    print(
        "=============================="
    )    

def print_suspicious_title_context(
    text: str,
    matches,
    recipes: list[dict],
):
    suspicious_starts = (
        "And ",
        "With ",
        "From ",
        "Of ",
        "For ",
        "Make ",
    )

    suspicious_exact = {
        "Japan",
        "Devil Seggs",
        "Xjapan Ramen",
        "Ricy Ketchup Omelet",
        "$3 Dollar Dinner",
    }

    print(
        "\n=============================="
    )
    print(
        "SUSPICIOUS TITLE CONTEXT"
    )
    print(
        "=============================="
    )

    for index, recipe in enumerate(
        recipes
    ):
        title = recipe["title"]

        suspicious = (
            title.startswith(
                suspicious_starts
            )
            or title in suspicious_exact
        )

        if not suspicious:
            continue

        match = matches[index]

        start = max(
            0,
            match.start() - 350
        )

        end = match.start()

        context = text[
            start:end
        ]

        print(
            f"\nRecipe "
            f"{index + 1}: "
            f"{title}"
        )

        print(
            "----- RAW TEXT ABOVE INGREDIENTS -----"
        )

        print(
            context
        )

        print(
            "--------------------------------------"
        )

def print_suspicious_steps(
    recipes: list[dict],
):
    print(
        "\n=============================="
    )
    print(
        "SUSPICIOUS COOKING STEPS"
    )
    print(
        "=============================="
    )

    suspicious_patterns = (
        " -",
        "stirthe",
        "addthe",
        "cookthe",
        "placethe",
        "servethe",
        "mixthe",
    )

    found = 0

    for recipe in recipes:

        for step_number, step in enumerate(
            recipe["steps"],
            start=1,
        ):

            lowered = step.lower()

            if any(
                pattern in lowered
                for pattern in suspicious_patterns
            ):

                print(
                    f"\n{recipe['title']}"
                )

                print(
                    f"Step {step_number}: "
                    f"{step}"
                )

                found += 1

    print(
        f"\nSuspicious steps found: "
        f"{found}"
    )

    print(
        "=============================="
    )

# ============================================================
# MAIN
# ============================================================

def main():

    full_text = load_pdf_text(
        JAPANESE_PDF
    )

    matches = (
        extract_recipe_sections(
            full_text
        )
    )

    recipes = (
        build_recipe_records(
            full_text,
            matches,
        )
    )

    print(
        f"Valid structured recipes: "
        f"{len(recipes)}"
    )

    print_preview(
        recipes
    )

    # print_all_titles(
    #     recipes
    # )
    # print_suspicious_title_context(
    #     full_text,
    #     matches,
    #     recipes,
    # )

    print_all_recipe_titles(
        recipes
    )

    print_duplicate_titles(
        recipes
    )

    print_suspicious_steps(
        recipes
    )

    save_recipes(
        recipes
    )


if __name__ == "__main__":
    main()