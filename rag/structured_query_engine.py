import json
import random
import re
from difflib import SequenceMatcher
from pathlib import Path

import chromadb

from routing.recipe_constraints import (
    extract_recipe_constraints,
)

from llama_index.core import (
    Settings,
    VectorStoreIndex,
)

from llama_index.embeddings.ollama import (
    OllamaEmbedding,
)

from llama_index.vector_stores.chroma import (
    ChromaVectorStore,
)

from rag.allergen_filter import (
    find_conflicts,
    normalize_user_allergies,
)

from rag.dietary_filter import (
    find_dietary_conflicts,
)

from rag.query_rewriter import (
    rewrite_query,
)


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHROMA_DB_PATH = (
    PROJECT_ROOT
    / "rag"
    / "structured_chroma_db"
)

STRUCTURED_RECIPE_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "structured_recipes"
)

FINAL_RECIPE_FILES = [
    STRUCTURED_RECIPE_DIRECTORY
    / "chinese_recipes_enriched.json",

    STRUCTURED_RECIPE_DIRECTORY
    / "japanese_recipes_enriched.json",

    STRUCTURED_RECIPE_DIRECTORY
    / "italian_recipes_gemini_nutrition_final.json",

    STRUCTURED_RECIPE_DIRECTORY
    / "italian2_recipes_gemini_nutrition_enriched.json",

    STRUCTURED_RECIPE_DIRECTORY
    / "healthy_foods_recipes_gemini_nutrition_enriched.json",

    STRUCTURED_RECIPE_DIRECTORY
    / "world_cuisines_recipes_gemini_nutrition_enriched.json",
]


# ============================================================
# Embeddings
# ============================================================

embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
)

Settings.embed_model = embed_model


# ============================================================
# Chroma
# ============================================================

chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_DB_PATH)
)

collection = (
    chroma_client
    .get_or_create_collection(
        name="structured_recipes"
    )
)

vector_store = ChromaVectorStore(
    chroma_collection=collection
)

index = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
)


# ============================================================
# Load ALL original structured recipes
# ============================================================

def load_recipe_records():

    if not STRUCTURED_RECIPE_DIRECTORY.exists():

        raise FileNotFoundError(
            "Structured recipe directory "
            "was not found at: "
            f"{STRUCTURED_RECIPE_DIRECTORY}"
        )

    json_files = FINAL_RECIPE_FILES

    missing_files = [
        path
        for path in json_files
        if not path.exists()
    ]

    if missing_files:

        raise FileNotFoundError(
            "Missing structured recipe files:\n"
            + "\n".join(
                f"  - {path}"
                for path in missing_files
            )
        )

    records = {}

    print(
        "\nLoading structured recipe library..."
    )

    for json_file in json_files:

        with open(
            json_file,
            "r",
            encoding="utf-8",
        ) as file:

            recipes = json.load(file)

        print(
            f"  {json_file.name}: "
            f"{len(recipes)} recipes"
        )

        for recipe in recipes:

            recipe_id = recipe.get(
                "id"
            )

            if not recipe_id:

                print(
                    "WARNING: Recipe without ID "
                    f"in {json_file.name}. "
                    "Skipping."
                )

                continue

            if recipe_id in records:

                raise ValueError(
                    "Duplicate recipe ID found: "
                    f"{recipe_id}\n"
                    f"File: {json_file.name}"
                )

            records[
                recipe_id
            ] = recipe

    print(
        f"Total structured recipes loaded: "
        f"{len(records)}"
    )

    return records


RECIPE_RECORDS = load_recipe_records()


# ============================================================
# Errors
# ============================================================

class UnsupportedAllergyError(Exception):
    pass


class NoSafeRecipeError(Exception):
    pass


class SpecificRecipeAllergyError(Exception):

    def __init__(
        self,
        recipe: dict,
        conflicts: set[str],
    ):

        self.recipe = recipe

        self.title = recipe.get(
            "title",
            "This recipe",
        )

        self.recipe_id = recipe.get(
            "id"
        )

        self.conflicts = conflicts

        super().__init__(
            self.title
        )


