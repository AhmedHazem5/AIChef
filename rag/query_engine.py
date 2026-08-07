from llama_index.core import Settings
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import (
    MetadataFilter,
    MetadataFilters,
)

from rag.settings import (
    embed_model,
    vector_store,
)

from rag.cuisine_detector import detect_cuisine

import ollama


MODEL_NAME = "qwen3:4b-instruct"


def rewrite_query(user_query: str) -> str:
    """
    Rewrite the user's recipe request into a concise search query.
    """

    prompt = f"""
Rewrite the user's request into a concise recipe search query.

Rules:
- Keep it under 12 words.
- Preserve cuisine if mentioned.
- Preserve ingredients if mentioned.
- Preserve dish names if mentioned.
- Do not answer the question.
- Return ONLY the rewritten search query.

User request:
{user_query}
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        options={
            "temperature": 0,
        },
    )

    return response["message"]["content"].strip()

# --------------------------------------------------
# LlamaIndex configuration
# --------------------------------------------------

Settings.embed_model = embed_model


# --------------------------------------------------
# Load existing index
# --------------------------------------------------

index = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
)


def recipe_database_is_empty() -> bool:
    """
    Returns True if no recipe chunks exist.
    """

    try:
        return vector_store._collection.count() == 0
    except Exception:
        return True


def retrieve_recipe_context(query: str) -> str:
    """
    Retrieve recipe chunks from ChromaDB.

    If a cuisine is detected,
    search only that cuisine.

    Otherwise,
    search the whole recipe database.
    """

    cuisine = detect_cuisine(query)
    search_query = rewrite_query(query)

    filters = None

    if cuisine:

        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="cuisine",
                    value=cuisine,
                )
            ]
        )

    retriever = index.as_retriever(
        similarity_top_k=3,
        filters=filters,
    )

    nodes = retriever.retrieve(search_query)

    if not nodes:
        return ""

    context = []

    for node in nodes:

        cuisine_name = node.metadata.get(
            "cuisine",
            "Unknown",
        )

        context.append(
            f"Cuisine: {cuisine_name}\n\n{node.text}"
        )

    return "\n\n------------------------\n\n".join(
        context
    )