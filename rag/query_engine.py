from llama_index.core import (
    Settings,
    VectorStoreIndex,
)

from llama_index.core.vector_stores import (
    MetadataFilter,
    MetadataFilters,
)

from rag.allergen_filter import (
    find_conflicts,
    normalize_user_allergies,
)

from rag.cuisine_detector import (
    detect_cuisine,
)

from rag.query_rewriter import (
    rewrite_query,
)

from rag.settings import (
    embed_model,
    vector_store,
)


# ============================================================
# Configuration
# ============================================================

RETRIEVAL_TOP_K = 20

# Only ONE chunk goes to Qwen per attempt.
# If the generated recipe is unsafe, recipe_node will retry
# using another chunk.
MAX_CONTEXT_CHUNKS = 4

MAX_CHARS_PER_CHUNK = 1200
MAX_TOTAL_CONTEXT_CHARS = 4500


# ============================================================
# Errors
# ============================================================

class UnsupportedAllergyError(Exception):
    pass


class NoSafeRecipeError(Exception):
    pass


# ============================================================
# LlamaIndex
# ============================================================

Settings.embed_model = embed_model

index = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
)


# ============================================================
# Database status
# ============================================================

def recipe_database_is_empty() -> bool:
    try:
        return (
            vector_store
            ._collection
            .count()
            == 0
        )

    except Exception:
        return True


# ============================================================
# Text cleanup
# ============================================================

def clean_retrieved_text(
    text: str,
) -> str:

    if not text:
        return ""

    # Collapse strange PDF whitespace.
    return " ".join(
        text.split()
    ).strip()


def trim_text(
    text: str,
    max_characters: int,
) -> str:

    cleaned = clean_retrieved_text(
        text
    )

    if len(cleaned) <= max_characters:
        return cleaned

    return (
        cleaned[:max_characters]
        + "..."
    )


# ============================================================
# Retrieve safe recipe context
# ============================================================

def retrieve_recipe_context(
    query: str,
    allergies: list[str] | None = None,
    excluded_node_ids: set[str] | None = None,
):
    """
    Retrieve ONE safe recipe candidate.

    Returns:

        {
            "context": "...",
            "node_id": "...",
            "source_file": "...",
            "cuisine": "..."
        }

    recipe_node can call this again while excluding previous
    candidates if Qwen generates an unsafe final recipe.
    """

    if allergies is None:
        allergies = []

    if excluded_node_ids is None:
        excluded_node_ids = set()

    # --------------------------------------------------------
    # Normalize allergies
    # --------------------------------------------------------

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
            "for these allergies yet: "
            f"{names}."
        )

    # --------------------------------------------------------
    # Search preparation
    # --------------------------------------------------------

    cuisine = detect_cuisine(
        query
    )

    search_query = rewrite_query(
        query
    )

    print(
        f"\nRAG search query: "
        f"{search_query}"
    )

    filters = None

    if cuisine:

        print(
            f"Cuisine filter: "
            f"{cuisine}"
        )

        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="cuisine",
                    value=cuisine,
                )
            ]
        )

    # --------------------------------------------------------
    # Retrieve many candidates.
    # --------------------------------------------------------

    retriever = index.as_retriever(
        similarity_top_k=
            RETRIEVAL_TOP_K,

        filters=filters,
    )

    nodes = retriever.retrieve(
        search_query
    )

    if not nodes:
        return None

    # --------------------------------------------------------
    # Hard allergy filtering
    # --------------------------------------------------------

    print(
        "\nRecipe safety filtering:"
    )

    if user_allergens:

        print(
            "Saved allergies:",
            sorted(
                user_allergens
            ),
        )

    else:

        print(
            "No saved allergies."
        )

    safe_candidates = []

    for node in nodes:

        node_id = str(
            node.node_id
        )

        # Already tried this candidate.
        if node_id in excluded_node_ids:

            print(
                "SKIPPED PREVIOUS CANDIDATE:",
                node_id,
            )

            continue

        source_file = (
            node.metadata.get(
                "source_file",
                "Unknown source",
            )
        )

        cuisine_name = (
            node.metadata.get(
                "cuisine",
                "Unknown",
            )
        )

        conflicts = find_conflicts(
            node.text,
            user_allergens,
        )

        if conflicts:

            print(
                f"BLOCKED: "
                f"{source_file} "
                f"[{cuisine_name}] "
                f"because of "
                f"{sorted(conflicts)}"
            )

            continue

        print(
            f"SAFE CANDIDATE: "
            f"{source_file} "
            f"[{cuisine_name}]"
        )

        safe_candidates.append(
            node
        )

    # --------------------------------------------------------
    # No safe candidate available.
    # --------------------------------------------------------

    if not safe_candidates:

        if user_allergens:

            raise NoSafeRecipeError(
                "I couldn't find another recipe "
                "that passed your allergy filters."
            )

        return None

    # --------------------------------------------------------
    # Use the BEST remaining safe candidate.
    # --------------------------------------------------------

    selected_nodes = safe_candidates[
        :MAX_CONTEXT_CHUNKS
    ]

    context_parts = []

    current_size = 0

    used_node_ids = []

    for node in selected_nodes:

        node_id = str(
            node.node_id
        )

        source_file = (
            node.metadata.get(
                "source_file",
                "Unknown source",
            )
        )

        cuisine_name = (
            node.metadata.get(
                "cuisine",
                "Unknown",
            )
        )

        selected_text = trim_text(
            node.text,
            MAX_CHARS_PER_CHUNK,
        )

        block = (
            f"Recipe source: {source_file}\n"
            f"Cuisine: {cuisine_name}\n\n"
            f"{selected_text}"
        )

        remaining = (
            MAX_TOTAL_CONTEXT_CHARS
            - current_size
        )

        if remaining <= 0:
            break

        if len(block) > remaining:
            block = block[:remaining]

        context_parts.append(
            block
        )

        current_size += len(block)

        used_node_ids.append(
            node_id
        )


    context = (
        "\n\n--- NEXT RECIPE SECTION ---\n\n"
    ).join(
        context_parts
    )


    print(
        f"\nUsing "
        f"{len(context_parts)} "
        "safe chunks."
    )

    print(
        f"Context size: "
        f"{len(context):,} characters"
    )


    return {
        "context": context,

        "node_ids": used_node_ids,

        "source_file": (
            selected_nodes[0]
            .metadata.get(
                "source_file",
                "Unknown source",
            )
        ),

        "cuisine": (
            selected_nodes[0]
            .metadata.get(
                "cuisine",
                "Unknown",
            )
        ),
    }

    source_file = (
        selected_node.metadata.get(
            "source_file",
            "Unknown source",
        )
    )

    cuisine_name = (
        selected_node.metadata.get(
            "cuisine",
            "Unknown",
        )
    )

    selected_text = trim_text(
        selected_node.text,
        MAX_CHARS_PER_CHUNK,
    )

    context = (
        f"Recipe source: {source_file}\n"
        f"Cuisine: {cuisine_name}\n\n"
        f"{selected_text}"
    )

    context = context[
        :MAX_TOTAL_CONTEXT_CHARS
    ]

    print(
        "\nSelected candidate:"
    )

    print(
        f"  Source: {source_file}"
    )

    print(
        f"  Cuisine: {cuisine_name}"
    )

    print(
        f"  Context size: "
        f"{len(context):,} characters"
    )

    return {
        "context": context,

        "node_id": str(
            selected_node.node_id
        ),

        "source_file":
            source_file,

        "cuisine":
            cuisine_name,
    }