class SpecificRecipeDietaryError(Exception):

    def __init__(
        self,
        recipe: dict,
        conflicts: set[str],
    ):

        self.recipe = recipe

        self.title = recipe.get(
            "title",
            "This recipe",
        )

        self.recipe_id = recipe.get(
            "id"
        )

        self.conflicts = conflicts

        super().__init__(
            self.title
        )


# ============================================================
# Database status
# ============================================================

def structured_database_is_empty():

    return (
        collection.count()
        == 0
    )


# ============================================================
# Recipe-title matching
# ============================================================

REQUEST_STOPWORDS = {
    "i",
    "me",
    "my",
    "want",
    "would",
    "like",
    "please",
    "can",
    "could",
    "you",
    "give",
    "get",
    "prepare",
    "cook",
    "do",
    "make",
    "the",
    "a",
    "an",
    "recipe",
    "for",
    "to",
}


def normalize_word(
    word: str,
):

    word = word.lower()

    if (
        len(word) > 3
        and word.endswith("s")
        and not word.endswith("ss")
    ):
        word = word[:-1]

    return word


def get_match_tokens(
    text: str,
):

    words = re.findall(
        r"[a-zA-Z0-9']+",
        text.lower(),
    )

    tokens = []

    for word in words:

        word = normalize_word(
            word
        )

        if word in REQUEST_STOPWORDS:
            continue

        tokens.append(
            word
        )

    return tokens


def find_specific_recipe(
    user_query: str,
):

    query_tokens = get_match_tokens(
        user_query
    )

    if len(query_tokens) < 2:
        return None

    query_normalized = " ".join(
        query_tokens
    )

    best_recipe = None
    best_score = 0.0

    for recipe in (
        RECIPE_RECORDS.values()
    ):

        title = recipe.get(
            "title",
            "",
        )

        title_tokens = get_match_tokens(
            title
        )

        if not title_tokens:
            continue

        title_normalized = " ".join(
            title_tokens
        )

        query_set = set(
            query_tokens
        )

        title_set = set(
            title_tokens
        )

        if query_set.issubset(
            title_set
        ):

            coverage = (
                len(query_set)
                / len(title_set)
            )

            score = (
                0.90
                + 0.10 * coverage
            )

        else:

            score = SequenceMatcher(
                None,
                query_normalized,
                title_normalized,
            ).ratio()

        if score > best_score:

            best_score = score
            best_recipe = recipe

    if (
        best_recipe
        and best_score >= 0.82
    ):

        print(
            "\nSpecific recipe request detected:"
        )

        print(
            f"  Recipe: "
            f"{best_recipe['title']}"
        )

        print(
            f"  Match score: "
            f"{best_score:.2f}"
        )

        return best_recipe

    return None


# ============================================================
# Allergy helper
# ============================================================

def get_recipe_conflicts(
    recipe: dict,
    user_allergens: set[str],
):

    ingredients = recipe.get(
        "ingredients",
        [],
    )

    return find_conflicts(
        " ".join(ingredients),
        user_allergens,
    )


# ============================================================
# Retrieval
# ============================================================

