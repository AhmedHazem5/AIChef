import json
from pathlib import Path

import chromadb

from llama_index.core import (
    Settings,
    StorageContext,
    VectorStoreIndex,
)

from llama_index.core.schema import (
    TextNode,
)

from llama_index.embeddings.ollama import (
    OllamaEmbedding,
)

from llama_index.vector_stores.chroma import (
    ChromaVectorStore,
)


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

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

CHROMA_DB_PATH = (
    PROJECT_ROOT
    / "rag"
    / "structured_chroma_db"
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


# ============================================================
# Load ALL structured recipe JSON files
# ============================================================

def load_structured_recipes():

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

        missing_text = "\n".join(
            f"  - {path}"
            for path in missing_files
        )

        raise FileNotFoundError(
            "Final recipe file(s) missing:\n"
            f"{missing_text}"
        )

    all_recipes = []

    seen_ids = set()

    print(
        "\nLoading structured recipe files..."
    )

    for json_file in json_files:

        try:

            with open(
                json_file,
                "r",
                encoding="utf-8",
            ) as file:

                recipes = json.load(
                    file
                )

        except json.JSONDecodeError as error:

            raise ValueError(
                "\nInvalid structured recipe JSON file:\n"
                f"  {json_file}\n\n"
                "The file is empty or contains invalid JSON."
            ) from error

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

            if recipe_id in seen_ids:

                raise ValueError(
                    "Duplicate recipe ID found: "
                    f"{recipe_id}\n"
                    f"File: {json_file.name}"
                )

            seen_ids.add(
                recipe_id
            )

            all_recipes.append(
                recipe
            )

    print(
        "\nTotal structured recipes: "
        f"{len(all_recipes)}"
    )

    return all_recipes


# ============================================================
# Convert recipe to ONE TextNode
#
# IMPORTANT:
#
# We use TextNode directly instead of Document.
#
# That prevents LlamaIndex from splitting a long recipe
# into multiple chunks/nodes.
#
# Result:
#
# 1 recipe = 1 node = 1 embedding
# ============================================================

def recipe_to_node(
    recipe: dict,
) -> TextNode:

    title = recipe.get(
        "title",
        "Unknown Recipe",
    )

    cuisine = recipe.get(
        "cuisine",
        "Unknown",
    )

    country = recipe.get(
        "country",
        "",
    )

    category = recipe.get(
        "category",
        "",
    )

    servings = recipe.get(
        "servings",
        "",
    )

    ingredients = recipe.get(
        "ingredients",
        [],
    )

    steps = recipe.get(
        "steps",
        [],
    )

    source_file = recipe.get(
        "source_file",
        "",
    )

    recipe_id = recipe[
        "id"
    ]

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

    carbs = nutrition.get(
        "carbohydrates_g"
    )

    fat = nutrition.get(
        "fat_g"
    )

    ingredients_text = "\n".join(
        f"- {ingredient}"
        for ingredient in ingredients
    )

    steps_text = "\n".join(
        f"{index}. {step}"
        for index, step in enumerate(
            steps,
            start=1,
        )
    )

    # --------------------------------------------------------
    # This text is what gets embedded.
    #
    # It includes enough semantic information for Chroma
    # retrieval while the original JSON remains the source
    # of truth.
    # --------------------------------------------------------

    text_parts = [
        f"Title: {title}",
        f"Cuisine: {cuisine}",
    ]

    if country:

        text_parts.append(
            f"Country: {country}"
        )

    if category:

        text_parts.append(
            f"Category: {category}"
        )

    if servings:

        text_parts.append(
            f"Servings: {servings}"
        )

    text_parts.extend(
        [
            "",
            "Ingredients:",
            ingredients_text,
            "",
            "Steps:",
            steps_text,
            "",
            "Nutrition:",
            f"Calories: {calories}",
            f"Protein: {protein} g",
            f"Carbohydrates: {carbs} g",
            f"Fat: {fat} g",
        ]
    )

    text = "\n".join(
        text_parts
    ).strip()

    # --------------------------------------------------------
    # Chroma metadata must use simple scalar values.
    # --------------------------------------------------------

    metadata = {
        "recipe_id":
            recipe_id,

        "title":
            title,

        "cuisine":
            cuisine,

        "country":
            country,    

        "category":
            category,

        "source_file":
            source_file,

        "servings":
            str(servings)
            if servings is not None
            else "",

        "calories":
            calories
            if calories is not None
            else -1,

        "protein_g":
            protein
            if protein is not None
            else -1,

        "carbohydrates_g":
            carbs
            if carbs is not None
            else -1,

        "fat_g":
            fat
            if fat is not None
            else -1,
    }

    return TextNode(
        id_=recipe_id,
        text=text,
        metadata=metadata,
    )


# ============================================================
# Clear old structured index
# ============================================================

def clear_index():

    count = collection.count()

    if count == 0:

        print(
            "Structured index is already empty."
        )

        return

    data = collection.get()

    ids = data.get(
        "ids",
        []
    )

    if ids:

        collection.delete(
            ids=ids
        )

    print(
        f"Removed {len(ids)} old "
        "structured recipe vectors."
    )


# ============================================================
# Build combined index
# ============================================================

def build_index():

    recipes = (
        load_structured_recipes()
    )

    # --------------------------------------------------------
    # Convert each recipe to exactly ONE node.
    # --------------------------------------------------------

    nodes = [
        recipe_to_node(
            recipe
        )
        for recipe in recipes
    ]

    print(
        f"\nWill create "
        f"{len(nodes)} embeddings."
    )

    print(
        "Each structured recipe "
        "creates exactly one embedding."
    )

    # --------------------------------------------------------
    # Cuisine totals
    # --------------------------------------------------------

    cuisine_counts = {}

    for recipe in recipes:

        cuisine = recipe.get(
            "cuisine",
            "Unknown",
        )

        cuisine_counts[cuisine] = (
            cuisine_counts.get(
                cuisine,
                0,
            )
            + 1
        )

    print(
        "\nRecipes by cuisine:"
    )

    for cuisine in sorted(
        cuisine_counts
    ):

        print(
            f"  {cuisine}: "
            f"{cuisine_counts[cuisine]}"
        )

    print()

    # --------------------------------------------------------
    # Clear old Chroma vectors
    # --------------------------------------------------------

    clear_index()

    # --------------------------------------------------------
    # Build storage context
    # --------------------------------------------------------

    storage_context = (
        StorageContext.from_defaults(
            vector_store=vector_store
        )
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # We index TextNodes directly.
    #
    # No Document splitter.
    # No transformation/chunking stage.
    #
    # One node stays one vector.
    # --------------------------------------------------------

    index = VectorStoreIndex(
        nodes=nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True,
    )

    # Prevent unused-variable warnings while keeping
    # a clear reference to the created index.
    _ = index

    # --------------------------------------------------------
    # Verify final Chroma count
    # --------------------------------------------------------

    stored_count = (
        collection.count()
    )

    expected_count = (
        len(nodes)
    )

    print(
        "\nStructured recipe index "
        "built successfully."
    )

    print(
        f"Stored vectors: "
        f"{stored_count}"
    )

    if (
        stored_count
        != expected_count
    ):

        print(
            "\nWARNING:"
        )

        print(
            f"Expected "
            f"{expected_count} vectors "
            f"but Chroma contains "
            f"{stored_count}."
        )

    else:

        print(
            "Vector count matches "
            "recipe count."
        )


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":

    build_index()