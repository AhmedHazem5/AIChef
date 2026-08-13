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

    json_files = sorted(
        STRUCTURED_RECIPE_DIRECTORY.glob(
            "*_recipes.json"
        )
    )

    if not json_files:

        raise FileNotFoundError(
            "No structured recipe JSON files "
            "were found in: "
            f"{STRUCTURED_RECIPE_DIRECTORY}"
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
    excluded_recipe_ids: set[str] | None = None,
    allow_specific_match: bool = True,
    search_query_override: str | None = None,
):

    if allergies is None:
        allergies = []

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

        if (
            len(safe_candidates)
            >= MAX_SAFE_CANDIDATES
        ):
            break

    # ========================================================
    # Randomly choose among the best valid safe candidates
    # ========================================================

    if safe_candidates:

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

    if user_allergens:

        raise NoSafeRecipeError(
            "I couldn't find a recipe "
            "that passed your allergy filters."
        )

    return None