def retrieve_structured_recipe(
    query: str,
    allergies: list[str] | None = None,
    dietary_preferences: list[str] | None = None,
    excluded_recipe_ids: set[str] | None = None,
    allow_specific_match: bool = True,
    search_query_override: str | None = None,
):

    if allergies is None:
        allergies = []

    if dietary_preferences is None:
        dietary_preferences = []

    dietary_preferences = [
        preference.lower().strip()
        for preference in dietary_preferences
        if (
            isinstance(preference, str)
            and preference.strip()
        )
    ]

    if excluded_recipe_ids is None:
        excluded_recipe_ids = set()

    (
        user_allergens,
        unsupported_allergies,
    ) = normalize_user_allergies(
        allergies
    )

    if unsupported_allergies:

        names = ", ".join(
            unsupported_allergies
        )

        raise UnsupportedAllergyError(
            "I cannot safely filter recipes "
            f"for these allergies yet: {names}."
        )

    # ========================================================
    # Specific named recipe
    # ========================================================

    if allow_specific_match:

        specific_recipe = (
            find_specific_recipe(
                query
            )
        )

        if specific_recipe:

            title = specific_recipe[
                "title"
            ]

            cuisine = specific_recipe.get(
                "cuisine",
                "Unknown",
            )

            conflicts = (
                get_recipe_conflicts(
                    specific_recipe,
                    user_allergens,
                )
            )

            print(
                "\nChecking requested recipe "
                "against saved allergies..."
            )

            if conflicts:

                print(
                    f"BLOCKED SPECIFIC RECIPE: "
                    f"{title} "
                    f"[{cuisine}] "
                    f"because of "
                    f"{sorted(conflicts)}"
                )

                raise (
                    SpecificRecipeAllergyError(
                        recipe=specific_recipe,
                        conflicts=conflicts,
                    )
                )

            dietary_text_parts = (
                list(
                    specific_recipe.get(
                        "ingredients",
                        [],
                    )
                )
                + list(
                    specific_recipe.get(
                        "steps",
                        [],
                    )
                )
                + [
                    specific_recipe.get(
                        "title",
                        "",
                    ),
                    specific_recipe.get(
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

                print(
                    f"BLOCKED SPECIFIC RECIPE: "
                    f"{title} "
                    f"[{cuisine}] "
                    f"because of dietary preferences "
                    f"{sorted(dietary_conflicts)}"
                )

                raise SpecificRecipeDietaryError(
                    recipe=specific_recipe,
                    conflicts=dietary_conflicts,
                )

            print(
                f"SAFE SPECIFIC RECIPE: "
                f"{title} "
                f"[{cuisine}]"
            )

            return {
                "recipe_id":
                    specific_recipe[
                        "id"
                    ],

                "recipe":
                    specific_recipe,

                "specific_request":
                    True,
            }

    # ========================================================
    # General / alternative semantic search
    # ========================================================

    if search_query_override:

        search_query = (
            search_query_override
        )

    else:

        search_query = rewrite_query(
            query
        )

    # ========================================================
    # Extract explicit user constraints
    #
    # Example:
    #
    # "Give me a Chinese noodle recipe"
    #
    # becomes:
    #
    # cuisine  = Chinese
    # category = Noodles
    # ========================================================

    constraints = (
        extract_recipe_constraints(
            query
        )
    )

    required_cuisine = (
        constraints.get(
            "cuisine"
        )
    )

    required_category = (
        constraints.get(
            "category"
        )
    )

    required_ingredients = (
        constraints.get(
            "required_ingredients",
            []
        )
    )

    max_calories = constraints.get(
        "max_calories"
    )

    min_calories = constraints.get(
        "min_calories"
    )

    min_protein_g = constraints.get(
        "min_protein_g"
    )

    max_protein_g = constraints.get(
        "max_protein_g"
    )

    max_carbohydrates_g = constraints.get(
        "max_carbohydrates_g"
    )

    max_fat_g = constraints.get(
        "max_fat_g"
    )

    nutrition_preference = constraints.get(
        "nutrition_preference"
    )

    # ========================================================
    # Early explicit dietary conflict check
    #
    # Example:
    # saved preference = halal
    # request category = Pork
    #
    # Reject immediately instead of retrieving many pork
    # recipes just to block every one of them.
    # ========================================================

    explicit_dietary_terms = []

    if required_category:
        explicit_dietary_terms.append(
            required_category
        )

    explicit_dietary_terms.extend(
        required_ingredients
    )

    explicit_dietary_conflicts = (
        find_dietary_conflicts(
            explicit_dietary_terms,
            dietary_preferences,
        )
    )

    if explicit_dietary_conflicts:

        preferences_text = ", ".join(
            sorted(
                explicit_dietary_conflicts
            )
        )

        requested_text = " ".join(
            explicit_dietary_terms
        ).strip()

        if not requested_text:
            requested_text = "That request"

        # Build a lightweight synthetic blocked request.
        #
        # This lets recipe_node save it as pending context so
        # a follow-up such as "yes" can trigger a safe,
        # semantically similar alternative search.
        blocked_request = {
            "id":
                None,

            "title":
                (
                    f"{requested_text} recipe"
                    if not requested_text.lower().endswith(
                        "recipe"
                    )
                    else requested_text
                ),

            "cuisine":
                required_cuisine
                or "",

            "category":
                required_category
                or "",

            "ingredients":
                list(
                    required_ingredients
                ),

            "steps":
                [],
        }

        raise SpecificRecipeDietaryError(
            recipe=blocked_request,
            conflicts=explicit_dietary_conflicts,
        )

    print(
        f"\nStructured RAG search query: "
        f"{search_query}"
    )

    # ========================================================
    # Retrieve a larger candidate pool because we may reject
    # candidates due to:
    #
    # cuisine mismatch
    # category mismatch
    # allergies
    # excluded recipes
    # ========================================================

    retriever = index.as_retriever(
        similarity_top_k=50,
    )

    nodes = retriever.retrieve(
        search_query
    )

    if not nodes:
        return None

    print(
        "\nStructured recipe safety filtering:"
    )

    if user_allergens:

        print(
            "Saved allergies:",
            sorted(user_allergens),
        )

    else:

        print(
            "No saved allergies."
        )

    if dietary_preferences:

        print(
            "Saved dietary preferences:",
            sorted(dietary_preferences),
        )

    else:

        print(
            "No saved dietary preferences."
        )

    # ========================================================
    # Collect safe candidates
    #
    # Broad requests can still return some variety, but only
    # AFTER explicit cuisine/category constraints are applied.
    # ========================================================

    safe_candidates = []

    MAX_SAFE_CANDIDATES = 5

    for node in nodes:

        recipe_id = (
            node.metadata.get(
                "recipe_id",
                str(node.node_id),
            )
        )

        # ----------------------------------------------------
        # Skip deliberately excluded recipes
        # ----------------------------------------------------

        if recipe_id in excluded_recipe_ids:

            print(
                f"SKIPPED EXCLUDED RECIPE: "
                f"{recipe_id}"
            )

            continue

        # ----------------------------------------------------
        # Load authoritative recipe from JSON
        # ----------------------------------------------------

        recipe = RECIPE_RECORDS.get(
            recipe_id
        )

        if not recipe:

            print(
                f"WARNING: Recipe "
                f"{recipe_id} exists in Chroma "
                "but was not found in the "
                "structured JSON library."
            )

            continue

        title = recipe.get(
            "title",
            "Unknown recipe",
        )

        cuisine = recipe.get(
            "cuisine",
            "Unknown",
        )

        category = recipe.get(
            "category",
            "",
        )
        # ====================================================
        # Explicit required ingredient constraints
        #
        # Example:
        #
        # "I want something with garlic and chicken"
        #
        # Every candidate must contain BOTH garlic and chicken.
        # ====================================================

        if required_ingredients:

            recipe_ingredients = (
                recipe.get(
                    "ingredients",
                    []
                )
            )

            ingredient_text = " ".join(
                str(item).lower()
                for item in recipe_ingredients
            )

            missing_required = []

            for required_ingredient in (
                required_ingredients
            ):

                if (
                    required_ingredient.lower()
                    not in ingredient_text
                ):

                    missing_required.append(
                        required_ingredient
                    )

            if missing_required:

                print(
                    f"SKIPPED REQUIRED INGREDIENT "
                    f"MISMATCH: "
                    f"{title} "
                    f"missing "
                    f"{missing_required}"
                )

                continue

        # ====================================================
        # Explicit cuisine constraint
        # ====================================================

        if required_cuisine:

            if (
                cuisine.lower()
                != required_cuisine.lower()
            ):

                print(
                    f"SKIPPED CUISINE MISMATCH: "
                    f"{title} "
                    f"[{cuisine}]"
                )

                continue

        # ====================================================
        # Explicit category constraint
        # ====================================================

        if required_category:

            # Chinese recipes already have categories.
            #
            # Japanese recipes currently may not have a
            # category field, so we do not automatically throw
            # them away just because the field is missing.
            #
            # If a category exists, however, it must match.
            if category:

                if (
                    category.lower()
                    != required_category.lower()
                ):

                    print(
                        f"SKIPPED CATEGORY MISMATCH: "
                        f"{title} "
                        f"[{category}]"
                    )

                    continue

        # ====================================================
        # Nutrition filtering
        # ====================================================

        nutrition = recipe.get(
            "nutrition",
            {},
        )

        calories = nutrition.get(
            "calories"
        )

        protein_g = nutrition.get(
            "protein_g"
        )

        carbohydrates_g = nutrition.get(
            "carbohydrates_g"
        )

        fat_g = nutrition.get(
            "fat_g"
        )

        # ----------------------------------------------------
        # Maximum calories
        # ----------------------------------------------------

        if (
            max_calories is not None
            and (
                calories is None
                or calories > max_calories
            )
        ):

            print(
                f"SKIPPED MAX CALORIES: "
                f"{title} "
                f"({calories} kcal)"
            )

            continue

        # ----------------------------------------------------
        # Minimum calories
        # ----------------------------------------------------

        if (
            min_calories is not None
            and (
                calories is None
                or calories < min_calories
            )
        ):

            print(
                f"SKIPPED MIN CALORIES: "
                f"{title} "
                f"({calories} kcal)"
            )

            continue

        # ----------------------------------------------------
        # Minimum protein
        # ----------------------------------------------------

        if (
            min_protein_g is not None
            and (
                protein_g is None
                or protein_g < min_protein_g
            )
        ):

            print(
                f"SKIPPED MIN PROTEIN: "
                f"{title} "
                f"({protein_g} g)"
            )

            continue

        # ----------------------------------------------------
        # Maximum protein
        # ----------------------------------------------------

        if (
            max_protein_g is not None
            and (
                protein_g is None
                or protein_g > max_protein_g
            )
        ):

            print(
                f"SKIPPED MAX PROTEIN: "
                f"{title} "
                f"({protein_g} g)"
            )

            continue

        # ----------------------------------------------------
        # Maximum carbohydrates
        # ----------------------------------------------------

        if (
            max_carbohydrates_g is not None
            and (
                carbohydrates_g is None
                or carbohydrates_g
                > max_carbohydrates_g
            )
        ):

            print(
                f"SKIPPED MAX CARBS: "
                f"{title} "
                f"({carbohydrates_g} g)"
            )

            continue

        # ----------------------------------------------------
        # Maximum fat
        # ----------------------------------------------------

        if (
            max_fat_g is not None
            and (
                fat_g is None
                or fat_g > max_fat_g
            )
        ):

            print(
                f"SKIPPED MAX FAT: "
                f"{title} "
                f"({fat_g} g)"
            )

            continue

        # ====================================================
        # Allergy filtering
        # ====================================================

        conflicts = get_recipe_conflicts(
            recipe,
            user_allergens,
        )

        if conflicts:

            print(
                f"BLOCKED: "
                f"{title} "
                f"[{cuisine}] "
                f"because of "
                f"{sorted(conflicts)}"
            )

            continue

        # ====================================================
        # Dietary preference filtering
        #
        # For vague/general searches, incompatible recipes are
        # silently removed from the candidate pool.
        # ====================================================

        dietary_text_parts = (
            list(
                recipe.get(
                    "ingredients",
                    [],
                )
            )
            + list(
                recipe.get(
                    "steps",
                    [],
                )
            )
            + [
                recipe.get(
                    "title",
                    "",
                ),
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

            print(
                f"BLOCKED DIETARY: "
                f"{title} "
                f"[{cuisine}] "
                f"because of "
                f"{sorted(dietary_conflicts)}"
            )

            continue

        # ====================================================
        # Safe candidate
        # ====================================================

        print(
            f"SAFE CANDIDATE: "
            f"{title} "
            f"[{cuisine}]"
        )

        safe_candidates.append(
            recipe
        )

        # For normal searches, keep the existing behavior:
        # collect the first 5 strong valid semantic matches.
        #
        # For relative nutrition requests such as
        # "high protein" or "low fat", keep scanning the
        # retrieved pool so we can rank a larger set properly.
        if (
            nutrition_preference is None
            and len(safe_candidates)
            >= MAX_SAFE_CANDIDATES
        ):
            break

    # ========================================================
    # Select recipe
    #
    # Normal search:
    #   random choice among the first 5 valid semantic matches.
    #
    # Relative nutrition preference:
    #   rank all valid retrieved candidates by the requested
    #   nutrition field and select the best one.
    # ========================================================

    if safe_candidates:

        if nutrition_preference:

            def nutrition_value(
                recipe: dict,
                field: str,
            ):

                nutrition = recipe.get(
                    "nutrition",
                    {},
                )

                value = nutrition.get(
                    field
                )

                if isinstance(
                    value,
                    (int, float),
                ):
                    return float(value)

                return None


            preference_config = {
                "high_protein": {
                    "field":
                        "protein_g",

                    "reverse":
                        True,

                    "label":
                        "protein",
                },

                "low_calorie": {
                    "field":
                        "calories",

                    "reverse":
                        False,

                    "label":
                        "calories",
                },

                "low_fat": {
                    "field":
                        "fat_g",

                    "reverse":
                        False,

                    "label":
                        "fat",
                },

                "low_carb": {
                    "field":
                        "carbohydrates_g",

                    "reverse":
                        False,

                    "label":
                        "carbohydrates",
                },
            }

            config = preference_config.get(
                nutrition_preference
            )

            ranked_candidates = []

            if config:

                field = config[
                    "field"
                ]

                reverse = config[
                    "reverse"
                ]

                for candidate in safe_candidates:

                    value = nutrition_value(
                        candidate,
                        field,
                    )

                    if value is None:
                        continue

                    ranked_candidates.append(
                        (
                            value,
                            candidate,
                        )
                    )

                ranked_candidates.sort(
                    key=lambda item: item[0],
                    reverse=reverse,
                )

            if ranked_candidates:

                selected_value, selected_recipe = (
                    ranked_candidates[0]
                )

                print(
                    "\nNutrition preference ranking:"
                )

                print(
                    f"  Preference: "
                    f"{nutrition_preference}"
                )

                print(
                    f"  Candidates ranked: "
                    f"{len(ranked_candidates)}"
                )

                print(
                    f"  Best "
                    f"{config['label']}: "
                    f"{selected_value}"
                )

            else:

                print(
                    "\nWARNING: No candidates had "
                    "usable nutrition values for "
                    f"{nutrition_preference}. "
                    "Falling back to normal selection."
                )

                selected_recipe = (
                    random.choice(
                        safe_candidates
                    )
                )

        else:

            selected_recipe = (
                random.choice(
                    safe_candidates
                )
            )

        title = selected_recipe.get(
            "title",
            "Unknown recipe",
        )

        cuisine = selected_recipe.get(
            "cuisine",
            "Unknown",
        )

        category = selected_recipe.get(
            "category",
            "",
        )

        nutrition = selected_recipe.get(
            "nutrition",
            {},
        )

        print(
            f"\nSELECTED SAFE RECIPE: "
            f"{title} "
            f"[{cuisine}]"
        )

        print(
            f"Safe candidate pool: "
            f"{len(safe_candidates)}"
        )

        print(
            "\nSelected structured recipe:"
        )

        print(
            f"  Title: {title}"
        )

        print(
            f"  Cuisine: {cuisine}"
        )

        if category:

            print(
                f"  Category: {category}"
            )

        print(
            "  Calories: "
            f"{nutrition.get('calories')}"
        )

        print(
            "  Protein: "
            f"{nutrition.get('protein_g')} g"
        )

        return {
            "recipe_id":
                selected_recipe[
                    "id"
                ],

            "recipe":
                selected_recipe,

            "specific_request":
                False,
        }

    # ========================================================
    # Nothing matched the explicit constraints
    # ========================================================

    constraint_parts = []

    if required_cuisine:

        constraint_parts.append(
            required_cuisine
        )

    if required_category:

        constraint_parts.append(
            required_category
        )

    if constraint_parts:

        description = " ".join(
            constraint_parts
        )

        raise NoSafeRecipeError(
            "I couldn't find a safe "
            f"{description} recipe "
            "that matches your request."
        )

    # ========================================================
    # No safe general recipe found
    # ========================================================

    if (
        user_allergens
        or dietary_preferences
    ):

        raise NoSafeRecipeError(
            "I couldn't find a recipe "
            "that passed your saved allergy "
            "and dietary preference filters."
        )

    return None