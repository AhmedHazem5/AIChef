import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from functools import lru_cache


PROJECT_ROOT = Path(__file__).resolve().parent.parent

NUTRITION_DATABASE_FILE = (
    PROJECT_ROOT
    / "data"
    / "nutrition"
    / "nutrition_database.json"
)


# ============================================================
# Load database once
# ============================================================

def load_nutrition_database():

    if not NUTRITION_DATABASE_FILE.exists():

        raise FileNotFoundError(
            "Nutrition database not found:\n"
            f"{NUTRITION_DATABASE_FILE}\n\n"
            "Run:\n"
            "python -m nutrition.build_nutrition_database"
        )

    with open(
        NUTRITION_DATABASE_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        records = json.load(
            file
        )

    print(
        f"Loaded {len(records)} "
        "local nutrition records."
    )

    return records


NUTRITION_RECORDS = (
    load_nutrition_database()
)


# ============================================================
# Normalize food names for matching
# ============================================================

# ============================================================
# Normalize food names for matching
# ============================================================

def normalize_food_name(
    text: str,
) -> str:

    if not text:
        return ""

    text = text.lower().strip()

    # ========================================================
    # Fix common cookbook/extraction typos
    # ========================================================

    typo_replacements = {
        "ligth": "light",
        "monced": "minced",
        "bonelss": "boneless",
        "bonned": "boned",
        "unitl": "until",
        "muchroom": "mushroom",
        "greed": "green",
        "shreeded": "shredded",
        "worcestershice": "worcestershire",
    }

    for wrong, correct in typo_replacements.items():

        text = re.sub(
            rf"\b{re.escape(wrong)}\b",
            correct,
            text,
        )

    # ========================================================
    # Remove parenthetical notes
    #
    # Example:
    # rice wine (optional)
    # ->
    # rice wine
    # ========================================================

    text = re.sub(
        r"\([^)]*\)",
        " ",
        text,
    )

    # ========================================================
    # Remove punctuation
    # ========================================================

    text = re.sub(
        r"[^\w\s]",
        " ",
        text,
    )

    # ========================================================
    # Remove preparation/state words that usually hurt USDA
    # matching but do not identify the food itself.
    #
    # IMPORTANT:
    # We intentionally keep words such as:
    # raw, cooked, dried, roasted
    #
    # because those can materially change nutrition.
    # ========================================================

    preparation_words = {
        "minced",
        "chopped",
        "peeled",
        "freshly",
        "ground",
        "finely",
        "thinly",
        "sliced",
        "slice",
        "shredded",
        "seeded",
        "cored",
        "beaten",
        "crushed",
        "diced",
        "julienne",
        "strips",
        "strip",
        "pieces",
        "piece",
    }

    words = text.split()

    words = [
        word
        for word in words
        if word not in preparation_words
    ]

    text = " ".join(
        words
    )

    # ========================================================
    # Remove common cookbook phrases left after preparation
    # cleanup.
    # ========================================================

    phrase_replacements = [
        (
            r"\band\s+cut\s+into\b.*$",
            "",
        ),
        (
            r"\bcut\s+into\b.*$",
            "",
        ),
        (
            r"\band\s+cut\s+in\s+half\b.*$",
            "",
        ),
        (
            r"\bcut\s+in\s+half\b.*$",
            "",
        ),
        (
            r"\bgreen\s+top\s+removed\b",
            "",
        ),
        (
            r"\btops\s+removed\b",
            "",
        ),
        (
            r"\broot\s+removed\b",
            "",
        ),
    ]

    for pattern, replacement in phrase_replacements:

        text = re.sub(
            pattern,
            replacement,
            text,
        )

    # ========================================================
    # Remove dangling connector words left after preparation
    # phrase removal
    #
    # Example:
    # "red bell peppers cored and seeded"
    # -> "red bell peppers and"
    # -> "red bell peppers"
    # ========================================================

    text = re.sub(
        r"\b(?:and|or)\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # ========================================================
    # Collapse whitespace
    # ========================================================

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


# ============================================================
# Food aliases
#
# These aliases convert cookbook terminology into terminology
# that matches the local USDA database more reliably.
#
# Keep these generic. Do not add aliases for individual
# recipes.
# ============================================================

FOOD_ALIASES = {

    "a whole chicken or chicken":
        "chicken broilers or fryers meat and skin raw",

    "whole chicken or chicken":
        "chicken broilers or fryers meat and skin raw",
        
    "pork or chicken breasts":
        "pork fresh ground raw",

    "potatoes about 11/2 lbs":
        "potatoes flesh and skin raw",

    "cod steaks 6 oz each":
        "fish cod atlantic raw",

    "package ramen noodles":
        "soup ramen noodle any flavor dry",

    "packages ramen noodles":
         "soup ramen noodle any flavor dry",

    "potato":
        "potatoes flesh and skin raw",

    "potatoes":
        "potatoes flesh and skin raw",
    # ========================================================
    # Generic fish approximations
    # ========================================================

    "whole snapper":
        "fish snapper mixed species raw",

    "fresh fish fillet":
        "fish snapper mixed species raw",

    "firm white fish fillets":
        "fish snapper mixed species raw",

    "fresh or frozen swordfish shark seabass tuna or monkfish":
        "fish snapper mixed species raw",

    "snapper or jewfish fillets":
        "fish snapper mixed species raw",

    "trout fillets":
        "fish trout raw",

    "cod steaks":
        "fish cod raw",

    "fresh salmon fillets":
        "fish salmon raw",

    # ========================================================
    # Shrimp
    # ========================================================

    "raw shrimp de-veined":
        "crustaceans shrimp raw",

    "raw shrimp in the shell":
        "crustaceans shrimp raw",

    "raw large shrimp in the shell":
        "crustaceans shrimp raw",

    # ========================================================
    # Pork / beef
    # ========================================================

    "boneless pork sirloin or tenderloin":
        "pork fresh loin tenderloin separable lean only raw",

    "boneless tenderloin":
        "pork fresh loin tenderloin separable lean only raw",

    "meaty spareribs":
        "pork spareribs raw",

    "beef fillet":
        "beef tenderloin steak raw",

    "sirloin tips":
        "beef sirloin steak raw",

    "fatty pork":
        "pork fresh belly raw",

    # ========================================================
    # Tofu
    # ========================================================

    "firm tofu":
        "tofu raw firm prepared with calcium",

    "firm tofu or bean curd":
        "tofu raw firm prepared with calcium",

    "bean curd":
        "tofu raw firm prepared with calcium",

    # ========================================================
    # Vegetables / nuts
    # ========================================================

    "fresh bean sprouts":
        "mung beans mature seeds sprouted raw",

    "green capsicum":
        "peppers sweet green raw",

    "salted peanuts":
        "peanuts all types oil roasted with salt",

    "salted walnuts":
        "nuts walnuts english",

    # ========================================================
    # Common cleanup aliases
    # ========================================================

    "grated ginger":
        "ginger root raw",

    "grated fresh ginger":
        "ginger root raw",

    "slices fresh ginger":
        "ginger root raw",

    "fresh ginger smashed":
        "ginger root raw",

    "whole green onion":
        "onions spring or scallions raw",

    "whole green onions":
        "onions spring or scallions raw",

    "cracked black pepper":
        "spices pepper black",

    "warm water":
        "water bottled generic",

    "iced water":
        "water bottled generic",

    "whole green onions":
        "onions spring or scallions raw",

    "chinese dried mushrooms":
        "mushrooms shiitake dried",

    "dried chinese mushroom":
        "mushrooms shiitake dried",

    "dried chinese mushrooms":
        "mushrooms shiitake dried",

    # ========================================================
    # Fish
    # ========================================================

    "snapper":
        "fish snapper mixed species raw",

    "fresh snapper":
        "fish snapper mixed species raw",

    "salmon fillet":
        "fish salmon raw",

    "salmon fillets":
        "fish salmon raw",


    # ========================================================
    # Lamb
    # ========================================================

    "boneless leg of lamb":
        "lamb australian imported fresh leg bottom boneless separable lean only trimmed to 1 8 fat raw",

    "lamb leg":
        "lamb australian imported fresh leg bottom boneless separable lean only trimmed to 1 8 fat raw",

    "lamb leg or shoulder meat":
        "lamb australian imported fresh leg bottom boneless separable lean only trimmed to 1 8 fat raw",


    # ========================================================
    # Pork
    # ========================================================

    "pork belly":
        "pork fresh belly raw",

    "pork tenderloin":
        "pork fresh loin tenderloin separable lean only raw",

    "boneless pork tenderloin":
        "pork fresh loin tenderloin separable lean only raw",

    "boneless pork sirloin":
        "pork fresh loin tenderloin separable lean only raw",


    # ========================================================
    # Noodles
    # ========================================================

    "fresh egg noodles":
        "noodles egg enriched cooked",

    "fresh egg noodle":
        "noodles egg enriched cooked",

    "dried chinese egg noodles":
        "noodles egg dry enriched",

    "dried chinese eggs noodles":
        "noodles egg dry enriched",

    "thin noodles":
        "noodles egg dry enriched",

    "brown sugar":
        "sugars brown",

    "packed brown sugar":
        "sugars brown",

    "firmly packed brown sugar":
        "sugars brown",

    # ========================================================
    # Beef
    # ========================================================

    "beef":
        "beef steak",

    "beef steak":
        "beef steak",

    "lean boneless beef steak":
        "beef steak",

    "stewing beef":
        "beef chuck raw",

    # ========================================================
    # Additional poultry
    # ========================================================

    "chicken":
        "chicken broilers or fryers meat only raw",

    "whole chicken":
        "chicken broilers or fryers meat and skin raw",

    "chicken pieces":
        "chicken broilers or fryers meat and skin raw",

    "chicken thighs":
        "chicken broilers or fryers thigh meat only raw",

    "chicken breast or thighs":
        "chicken broilers or fryers meat only raw",

    "chicken breasts or thighs":
        "chicken broilers or fryers meat only raw",

    # ========================================================
    # Seafood
    # ========================================================

    "raw shrimp shelled":
        "crustaceans shrimp raw",

    "raw shrimp de-veined":
        "crustaceans shrimp raw",

    "raw shrimp shelled and de-veined":
        "crustaceans shrimp raw",

    "raw shrimp peeled and de-veined":
        "crustaceans shrimp raw",

    "crab":
        "crustaceans crab",

    "crab in shell":
        "crustaceans crab",

    # ========================================================
    # Vegetables
    # ========================================================

    "button mushroom":
        "mushrooms white raw",

    "button mushrooms":
        "mushrooms white raw",

    "white onion":
        "onions raw",

    "white onions":
        "onions raw",

    "green pepper":
        "peppers sweet green raw",

    "green peppers":
        "peppers sweet green raw",

    "tomato":
        "tomatoes red ripe raw",

    "tomatoes":
        "tomatoes red ripe raw",

    "eggplant":
        "eggplant raw",

    "zucchini":
        "squash summer zucchini raw",

    "pineapple":
        "pineapple raw",

    "fresh pineapple":
        "pineapple raw",

    # ========================================================
    # Other common ingredients
    # ========================================================

    "white vinegar":
        "vinegar distilled",

    "cornstach":
        "cornstarch",

    # ========================================================
    # Poultry
    # ========================================================

"chicken breast":
    "chicken broiler or fryers breast skinless boneless meat only raw",

"chicken breasts":
    "chicken broiler or fryers breast skinless boneless meat only raw",

"boneless chicken breast":
    "chicken broiler or fryers breast skinless boneless meat only raw",

"boneless chicken breasts":
    "chicken broiler or fryers breast skinless boneless meat only raw",

"skinless chicken breast":
    "chicken broiler or fryers breast skinless boneless meat only raw",

"skinless chicken breasts":
    "chicken broiler or fryers breast skinless boneless meat only raw",

"boneless skinless chicken breast":
    "chicken broiler or fryers breast skinless boneless meat only raw",

"boneless skinless chicken breasts":
    "chicken broiler or fryers breast skinless boneless meat only raw",

"chicken wings":
    "chicken broilers or fryers wing meat and skin raw",

"chicken wing":
    "chicken broilers or fryers wing meat and skin raw",


# ========================================================
# Vegetables
# ========================================================

"carrot":
    "carrots raw",

"carrots":
    "carrots raw",

"fresh mushroom":
    "mushrooms white raw",

"fresh mushrooms":
    "mushrooms white raw",

"mushroom":
    "mushrooms white raw",

"mushrooms":
    "mushrooms white raw",


# ========================================================
# Soy sauce
# ========================================================

"soy sauce":
    "soy sauce made from soy and wheat shoyu",

"light soy sauce":
    "soy sauce made from soy and wheat shoyu",

"dark soy sauce":
    "soy sauce made from soy and wheat shoyu",


# ========================================================
# Vinegar
# ========================================================

# USDA SR Legacy in our local database does not appear
# to contain a dedicated rice-vinegar record. Distilled
# vinegar is used as a conservative nutrition substitute.
"rice vinegar":
    "vinegar distilled",

"white rice vinegar":
    "vinegar distilled",
    # ========================================================
    # Pork
    # ========================================================

    "pork loin":
        "pork loin",

    "boneless center cut pork loin":
        "pork loin",

    # ========================================================
    # Common vegetables
    # ========================================================

    "onion":
        "onions raw",

    "onions":
        "onions raw",

    "green onions":
        "onions spring or scallions raw",

    "green onion":
        "onions spring or scallions raw",

    "scallions":
        "onions spring or scallions raw",

    "scallion":
        "onions spring or scallions raw",

    "napa cabbage":
        "cabbage napa raw",

    "garlic":
        "garlic raw",

    "garlic clove":
        "garlic raw",

    "garlic cloves":
        "garlic raw",

    "ginger":
        "ginger root raw",

    "fresh ginger":
        "ginger root raw",

    "red bell pepper":
        "peppers sweet red raw",

    "red bell peppers":
        "peppers sweet red raw",

    "green bell pepper":
        "peppers sweet green raw",

    "green bell peppers":
        "peppers sweet green raw",

    "carrot":
        "carrots raw",

    "carrots":
        "carrots raw",

    "cucumber":
        "cucumber with peel raw",

    "cucumbers":
        "cucumber with peel raw",

    "leek":
        "leeks raw",

    "leeks":
        "leeks raw",

    "bean sprouts":
        "mung beans mature seeds sprouted raw",

    "snow peas":
        "peas edible podded raw",

    "iceberg lettuce":
        "lettuce iceberg raw",

    # ========================================================
    # Noodles / wrappers
    # ========================================================

    "dried egg noodles":
        "noodles egg dry enriched",

    "egg noodles dried":
        "noodles egg dry enriched",

    "dried vermicelli":
        "vermicelli",

    "wanton skins":
        "wonton wrappers",

    "wonton skins":
        "wonton wrappers",

    "wanton wrappers":
        "wonton wrappers",

    "wonton wrappers":
        "wonton wrappers",

    # ========================================================
    # Seafood
    # ========================================================

    "shrimp":
        "crustaceans shrimp cooked",

    "cooked shrimp":
        "crustaceans shrimp cooked",

    "shelled cooked shrimp":
        "crustaceans shrimp cooked",

    "fresh raw shrimp":
        "crustaceans shrimp raw",

    "raw shrimp":
        "crustaceans shrimp raw",

    # ========================================================
    # Eggs
    # ========================================================

    "egg":
        "egg whole raw fresh",

    "eggs":
        "egg whole raw fresh",

    "egg yolk":
        "egg yolk raw fresh",

    "egg yolks":
        "egg yolk raw fresh",

    "egg white":
        "egg white raw fresh",

    "egg whites":
        "egg white raw fresh",

    # ========================================================
    # Mushrooms / water chestnuts
    # ========================================================

    "water chestnuts":
        "waterchestnuts chinese matai raw",

    "water chestnut":
        "waterchestnuts chinese matai raw",

    "dried chinese mushrooms":
        "mushrooms shiitake dried",

    "dried chinese mushroom":
        "mushrooms shiitake dried",

    # ========================================================
    # Sauces / condiments
    # ========================================================

    "ketchup":
        "catsup",

    "peanut butter":
        "peanut butter smooth",

    # ========================================================
    # Herbs / spices
    # ========================================================

    "cilantro":
        "coriander leaves raw",

    "fresh cilantro":
        "coriander leaves raw",

    "black pepper":
        "spices pepper black",

    "ground black pepper":
        "spices pepper black",

    "ground pepper":
        "spices pepper black",

    "five spice powder":
        "spices",

    "five spice":
        "spices",

    # ========================================================
    # Seeds / nuts
    # ========================================================

    "sesame seeds":
        "seeds sesame whole dried",

    "roasted sesame seeds":
        "seeds sesame whole roasted toasted",

    "cashews":
        "nuts cashew nuts",

    "roasted cashews":
        "nuts cashew nuts dry roasted",

    # ========================================================
    # Bouillon
    # ========================================================

    "instant chicken bouillon granules":
        "soup chicken broth or bouillon dry",

    # ========================================================
    # Starches
    # ========================================================

    "cornstarch":
        "cornstarch",

    # ========================================================
    # Water
    # ========================================================

    "water":
        "water bottled generic",

    # ========================================================
    # Oils
    # ========================================================

    "cooking oil":
        "oil vegetable canola",

    "vegetable oil":
        "oil vegetable canola",

    "sesame oil":
        "oil sesame salad or cooking",



    # ========================================================
    # Remaining recipe cleanup aliases
    # ========================================================

    # Chicken
    "a whole chicken or chicken pieces":
        "chicken broilers or fryers meat and skin raw",

    "whole chicken or chicken pieces":
        "chicken broilers or fryers meat and skin raw",

    # Fish
    "halibut fillets":
        "fish halibut raw",

    "fresh halibut fillets":
        "fish halibut raw",

    "turbot or halibut fillets":
        "fish halibut raw",

    "fresh fish fillet preferably cod or haddock":
        "fish cod raw",

    "or 2 firm white fish fillets of haddock halibut cod or seabass":
        "fish cod raw",

    # Pork / chicken alternatives
    "pork belly or fillet":
        "pork fresh belly raw",

    "lean boneless pork or chicken breasts":
        "chicken broiler or fryers breast skinless boneless meat only raw",

    "ground pork or chicken breasts":
        "pork fresh ground raw",

    # Tofu
    "firm bean curd":
        "tofu raw firm prepared with calcium",

    "tofu cake":
        "tofu raw firm prepared with calcium",

    # Shrimp
    "raw shrimp de-veined":
        "crustaceans shrimp raw",

    # Baking / coating
    "confectioners' sugar":
        "sugars powdered",

    "confectioners sugar":
        "sugars powdered",

    "panko breadcrumbs":
        "bread crumbs dry grated plain",

    # Potatoes
    "potatoes about 11/2 lbs":
        "potatoes flesh and skin raw",

    # Stocks
    "stock from shrimp":
        "soup fish broth",
}


# ============================================================
# Apply aliases
# ============================================================

def apply_aliases(
    food_name: str,
) -> str:

    normalized = normalize_food_name(
        food_name
    )

    # --------------------------------------------------------
    # Exact alias first
    # --------------------------------------------------------

    if normalized in FOOD_ALIASES:

        return FOOD_ALIASES[
            normalized
        ]

    # --------------------------------------------------------
    # Remove a few residual cookbook descriptors.
    #
    # Example:
    # "green onions green top removed"
    # becomes:
    # "green onions"
    # --------------------------------------------------------

    cleaned = normalized

    residual_phrases = [
        "green top removed",
        "tops removed",
        "root removed",
    ]

    for phrase in residual_phrases:

        cleaned = cleaned.replace(
            phrase,
            " ",
        )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()

    if cleaned in FOOD_ALIASES:

        return FOOD_ALIASES[
            cleaned
        ]

    return cleaned

# ============================================================
# Score one database record
# ============================================================

def score_match(
    query: str,
    description: str,
) -> float:

    query_norm = normalize_food_name(
        query
    )

    description_norm = normalize_food_name(
        description
    )

    query_words = set(
        query_norm.split()
    )

    description_words = set(
        description_norm.split()
    )

    if not query_words:
        return 0.0

    # Exact normalized description.
    if query_norm == description_norm:
        return 1.0

    # All query words appear in USDA description.
    if query_words.issubset(
        description_words
    ):

        coverage = (
            len(query_words)
            / max(
                len(description_words),
                1,
            )
        )

        return (
            0.90
            + 0.10 * coverage
        )

    overlap = (
        len(
            query_words
            & description_words
        )
        / len(query_words)
    )

    sequence = SequenceMatcher(
        None,
        query_norm,
        description_norm,
    ).ratio()

    return (
        0.65 * overlap
        + 0.35 * sequence
    )


# ============================================================
# Find best local nutrition match
# ============================================================

def has_complete_macros(
    record: dict,
) -> bool:

    required_fields = (
        "calories_per_100g",
        "protein_g_per_100g",
        "carbohydrates_g_per_100g",
        "fat_g_per_100g",
    )

    return all(
        record.get(field)
        is not None
        for field in required_fields
    )


@lru_cache(maxsize=4096)
def find_food_match(
    food_name: str,
    minimum_score: float = 0.60,
    require_complete_nutrition: bool = False,
    excluded_fdc_id=None,
):

    search_name = apply_aliases(
        food_name
    )

    best_record = None
    best_score = 0.0

    for record in NUTRITION_RECORDS:

        # ----------------------------------------------------
        # Optionally skip one specific USDA record.
        #
        # Useful when looking for a fallback to an incomplete
        # exact match.
        # ----------------------------------------------------

        if (
            excluded_fdc_id
            is not None
            and record.get(
                "fdc_id"
            )
            == excluded_fdc_id
        ):
            continue

        # ----------------------------------------------------
        # For nutrition fallbacks, only consider records that
        # actually contain all four macros.
        # ----------------------------------------------------

        if (
            require_complete_nutrition
            and not has_complete_macros(
                record
            )
        ):
            continue

        description = record.get(
            "description",
            "",
        )

        if not description:
            continue

        score = score_match(
            search_name,
            description,
        )

        if score > best_score:

            best_score = score
            best_record = record

    if (
        best_record is None
        or best_score < minimum_score
    ):

        return None

    return {
        "query":
            food_name,

        "normalized_query":
            search_name,

        "score":
            round(
                best_score,
                3,
            ),

        "record":
            best_record,
    }

@lru_cache(maxsize=4096)
def find_complete_nutrition_fallback(
    food_name: str,
    excluded_fdc_id=None,
    minimum_score: float = 0.65,
):

    return find_food_match(
        food_name=food_name,
        minimum_score=minimum_score,
        require_complete_nutrition=True,
        excluded_fdc_id=excluded_fdc_id,
    )

# ============================================================
# Simple command-line test
# ============================================================

def test_match(
    food_name: str,
):

    result = find_food_match(
        food_name
    )

    print(
        "\n=============================="
    )

    print(
        f"Nutrition search: {food_name}"
    )

    print(
        "=============================="
    )

    if not result:

        print(
            "No acceptable match found."
        )

        return

    record = result[
        "record"
    ]

    print(
        f"Matched: "
        f"{record['description']}"
    )

    print(
        f"Score: "
        f"{result['score']}"
    )

    print(
        f"Source: "
        f"{record['source']}"
    )

    print(
        f"Calories / 100 g: "
        f"{record['calories_per_100g']}"
    )

    print(
        f"Protein / 100 g: "
        f"{record['protein_g_per_100g']}"
    )

    print(
        f"Carbs / 100 g: "
        f"{record['carbohydrates_g_per_100g']}"
    )

    print(
        f"Fat / 100 g: "
        f"{record['fat_g_per_100g']}"
    )

@lru_cache(maxsize=4096)
def find_top_food_matches(
    food_name: str,
    limit: int = 10,
):

    search_name = apply_aliases(
        food_name
    )

    scored = []

    for record in NUTRITION_RECORDS:

        description = record.get(
            "description",
            "",
        )

        if not description:
            continue

        score = score_match(
            search_name,
            description,
        )

        scored.append(
            {
                "score":
                    score,

                "record":
                    record,
            }
        )

    scored.sort(
        key=lambda item:
            item["score"],
        reverse=True,
    )

    return scored[:limit]

if __name__ == "__main__":

    test_foods = [
            "a whole chicken or chicken pieces",
            "crab",
            "egg",
            "halibut fillets",
            "fresh fish fillet",
            "raw shrimp",
            "firm bean curd",
            "ground pork or chicken breasts",
            "pork belly or fillet",
        ]

    for food_name in test_foods:

        print(
            "\n================================"
        )

        print(
            f"SEARCH: {food_name}"
        )

        print(
            "================================"
        )
        print(
            f"Normalized: {normalize_food_name(food_name)}"
        )

        print(
            f"Aliased:    {apply_aliases(food_name)}"
        )

        matches = find_top_food_matches(
            food_name,
            limit=5,
        )

        for index, item in enumerate(
            matches,
            start=1,
        ):

            record = item[
                "record"
            ]

            print(
                f"\n{index}. "
                f"{record['description']}"
            )

            print(
                f"   Score: "
                f"{item['score']:.3f}"
            )

            print(
                f"   Source: "
                f"{record['source']}"
            )

            print(
                "   Calories/100g: "
                f"{record['calories_per_100g']}"
            )

            portions = record.get(
                "portions",
                [],
            )

            if portions:

                print(
                    "   Portions:"
                )

                for portion in portions[:8]:

                    print(
                        "     - "
                        f"{portion['description']} "
                        f"= {portion['gram_weight']} g"
                    )

            else:

                print(
                    "   Portions: none"
                )